"""Same-frame string integration and independently detected short-sequence review.

Existing string_geometry/string_detector are reused, never reimplemented.
Every sequence frame receives fresh IMAGE inference; no carry-forward coordinates.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from chord_photo_validation import analyze, string_interface
from hand_fret_tracker import FretboardGeometry, analyze_result, detect_image, render
from hand_quality import location_gate, reviewed_gate
from string_geometry import analyze_saved_board

OUT = Path('dataset/chord_sequence_review')
ROI = [740, 155, 1135, 420]  # Valid only for this 1280x720 fixed-camera tutorial.


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')


def roi_observations(raw):
    x0, y0, x1, y1 = ROI
    result = detect_image(raw[y0:y1, x0:x1], 'hand_landmarker.task')
    return [dict(hand_index=i, landmarks=[dict(index=j, pixel=[lm.x*(x1-x0)+x0, lm.y*(y1-y0)+y0])
                                        for j, lm in enumerate(hand)])
            for i, hand in enumerate(result.hand_landmarks)]


def combined(raw, track, strings, quality, prefix):
    board = FretboardGeometry(track['corners'], track['frets'])
    display = copy.deepcopy(track)
    for hand in display['hands']:
        hand['candidates']=[]  # Do not display legacy single-center fret labels as decisions.
    original, flat = render(raw, board, display)
    # Preserve visibility evidence: supported intervals solid, unsupported spans dashed.
    for line in strings['strings']:
        for canvas, inverse in ((flat, None), (original, board.M_inv)):
            for x in range(0, board.width-1, 8):
                observed = line['source']=='observed' and any(a<=x<=b for a,b in line.get('observed_intervals', []))
                if not observed and (x//8)%2:
                    continue
                coords=np.array([[x,line['m']*x+line['b']], [min(x+8,board.width-1),line['m']*min(x+8,board.width-1)+line['b']]])
                if inverse is not None:
                    coords=cv2.perspectiveTransform(coords[:,None],inverse)[:,0]
                color=(0,220,220) if observed else (150,80,150)
                cv2.line(canvas,tuple(np.rint(coords[0]).astype(int)),tuple(np.rint(coords[1]).astype(int)),color,1)
        identity = str(line['string_num']) if line.get('string_num') is not None else line.get('line_id','?')
        cv2.putText(flat, identity, (680,round(line['m']*680+line['b'])), cv2.FONT_HERSHEY_SIMPLEX,.3,(255,255,0),1)
    from fingertip_probability import circle_distribution
    selected=track['selected_hand_index']
    if selected is not None:
        hand=track['hands'][selected]
        for name,index in [('thumb',4),('index',8),('middle',12),('ring',16),('pinky',20)]:
            gate=quality[name]
            color=(0,0,255) if gate['decision']=='abstain' else (0,230,100)
            point=hand['landmarks'][index]['pixel']
            distribution=circle_distribution(point,6,board.M)
            cv2.circle(original,tuple(np.rint(point).astype(int)),6,color,2)
            cv2.putText(original,name+':'+gate['decision'],tuple(np.rint(point).astype(int)),cv2.FONT_HERSHEY_SIMPLEX,.3,color,1)
            if distribution['status']=='ok':
                cv2.polylines(flat,[np.rint(np.clip(distribution['exact_boundary'],-100000,100000)).astype(np.int32)],True,color,2)
            if gate['secondary_pixel'] is not None:
                cv2.drawMarker(original,tuple(np.rint(gate['secondary_pixel']).astype(int)),(255,0,255),cv2.MARKER_CROSS,12,1)
    cv2.putText(original,'red=abstain; magenta cross=ROI observation; strings=external',(5,40),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,255),1)
    cv2.imwrite(str(prefix)+'_original.png',original)
    cv2.imwrite(str(prefix)+'_flat.png',flat)
    tile=np.full((640,800,3),235,np.uint8)
    cv2.putText(tile,prefix.name,(5,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1)
    tile[30:480]=cv2.resize(original,(800,450));tile[485:635]=flat
    cv2.imwrite(str(prefix)+'_review.png',tile)


def process_stills():
    reports=[]
    reviews=json.loads(Path('dataset/chord_video_review/visual_point_review.json').read_text())
    for stamp in ['0005.00','0194.86','0206.03','0217.20']:
        stem='case_'+stamp
        track=json.loads((Path('dataset/chord_video_review')/(stem+'_tracking.json')).read_text())
        cached=json.loads(Path(track['board_result']).read_text())
        raw=cv2.imread(track['image']); track['corners']=cached['corners']
        latest=Path('dataset/string_review')/(stem+'_high.json')
        if latest.exists():
            payload=json.loads(latest.read_text())
            string_origin='existing_string_owner_output'
        else:
            payload,*_=analyze_saved_board(raw,cached,source_id=stem)
            string_origin='existing_string_detector_local_execution'
        strings=string_interface(payload,track)
        roi=roi_observations(raw)
        selected=track['selected_hand_index']; hand=track['hands'][selected] if selected is not None else None
        quality={name:location_gate(hand,roi,index) for name,index in [('thumb',4),('index',8),('middle',12),('ring',16),('pinky',20)]} if hand else {}
        if hand:
            tip_names={4:'thumb',8:'index',12:'middle',16:'ring',20:'pinky'}
            for review in reviews:
                if review['case_id']!=stem+'_tracking' or review.get('review_status')!='reviewed':
                    continue
                for label in review['landmarks']:
                    if label.get('visibility')=='visible' and label['index'] in tip_names:
                        finger_name=tip_names[label['index']]
                        quality[finger_name]=reviewed_gate(quality[finger_name],label['pixel'])
        result=analyze(track,[6.],payload)
        for finger in result['fingers']:
            finger['location_quality']=quality[finger['finger']]
            finger['decision']=quality[finger['finger']]['decision']
        for detected_hand in result['hands']:
            detected_hand['legacy_center_point_diagnostics']=detected_hand.pop('candidates',[])
        result.update(corners=cached['corners'],geometry_source=cached['source'],
                      geometry_source_kind='manual_approximation',
                      geometry_validation_status='agent_manual_approximation_not_independent',
                      strings_origin=string_origin,roi_observations=roi,location_quality=quality,
                      contact='unknown',api_calls=0,source_tracking=track['image'])
        write_json(OUT/(stem+'_integrated.json'),result)
        if hand:combined(raw,track,strings,quality,OUT/stem)
        reports.append(dict(case=stem,strings=len(strings['strings']),
                            unresolved_numbers=len(strings.get('unresolved',[])),
                            identity=strings['identity_verification'],quality=quality))
    write_json(OUT/'stills_summary.json',reports)


def sequence():
    video=next(Path('sample video').glob('*.mp4'))
    cap=cv2.VideoCapture(str(video)); fps=cap.get(cv2.CAP_PROP_FPS)
    base=json.loads(Path('dataset/chord_video_review/case_0217.20_board.json').read_text())
    base_matrix=FretboardGeometry(base['corners'],base['frets']).M
    previous=None; rows=[];last_gray=None;last_anchor=None
    # 49 frames / 2 sec, includes the frozen error scene; independent inference at 24fps.
    for frame_index in range(5189,5238):
        cap.set(cv2.CAP_PROP_POS_FRAMES,frame_index);ok,raw=cap.read()
        if not ok:
            rows.append(dict(frame_index=frame_index,status='decode_failed',hands=[],reused_observation=False))
            previous=None;last_gray=None;continue
        t=frame_index/fps*1000
        stem=f'frame_{frame_index}'
        image_path=OUT/(stem+'.png'); cv2.imwrite(str(image_path),raw)
        board=FretboardGeometry(base['corners'],base['frets'])
        # A nearby manual fixture is a reference, not a new board detection.
        # Estimate incremental camera/neck motion using only unoccluded neck anchors.
        gray=cv2.cvtColor(raw,cv2.COLOR_BGR2GRAY)
        motion=None
        if last_gray is not None and last_anchor is not None:
            nxt,st,err=cv2.calcOpticalFlowPyrLK(last_gray,gray,last_anchor,None)
            valid=st.ravel().astype(bool) if st is not None else np.zeros(len(last_anchor),bool)
            if nxt is not None and valid.sum()>=6:
                motion=float(np.median(np.linalg.norm(nxt[valid]-last_anchor[valid],axis=2)))
        mask=np.zeros_like(gray);mask[208:280,440:710]=255
        anchors=cv2.goodFeaturesToTrack(gray,50,.02,6,mask=mask)
        result=analyze_result(detect_image(raw,'hand_landmarker.task'),raw.shape,board)
        result.update(image=str(image_path),corners=base['corners'],frets=base['frets'],
                      image_size=[1280,720],canvas_size=[800,150],M=board.M.tolist(),M_inv=board.M_inv.tolist(),
                      board_result='dataset/chord_video_review/case_0217.20_board.json')
        roi=roi_observations(raw)
        quality={}; selected=result['selected_hand_index']
        if selected is not None:
            hand=result['hands'][selected]
            for name,index in [('thumb',4),('index',8),('middle',12),('ring',16),('pinky',20)]:
                prior=previous.get(name) if previous else None
                quality[name]=location_gate(hand,roi,index,previous=prior,timestamp_ms=t)
            wrist=np.array(hand['landmarks'][0]['pixel'])
            if previous and np.linalg.norm(wrist-previous['wrist'])>50:
                for gate in quality.values():
                    gate['decision']='abstain';gate['reasons'].append('hand_identity_discontinuity')
            previous={name:dict(pixel=gate['full_pixel'],timestamp_ms=t) for name,gate in quality.items()}
            previous['wrist']=wrist
        else:
            previous=None
        geometry_reasons=['manual_reference_not_revalidated_per_frame']
        if motion is None or motion>2:
            geometry_reasons.append('anchor_motion_unavailable' if motion is None else 'board_motion')
        # Sequence cannot certify fret decisions from a reused manual board reference.
        for gate in quality.values():
            gate['decision']='abstain'; gate['reasons']+=geometry_reasons
        record=dict(frame_index=frame_index,timestamp_ms=t,status=result['status'],
                    observation='fresh_mediapipe_image_inference',reused_observation=False,
                    hands=result['hands'],roi_observations=roi,location_quality=quality,
                    geometry_source='manual_reference_only',geometry_reference=base['source'],
                    geometry_source_kind='manual_approximation',
                    geometry_status='unvalidated_per_frame',anchor_displacement_px=motion,
                    physical_fret_decision=None,contact='unknown',api_calls=0)
        write_json(OUT/(stem+'.json'),record)
        rows.append(dict(frame_index=frame_index,timestamp_ms=t,status=result['status'],
                         hand_count=len(result['hands']),roi_count=len(roi),
                         index_quality=quality.get('index'),anchor_displacement_px=motion,
                         reused_observation=False))
        if frame_index in [5189,5201,5213,5225,5237]:
            payload,*_=analyze_saved_board(raw,base,source_id=stem)
            strings=string_interface(payload,result)
            write_json(OUT/(stem+'_strings.json'),strings)
            if selected is not None:combined(raw,result,strings,quality,OUT/stem)
        last_gray,last_anchor=gray,anchors
    cap.release()
    write_json(OUT/'sequence_summary.json',dict(video=str(video),fps=fps,frames=rows,
        mode='independent detections, no persistent IDs or smoothing',api_calls=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sequence',action='store_true')
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    process_stills()
    if args.sequence:sequence()
