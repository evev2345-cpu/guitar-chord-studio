"""Hand-only 3..12s run using actual video PTS, no APIs and no temporal imputation."""
import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from hand_frame_contract import file_sha256,frame_identity,adapt_geometry,apply_geometry_gate
from hand_fret_tracker import FretboardGeometry,analyze_result,detect_image,EDGES
from hand_quality import location_gate
from validate_chord_sequence import roi_observations

DEFAULT_OUT=Path('dataset/hand_analysis/runs/clip_003_012_20261103_v1')
FINGERS={'thumb':4,'index':8,'middle':12,'ring':16,'pinky':20}


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')


def probe(video):
    command=['ffprobe','-v','error','-select_streams','v:0','-read_intervals','0%13',
             '-show_frames','-show_streams','-show_entries',
             'frame=pts,best_effort_timestamp,pts_time,best_effort_timestamp_time:stream=time_base,start_time,r_frame_rate',
             '-of','json',str(video)]
    return json.loads(subprocess.run(command,check=True,capture_output=True,encoding='utf-8').stdout)


def draw(raw,result,quality,identity):
    canvas=raw.copy()
    for hand in result['hands']:
        color=(0,200,255) if hand['hand_index']==result['selected_hand_index'] else (130,130,130)
        points=[tuple(np.rint(l['pixel']).astype(int)) for l in hand['landmarks']]
        for a,b in EDGES:cv2.line(canvas,points[a],points[b],color,1)
    if result['selected_hand_index'] is not None:
        hand=result['hands'][result['selected_hand_index']]
        for name,index in FINGERS.items():
            q=quality[name]
            p=tuple(np.rint(hand['landmarks'][index]['pixel']).astype(int))
            color=(0,0,255) if q['decision']=='abstain' else (0,220,100)
            cv2.circle(canvas,p,6,color,2)
    cv2.putText(canvas,f"PTS {identity['frame_pts_s']:.6f}s frame {identity['frame_index']} / geometry not assumed valid",(5,18),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,255),1)
    return canvas


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--geometry-manifest',type=Path,help='JSON object with frames list of upstream same-frame records')
    args=parser.parse_args()
    if (args.output/'observations.jsonl').exists():
        raise FileExistsError('Existing run preserved; choose a new --output')
    args.output.mkdir(parents=True,exist_ok=True)
    video=next(Path('sample video').glob('*.mp4'));source_id=file_sha256(video)
    info=probe(video);time_base=info['streams'][0]['time_base'];frames=info['frames']
    write_json(args.output/'source_pts_probe.json',info)
    upstream={}
    if args.geometry_manifest:
        data=json.loads(args.geometry_manifest.read_text(encoding='utf-8'))
        upstream={f['frame_index']:f for f in data['frames']}
    # Legacy 5s manual board is only used to propose a hand near the neck, NOT to validate frets.
    reference=json.loads(Path('dataset/chord_video_review/case_0005.00_board.json').read_text())
    board=FretboardGeometry(reference['corners'],reference['frets'])
    cap=cv2.VideoCapture(str(video));previous=None;summary=[];contract=[]
    with (args.output/'observations.jsonl').open('w',encoding='utf-8') as output:
        for index,pf in enumerate(frames):
            ok,raw=cap.read()
            if not ok:raise RuntimeError('Decoded frame missing at '+str(index))
            identity=frame_identity(source_id,index,pf,time_base,raw)
            pts=identity['frame_pts_s']
            if pts<3:continue
            if pts>=12:break
            # Every frame freshly observed; previous values are used for speed diagnostics only.
            result=analyze_result(detect_image(raw,'hand_landmarker.task'),raw.shape,board)
            roi=roi_observations(raw)
            geometry=adapt_geometry(identity,upstream.get(index))
            quality={};diagnostic={}
            selected=result['selected_hand_index']
            if selected is not None:
                hand=result['hands'][selected]
                for name,tip in FINGERS.items():
                    prior=previous.get(name) if previous else None
                    q=location_gate(hand,roi,tip,previous=prior,timestamp_ms=pts*1000)
                    diagnostic[name]=q
                    quality[name]=apply_geometry_gate(q,geometry)
                previous={name:dict(pixel=q['full_pixel'],timestamp_ms=pts*1000) for name,q in diagnostic.items()}
            else:previous=None
            for hand in result['hands']:
                hand['legacy_reference_center_diagnostics']=hand.pop('candidates',[])
            record=dict(schema_version='hand_frame_evidence.v2',**identity,
                        status=result['status'],selected_hand_index=selected,hands=result['hands'],
                        roi_observations=roi,raw_location_quality=diagnostic,location_quality=quality,
                        geometry=geometry,geometry_reference_for_hand_selection=dict(
                            path='dataset/chord_video_review/case_0005.00_board.json',source_kind='manual_approximation',
                            validity='unknown',not_frame_validated=True),
                        observation_status='fresh_image_inference',reused_observation=False,
                        frame_pts_basis='ffprobe_integer_pts_times_stream_time_base',
                        contact='unknown',precise_fret_decision=None,api_calls=0)
            # Save lossless representatives at 0.5s cadence; all frames retain pixel hashes.
            if index%12==0 or not summary:
                image_path=args.output/f'frame_{index:06d}.png';cv2.imwrite(str(image_path),raw)
                record.update(image_file=str(image_path),image_file_sha256=file_sha256(image_path))
                cv2.imwrite(str(args.output/f'frame_{index:06d}_overlay.png'),draw(raw,result,quality,identity))
            output.write(json.dumps(record,allow_nan=False)+'\n')
            contract.append({k:record[k] for k in ['source_id','case_id','frame_index','frame_pts','frame_time_base','frame_pts_s','frame_pixel_sha256','image_file_sha256','image_file','image_size']})
            summary.append(dict(frame_index=index,frame_pts_s=pts,status=result['status'],
                                roi_count=len(roi),quality=diagnostic,geometry_status=geometry['status']))
            if len(summary)%48==0:print('fresh frames',len(summary),flush=True)
    cap.release()
    write_json(args.output/'frame_contract.json',dict(schema_version='hand_frame_join.v1',source_id=source_id,frames=contract))
    write_json(args.output/'summary.json',dict(source_id=source_id,source_path=str(video),start_s=3,end_s=12,
        frame_count=len(summary),statuses=dict(Counter(r['status'] for r in summary)),
        actual_pts=True,video_stream_time_base=time_base,video_stream_start_time=info['streams'][0]['start_time'],
        geometry_manifest=str(args.geometry_manifest) if args.geometry_manifest else None,
        roi_bounds_original_px=[740,155,1135,420],frames=summary,api_calls=0))
    write_json(args.output/'geometry_request.json',dict(source_id=source_id,
        frame_contract=str(args.output/'frame_contract.json'),required_fields=['source_id','frame_index','frame_pts_s','frame_pixel_sha256','geometry_validity','geometry_source_kind'],
        accepted_statuses=['valid','suspect','unknown','invalid'],
        note='Unknown until same-frame upstream validity is supplied; a manual reference is not validation'))
    print('completed',len(summary),'frames',source_id,flush=True)


if __name__=='__main__':main()
