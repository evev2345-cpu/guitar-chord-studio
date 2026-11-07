"""Source-specific provisional neck tracking + native full-frame VIDEO hands.

Calibration never reads screen chords/TAB/audio. No contact or string truth is
inferred. A manually estimated reference must match this source's decoded pixels.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from global_fretting_hand import rank_view
from improve_hand_skeleton import serialize
from virtual_string_grid import build_grid
from hand_cell_distribution import sample_projected,integrate_points
from low_string_root_prior import low_string_support,FINGER_WEIGHTS,TUNING

ROOT=Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / 'models' / 'hand_landmarker.task'
if not MODEL_PATH.exists():
    MODEL_PATH = Path(__file__).resolve().parent / 'hand_landmarker.task'


def project(points,matrix):
    return cv2.perspectiveTransform(np.asarray(points,np.float64)[:,None],np.asarray(matrix,np.float64))[:,0]


class NeckTracker:
    def __init__(self,reference,calibration):
        self.gray=cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY);self.cal=calibration
        mask=np.zeros_like(self.gray);cv2.fillConvexPoly(mask,np.asarray(calibration['texture_polygon'],np.int32),255)
        self.points=cv2.goodFeaturesToTrack(self.gray,maxCorners=180,qualityLevel=.015,minDistance=5,mask=mask)

    def track(self,image):
        fail=dict(status='unknown',reason='alignment_unavailable')
        if self.points is None:return fail,None
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        q,ok,_=cv2.calcOpticalFlowPyrLK(self.gray,gray,self.points,None,winSize=(25,25),maxLevel=4)
        if q is None:return fail,None
        back,bok,_=cv2.calcOpticalFlowPyrLK(gray,self.gray,q,None,winSize=(25,25),maxLevel=4)
        if back is None:return fail,None
        good=(ok[:,0]>0)&(bok[:,0]>0)&(np.linalg.norm(back[:,0]-self.points[:,0],axis=1)<1.5)
        if good.sum()<12:return dict(status='unknown',reason='too_few_features',tracked=int(good.sum())),None
        affine,inliers=cv2.estimateAffinePartial2D(self.points[good,0],q[good,0],method=cv2.RANSAC,ransacReprojThreshold=1.5)
        if affine is None:return fail,None
        matrix=np.vstack([affine,[0,0,1]]);keep=inliers[:,0]>0
        error=np.linalg.norm(project(self.points[good,0],matrix)-q[good,0],axis=1)
        scale=np.linalg.norm(matrix[:2,0]);corners=project(self.cal['corners'],matrix)
        within=bool((corners>=0).all() and (corners[:,0]<image.shape[1]).all() and (corners[:,1]<image.shape[0]*.68).all())
        valid=bool(keep.sum()>=12 and keep.mean()>=.6 and np.median(error[keep])<1.25 and .65<scale<1.4 and within)
        return dict(status='measured_alignment' if valid else 'unknown',inliers=int(keep.sum()),inlier_fraction=float(keep.mean()),
                    median_error_px=float(np.median(error[keep])),scale=float(scale),precise_geometry_verified=False),matrix if valid else None


def board_for(calibration,matrix,image,index,pts,source_id):
    corners=project(calibration['corners'],matrix)
    M=cv2.getPerspectiveTransform(corners.astype(np.float32),np.array([[0,0],[800,0],[800,150],[0,150]],np.float32))
    identity=dict(source_id=source_id,frame_index=index,frame_pts_s=pts,frame_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),image_size=[image.shape[1],image.shape[0]])
    frets=[]
    for f in calibration['frets']:
        ends=project(project(f['endpoints'],matrix),M)
        frets.append(dict(physical_fret_candidate=f['number'],xt=float(ends[0,0]),xb=float(ends[1,0]),source='source_specific_manual_estimate',confirmed_physical_fret_num=None))
    return dict(**identity,frame_identity=identity,corners=corners.tolist(),M=M.tolist(),M_inv=np.linalg.inv(M).tolist(),canvas_size=[800,150],frets=frets,
                geometry_validity=dict(status='provisional',exact_geometry_verified=False,contact_fret_decision_allowed=False),
                capo=dict(value=None,physical_fret_candidate=calibration.get('capo_candidate'),independently_verified=False))


def hand_evidence(grid,hand):
    fingers=[];cells={}
    for tip,name in [(8,'index'),(12,'middle'),(16,'ring'),(20,'pinky')]:
        points,valid=sample_projected(grid,hand['pixel_landmarks'][tip],12,samples=512)
        dist=integrate_points(grid,points,valid)
        dist['cells']=[c for c in dist['cells'] if c['position_mass']>0]
        fingers.append(dict(finger=name,tip_index=tip,pixel=hand['pixel_landmarks'][tip],**dist))
        for cell in dist['cells']:
            key=(cell['virtual_string_num'],cell['physical_fret_candidate'])
            cells[key]=max(cells.get(key,0),FINGER_WEIGHTS[name]*cell['position_mass'])
    pcs=np.zeros(12)
    for (string,fret),mass in cells.items():pcs[(TUNING[string]+fret)%12]+=mass
    return dict(fingers=fingers,pc_support=pcs.tolist(),low_string=low_string_support(fingers,include_uncertain_middle=True),
                supported_fingers=sum(f['assigned_mass']>=.3 for f in fingers if f['finger']!='middle'),
                total_support=float(pcs.sum()),contact='unknown',anatomical_validity='unknown',score_type='uncalibrated_location_support')


def run(video, calibration, out, start=0, end=None, progress_callback=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'observations.jsonl').exists():raise FileExistsError('Vision observations already exist; preserve original run')
    cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));source_id=hashlib.sha256(Path(video).read_bytes()).hexdigest()
    if 'fps' in calibration and abs(fps-calibration['fps'])>1e-6:raise ValueError('Calibration FPS mismatch')
    cap.set(cv2.CAP_PROP_POS_FRAMES,calibration['reference_frame']);ok,reference=cap.read()
    if not ok:raise ValueError('Reference frame decode failed')
    if hashlib.sha256(reference.tobytes()).hexdigest()!=calibration['reference_pixel_sha256']:raise ValueError('Calibration belongs to different decoded source')
    if [reference.shape[1],reference.shape[0]]!=calibration['image_size']:raise ValueError('Calibration size mismatch')
    tracker=NeckTracker(reference,calibration);cap.set(cv2.CAP_PROP_POS_FRAMES,round(start*fps))
    config=dict(six_side='top',anchor_y=[15.,15.],opposite_margin=[15.,15.],spacing_scale=1.,anchor_status='assumed_not_observed')
    reference_board=board_for(calibration,np.eye(3),reference,calibration['reference_frame'],calibration['reference_frame']/fps,source_id)
    reference_grid=build_grid(reference_board,config)
    # Fretboard-guided fretting hand search region: isolates neck from picking/strumming hand on body
    ref_c=np.asarray(calibration['corners'],float)
    c_min=ref_c.min(axis=0);c_max=ref_c.max(axis=0)
    th=float((np.linalg.norm(ref_c[0]-ref_c[3])+np.linalg.norm(ref_c[1]-ref_c[2]))/2)
    pad_x=max(70,int(th*1.0));pad_y=max(100,int(th*2.0))
    h_img,w_img=reference.shape[:2]
    x0=max(0,int(c_min[0]-pad_x));x1=min(w_img,int(c_max[0]+pad_x))
    y0=max(0,int(c_min[1]-pad_y));y1=min(h_img,int(c_max[1]+pad_y))
    crop_transform=np.array([[1.,0.,-x0],[0.,1.,-y0],[0.,0.,1.]])
    options=vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(MODEL_PATH)),running_mode=vision.RunningMode.VIDEO,num_hands=2)
    previous=None;stable=0;overlay=[];counts={};last_index=min(count,round(end*fps)) if end is not None else count
    total_frames = max(1, last_index - round(start * fps))
    with vision.HandLandmarker.create_from_options(options) as detector,(out/'observations.jsonl').open('w',encoding='utf-8') as dest:
        for index in range(round(start*fps),last_index):
            if progress_callback and (index % 30 == 0 or index == last_index - 1):
                try:
                    progress_callback(index - round(start * fps), total_frames, index / fps, count / fps)
                except Exception:
                    pass
            ok,image=cap.read()
            if not ok:raise ValueError('Decode failed at frame '+str(index))
            pts=index/fps;alignment,matrix=tracker.track(image)
            sub=image[y0:y1,x0:x1]
            result=detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(sub,cv2.COLOR_BGR2RGB)),round(pts*1000))
            hands=serialize(result,sub.shape,crop_transform);corners=project(calibration['corners'],matrix) if matrix is not None else None
            selection=rank_view(hands,image.shape,corners=corners,previous=previous if corners is not None else None)
            hand=selection['selected'] if corners is not None else None
            record=dict(frame_index=index,time_s=pts,source_id=source_id,alignment=alignment,role_status=selection['status'],geometry_status='provisional',contact='unknown',root_voicing_validated=False)
            if hand is not None:
                points=np.asarray(hand['pixel_landmarks']);step=float(np.median(np.linalg.norm(points-previous,axis=1))) if previous is not None else None
                stable=stable+1 if step is not None and step<12 else 0;previous=points
                board=board_for(calibration,matrix,image,index,pts,source_id)
                # The same measured similarity transports board and wire models;
                # normalized polygons stay fixed, only original->flat M changes.
                if not np.allclose([[f['xt'],f['xb']] for f in board['frets']],[[f['xt'],f['xb']] for f in reference_board['frets']],atol=.01):
                    raise ValueError('Tracked normalized geometry changed unexpectedly')
                grid=dict(reference_grid,**{k:board[k] for k in ['source_id','frame_index','frame_pts_s','frame_pixel_sha256','image_size','frame_identity','M','M_inv']})
                grid['grid_id']=hashlib.sha256((reference_grid['grid_id']+board['frame_pixel_sha256']).encode()).hexdigest()
                spatial=hand_evidence(grid,hand)
                usable=bool(stable>=2 and spatial['supported_fingers']>=2 and spatial['total_support']>=.5)
                record.update(status='provisional_location_only' if usable else 'insufficient_spatial_support',hand=hand,corners=corners.tolist(),
                              frame_pixel_sha256=board['frame_pixel_sha256'],M=board['M'],grid_id=grid['grid_id'],spatial=spatial,stable_frames=stable,median_hand_step_px=step)
                if index%120==0:
                    from virtual_string_grid import render_grid
                    preview,_=render_grid(image,grid)
                    for chain in [[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20]]:cv2.polylines(preview,[points[chain].astype(np.int32)],False,(255,255,0),2)
                    cv2.imwrite(str(out/f'frame_{index}.png'),preview)
            else:
                previous=None;stable=0;record['status']='no_current_visual_support'
            counts[record['status']]=counts.get(record['status'],0)+1
            dest.write(json.dumps(record,ensure_ascii=False)+'\n')
            overlay.append(dict(time_s=pts,frame_index=index,corners=record.get('corners'),hand=(record.get('hand') or {}).get('pixel_landmarks'),status=record['status']))
            if index%240==0:print('Vision',round(pts,1),'/',round(count/fps,1),counts,flush=True)
    cap.release()
    (out/'overlay.json').write_text(json.dumps(overlay),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps(dict(source_id=source_id,fps=fps,status_counts=counts,calibration=calibration,
        model_sha256=hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),mode='fretboard_roi_VIDEO',crop_roi=[x0,y0,x1,y1],anatomy_verified=False,geometry_verified=False,contact='unknown',audio_used_to_select_hand=False),indent=2),encoding='utf-8')
    print('Vision completed',counts,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--calibration',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float)
    a=p.parse_args();run(a.video,json.loads(a.calibration.read_text(encoding='utf-8')),a.output,a.start,a.end)
