"""Native global, native enlarged-view consensus, VIDEO tracking comparison.

No audio/reference labels choose the skeleton. Every selected point set belongs
to one current-frame model inference. No hand/finger relabeling or point repair.
"""
import json
import hashlib
from pathlib import Path
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from fretting_hand_skeleton import FrettingHandSkeletonDetector,hand_bounding_crop
from global_fretting_hand import detect_global_fretting,rank_view
from improve_hand_skeleton import serialize
from review_fretboard_clip import track,project,REFERENCE_CORNERS,make_board
from fretboard_frame_identity import make_frame_identity
from whole_hand_consensus import choose_candidate
from hand_cell_distribution import sample_projected,integrate_points
from low_string_root_prior import assess

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/hand_analysis/runs/low_string_stability_20261105_v1'
VIDEO_ID='283220036613f22a618aaaad2574df638085772dde16eec05c7e56caccd1da2f'
from virtual_string_grid import build_grid

def distributions(grid,hand):
    if hand is None:return []
    result=[]
    for tip,name in [(8,'index'),(12,'middle'),(16,'ring'),(20,'pinky')]:
        pixel=hand['pixel_landmarks'][tip];points,valid=sample_projected(grid,pixel,12,samples=2048)
        result.append(dict(finger=name,tip_index=tip,pixel=pixel,**integrate_points(grid,points,valid)))
    return result

def main():
    if OUT.exists():raise FileExistsError(OUT)
    (OUT/'frames').mkdir(parents=True);manifest=json.loads((ROOT/'dataset/integration_review/runs/actual_video_review_20261105_v1/manifest.json').read_text());source=Path(manifest['source_video']);cap=cv2.VideoCapture(str(source))
    reference=cv2.imread(str(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000120.png'))
    records=[];previous=None;segments=[('middle_200',199.5,200.5),('root_214',213.,214.5),('new_257',256.5,257.5)]
    with FrettingHandSkeletonDetector(ROOT/'hand_landmarker.task',num_hands=2) as image_detector:
        for name,start,end in segments:
            previous=None;options=vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(ROOT/'hand_landmarker.task')),running_mode=vision.RunningMode.VIDEO,num_hands=2)
            with vision.HandLandmarker.create_from_options(options) as video_detector:
                for index in range(round(start*24)-1,round(end*24)):
                    pts=(index+1)/24;cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,im=cap.read()
                    if not ok:raise ValueError('Video decode failed')
                    path=OUT/'frames'/f'f{index}.png';cv2.imwrite(str(path),im);e,M=track(reference,im);corners=project(REFERENCE_CORNERS,M)
                    baseline=detect_global_fretting(image_detector,im,corners=corners);selected=baseline['selection']['selected'];base_hand=None if selected is None else selected['hands'][0];proposals=[]
                    if selected is not None:
                        proposals.append(dict(candidate_id='baseline_current',hands=[base_hand]))
                        anchor=np.array(base_hand['pixel_landmarks'])[[0,5,9,13,17]].mean(axis=0)
                        for padding in [.15,.3,.5]:
                            crop=hand_bounding_crop(base_hand['pixel_landmarks'],im.shape,padding=padding,minimum_size=220);x0,y0,x1,y1=crop
                            for output_side in [480,720]:
                                sx=output_side/(x1-x0);sy=output_side/(y1-y0);enlarged=cv2.resize(im[y0:y1,x0:x1],(output_side,output_side),interpolation=cv2.INTER_CUBIC)
                                transform=np.array([[sx,0,-x0*sx],[0,sy,-y0*sy],[0,0,1.]],float)
                                result=image_detector.detector.detect(image_detector.mp.Image(image_format=image_detector.mp.ImageFormat.SRGB,data=cv2.cvtColor(enlarged,cv2.COLOR_BGR2RGB)))
                                hands=serialize(result,enlarged.shape,transform);hands=[h for h in hands if np.linalg.norm(np.array(h['pixel_landmarks'])[[0,5,9,13,17]].mean(axis=0)-anchor)<70]
                                proposals.append(dict(candidate_id=f'pad{padding}_size{output_side}',crop=list(crop),source_transform=transform.tolist(),hands=hands))
                    consensus=choose_candidate(proposals,previous);chosen=consensus['selected'];consensus_hand=None if chosen is None else chosen['hands'][0]
                    if consensus_hand is not None:previous=np.array(consensus_hand['pixel_landmarks'])
                    vr=video_detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)),round(pts*1000));video_hands=serialize(vr,im.shape,np.eye(3));vrank=rank_view(video_hands,im.shape,corners=corners);video_hand=vrank['selected']
                    identity=make_frame_identity(VIDEO_ID,index,pts,im,str(path),name);board=make_board(identity,M,e,str(path));grid=build_grid(board,dict(six_side='top',anchor_y=[15.,15.],opposite_margin=[15.,15.],spacing_scale=1.,anchor_status='assumed_not_observed'))
                    branches={}
                    for method,hand in [('baseline',base_hand),('multi_crop',consensus_hand),('video_tracking',video_hand)]:
                        fingers=distributions(grid,hand);candidates=[dict(root_pc=0,quality='6',pcs=[0,4,7,9],score=1.,symbol='C6'),dict(root_pc=9,quality='m7',pcs=[0,4,7,9],score=1.,symbol='Am7')]
                        branches[method]=dict(hand=hand,fingers=fingers,root_diagnostic=assess(candidates,fingers,include_uncertain_middle=True,visual_status='unknown'))
                    records.append(dict(segment=name,frame_index=index,pts=pts,image=str(path),alignment=e,branches=branches,consensus=consensus,
                        candidates=proposals,video_role_status=vrank['status'],root_probe='Fixed C6/Am7 pair for214diagnostic only; not a chord ground truth for other times'))
            print('Completed segment',name,flush=True)
    (OUT/'result.json').write_text(json.dumps(dict(frames=records,config=dict(segments=segments,crop_padding=[.15,.3,.5],enlarged_sizes=[480,720],rotation='Native0degrees only for enlarged views; global fallback follows existing native-first policy',
        whole_hand_selection='Current-frame medoid +bounded history, relax on large palm movement',previous_positions_imputed=False,
        reference_or_audio_selection=False,model_sha256=hashlib.sha256((ROOT/'hand_landmarker.task').read_bytes()).hexdigest())),indent=2),encoding='utf-8')
    cap.release();print('Completed',len(records),'frames',flush=True)

if __name__=='__main__':main()
