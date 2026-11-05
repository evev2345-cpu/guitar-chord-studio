"""Offline 3-12s review: true PTS, manual geometry, motion evidence, strings."""
import argparse
import json
import subprocess
from pathlib import Path
import cv2
import numpy as np
from fretboard_frame_identity import sha256_file,make_frame_identity,attach_frame_identity
from string_geometry import analyze_saved_board
from string_detector import render_strings

ROOT=Path(__file__).resolve().parent
DEFAULT_OUT=ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1'
REFERENCE_CORNERS=np.array([[1114.,208.],[430.,204.],[430.,286.],[1114.,275.]],np.float64)
REFERENCE_INDEX=120
# Explicit independent visual count from nut. The old 2..7 labels were shifted.
PHYSICAL_CANDIDATES={1:[1057,1057],2:[1003,1005],3:[953,956],4:[906,910],5:[863,867],6:[822,826]}


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def project(points,matrix):
    return cv2.perspectiveTransform(np.asarray(points,np.float64)[:,None],np.asarray(matrix,np.float64))[:,0]


def get_pts(video,out):
    target=out/'video_frame_pts.json'
    if target.exists():return json.loads(target.read_text(encoding='utf-8'))['frames']
    args=['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries',
          'frame=pts,pts_time,best_effort_timestamp_time,pkt_dts_time,key_frame','-of','json',str(video)]
    data=json.loads(subprocess.run(args,capture_output=True,text=True,encoding='utf-8',check=True).stdout)
    write(target,data)
    return data['frames']


def track(reference,current):
    # Texture on the body-side neck is measured, not fingertips. Alignment alone
    # never certifies an exact fret or hand/string contact.
    a=cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY);b=cv2.cvtColor(current,cv2.COLOR_BGR2GRAY)
    mask=np.zeros_like(a);mask[207:280,500:830]=255
    points=cv2.goodFeaturesToTrack(a,maxCorners=160,qualityLevel=.03,minDistance=6,mask=mask)
    if points is None:return dict(status='unknown',reason='no_reference_features'),np.eye(3)
    moved,valid,_=cv2.calcOpticalFlowPyrLK(a,b,points,None,winSize=(21,21),maxLevel=3)
    back,back_valid,_=cv2.calcOpticalFlowPyrLK(b,a,moved,None,winSize=(21,21),maxLevel=3)
    good=(valid[:,0]>0)&(back_valid[:,0]>0)&(np.linalg.norm(points[:,0]-back[:,0],axis=1)<1)
    if int(good.sum())<12:return dict(status='unknown',reason='too_few_consistent_features',tracked=int(good.sum())),np.eye(3)
    affine,inliers=cv2.estimateAffinePartial2D(points[good,0],moved[good,0],method=cv2.RANSAC,ransacReprojThreshold=1.5)
    if affine is None:return dict(status='unknown',reason='transform_not_found'),np.eye(3)
    matrix=np.vstack([affine,[0.,0.,1.]])
    errors=np.linalg.norm(project(points[good,0],matrix)-moved[good,0],axis=1)
    keep=inliers[:,0]>0
    corners=project(REFERENCE_CORNERS,matrix)
    shift=np.linalg.norm(corners-REFERENCE_CORNERS,axis=1)
    status='valid' if keep.sum()>=12 and keep.mean()>=.6 and float(np.median(errors[keep]))<1 else 'suspect'
    return dict(status=status,method='LK_forward_backward_RANSAC_similarity_on_neck_ROI',
        reference_frame_index=REFERENCE_INDEX,tracked=int(good.sum()),inliers=int(keep.sum()),
        inlier_fraction=float(keep.mean()),median_inlier_error_px=float(np.median(errors[keep])),
        maximum_corner_shift_px=float(shift.max()),median_corner_shift_px=float(np.median(shift)),
        note='Texture alignment only; not independent corner/fret ground truth'),matrix


def make_board(identity,affine,alignment,image):
    corners=project(REFERENCE_CORNERS,affine)
    target=np.array([[0,0],[800,0],[800,150],[0,150]],np.float32)
    M=cv2.getPerspectiveTransform(corners.astype(np.float32),target)
    frets=[]
    original_nut=[[1114.,208.],[1114.,275.]]
    for number,endpoints in [(0,original_nut)]+[(n,[[x1,210.],[x2,273.]]) for n,(x1,x2) in PHYSICAL_CANDIDATES.items()]:
        native=project(endpoints,affine);flat=project(native,M)
        m=float((flat[1,0]-flat[0,0])/(flat[1,1]-flat[0,1]));intercept=float(flat[0,0]-m*flat[0,1])
        frets.append(dict(fret_num=number,physical_fret_candidate=number,confirmed_physical_fret_num=None,
            relative_fret=None,relative_fret_candidate=number-1 if number>=1 else None,
            relative_fret_status='unknown_pending_independent_capo_verification',
            source='manual_estimate',numbering_status='agent_visual_provisional',
            detection_method='manual_reference_frame120_then_ROI_similarity_transfer',
            original_endpoints=native.tolist(),reference_endpoints=endpoints,
            m=m,b=intercept,xt=intercept,xb=m*150+intercept,
            legacy_fret_num=number+1 if number>=1 else 0))
    capo_polygon=project([[1069,201],[1082,201],[1082,287],[1069,287]],affine)
    status='unknown' if alignment['status']=='unknown' else 'suspect'
    validity=dict(status=status,roi_alignment_status=alignment['status'],
        exact_geometry_verified=False,contact_fret_decision_allowed=False,
        reasons=['manual fixture without independent per-frame corner reference',
                 'body end is a review ROI, not verified final fret wire',
                 'physical fret numbers and capo remain visual provisional candidates'],alignment=alignment)
    return dict(frame_identity=identity,**identity,raw_image=str(image),corners=corners.tolist(),
        canvas_size=[800,150],M=M.tolist(),M_inv=np.linalg.inv(M).tolist(),frets=frets,
        source='agent_manual_visual_approximation_with_texture_alignment',
        physical_order='low_e_top',geometry_validity=validity,
        boundary_definitions=dict(nut='original nut near reference x1114; provisional',
                                  body='manual_ROI_endpoint_not_verified_last_fret'),
        capo=dict(value=None,status='unknown',physical_fret_candidate=1,
                  candidate_source='agent_visual_clamp_in_first_fret_space_not_tutorial_text',
                  independently_verified=False,original_polygon=capo_polygon.tolist(),is_nut=False,is_metal_fret_wire=False),
        source_metadata=identity,api_calls=0)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT_OUT)
    args=parser.parse_args();out=args.output
    if (out/'manifest.json').exists():raise SystemExit('Run exists; choose another output to preserve prior artifacts')
    out.mkdir(parents=True,exist_ok=True);(out/'frames').mkdir(exist_ok=True)
    video=next((ROOT/'sample video').glob('*.mp4'));source_id=sha256_file(video)
    if source_id!='283220036613f22a618aaaad2574df638085772dde16eec05c7e56caccd1da2f':
        raise ValueError('This manual reference belongs to a different video; refuse reuse')
    pts=get_pts(video,out)
    indices=[i for i,p in enumerate(pts) if 3<=float(p['pts_time'])<12]
    boundary=min(range(len(pts)),key=lambda i:abs(float(pts[i]['pts_time'])-12))
    representative={indices[0],indices[-1],boundary,REFERENCE_INDEX}
    for t in [3.5,4.5,6.,7.5,9.,10.5]:
        representative.add(min(indices,key=lambda i:abs(float(pts[i]['pts_time'])-t)))
    cap=cv2.VideoCapture(str(video));reference=None
    for i in range(REFERENCE_INDEX+1):
        ok,frame=cap.read()
        if not ok:raise RuntimeError('Reference decode failed')
    reference=frame.copy();cap.release()
    cap=cv2.VideoCapture(str(video));motion=[]
    for i in range(boundary+1):
        ok,frame=cap.read()
        if not ok:raise RuntimeError('Decode failed before interval end')
        if i not in indices and i!=boundary:continue
        evidence,affine=track(reference,frame)
        motion.append(dict(frame_index=i,frame_pts_s=float(pts[i]['pts_time']),evidence=evidence,affine=affine.tolist()))
    cap.release()
    # Movement moments chosen from measured neck ROI displacement, not scene labels.
    accepted=[]
    for record in sorted(motion,key=lambda r:r['evidence'].get('maximum_corner_shift_px',0),reverse=True):
        if record['frame_index'] not in indices:continue
        if all(abs(record['frame_pts_s']-r['frame_pts_s'])>.5 for r in accepted):
            accepted.append(record);representative.add(record['frame_index'])
        if len(accepted)>=3:break
    write(out/'motion_evidence.json',motion)
    lookup={r['frame_index']:r for r in motion}
    cap=cv2.VideoCapture(str(video));records=[];panels=[]
    for i in range(boundary+1):
        ok,frame=cap.read()
        if i not in representative:continue
        record=lookup[i];pts_s=float(pts[i]['pts_time'])
        case_id=f'clip003012_f{i:06d}'
        image=out/'frames'/f'{case_id}.png';cv2.imwrite(str(image),frame)
        identity=make_frame_identity(source_id,i,pts_s,frame,image,case_id)
        board=make_board(identity,np.asarray(record['affine']),record['evidence'],image.resolve())
        write(out/'frames'/f'{case_id}_board.json',board)
        strings,flat,det,_,inv=analyze_saved_board(frame,board,source_id=case_id)
        # A per-frame partial set cannot inherit physical identities from a
        # different frame. Keep all physical numbering provisional/unknown.
        for line in strings['strings']:
            line['string_num']=None;line['number_source']='unknown_pending_same_frame_independent_reference'
        strings['numbering_status']='unresolved'
        strings['unresolved']=[dict(string_num=n,source='unresolved',geometry=None,reason='physical identity not independently established') for n in range(1,7)]
        strings['geometry_validity']=board['geometry_validity'];strings['capo']=board['capo']
        write(out/'frames'/f'{case_id}_strings.json',strings)
        flatvis,rawvis=render_strings(flat,frame,inv,strings)
        cv2.polylines(rawvis,[np.round(board['corners']).astype(int)],True,(255,150,0),1)
        cv2.polylines(rawvis,[np.round(board['capo']['original_polygon']).astype(int)],True,(0,150,255),1)
        for f in board['frets']:
            a,b=np.round(f['original_endpoints']).astype(int)
            cv2.line(rawvis,tuple(a),tuple(b),(255,100,255),1)
        cv2.imwrite(str(out/'frames'/f'{case_id}_overlay.png'),rawvis)
        cv2.imwrite(str(out/'frames'/f'{case_id}_flat.png'),flatvis)
        tile=np.full((195,820,3),25,np.uint8)
        cv2.putText(tile,f"{case_id} PTS={pts_s:.6f} geometry={board['geometry_validity']['status']} lines={len(strings['strings'])}",(7,23),cv2.FONT_HERSHEY_SIMPLEX,.43,(255,255,255),1)
        tile[35:185,10:810]=flatvis;panels.append(tile)
        records.append(dict(**identity,in_primary_interval=i in indices,
            selection_reasons=[name for name,condition in [('representative',i in representative),('measured_motion_peak',any(r['frame_index']==i for r in accepted)),('end_boundary',i==boundary)] if condition],
            geometry_validity=board['geometry_validity'],observed_line_candidates=len(strings['strings']),
            physical_string_numbering='unknown',board_json=str((out/'frames'/f'{case_id}_board.json').resolve()),
            strings_json=str((out/'frames'/f'{case_id}_strings.json').resolve()),overlay=str((out/'frames'/f'{case_id}_overlay.png').resolve())))
        print(case_id,pts_s,record['evidence']['status'],record['evidence'].get('maximum_corner_shift_px'),len(strings['strings']),flush=True)
    cap.release()
    for page,start in enumerate(range(0,len(panels),4),1):cv2.imwrite(str(out/f'overview_{page}.jpg'),np.vstack(panels[start:start+4]))
    manifest=dict(schema_version='guitar_fretboard_review.v1',source_id=source_id,source_path=str(video.resolve()),
        interval=dict(start_pts_s=3,end_pts_s=12,end_exclusive=True),decoded_interval_frames=len(indices),
        decoded_video_frame_count=len(pts),frames=records,api_calls=0,
        geometry_policy='manual+ROI alignment; exact contact/fret decisions forbidden until independent review',
        observed_or_estimated='observed pixels/texture/string support; estimated manual geometry; unverified physical IDs')
    write(out/'manifest.json',manifest)
    write(out/'same_frame_fixture.json',dict(source_id=source_id,frames=records,
        join_keys=['source_id','frame_index','frame_pts_s','frame_pixel_sha256'],
        decoding='OpenCV BGR; use supplied lossless PNG to match pixels exactly',api_calls=0))
    print('OUT',out.resolve())


if __name__=='__main__':main()
