"""Join immutable hand observations to delivered upstream board/string fixtures."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace as NS
import cv2
import numpy as np

from hand_frame_contract import adapt_geometry,apply_geometry_gate,file_sha256
from hand_fret_tracker import FretboardGeometry,analyze_result
from chord_photo_validation import analyze,string_interface
from validate_chord_sequence import combined
from run_hand_common_clip import DEFAULT_OUT,write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--upstream',type=Path,default=Path('dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames'))
    args=parser.parse_args()
    observations={r['frame_index']:r for r in map(json.loads,(args.run/'observations.jsonl').read_text().splitlines())}
    out=args.run/'upstream_join';out.mkdir(exist_ok=True)
    results=[];pending=[]
    for path in sorted(args.upstream.glob('*_board.json')):
        upstream=json.loads(path.read_text());index=upstream['frame_index']
        if index not in observations:continue  # [3,12) excludes upstream's 12s boundary inspection.
        obs=observations[index];geometry=adapt_geometry(obs,upstream)
        raw=cv2.imread(upstream['image_file'])
        strings_path=path.with_name(path.name.replace('_board.json','_strings.json'))
        if not strings_path.exists():
            pending.append(dict(frame_index=index,reason='same_frame_string_evidence_not_provided',board_path=str(path)))
            strings=None
        else:
            strings=json.loads(strings_path.read_text())
            adapt_geometry(obs,strings)  # Same source/index/PTS/pixels, not merely equal M.
        board=FretboardGeometry(upstream['corners'],upstream['frets'])
        # Reproject saved fresh observations into SAME-FRAME upstream geometry, no new inference.
        detection=NS(hand_landmarks=[[NS(x=l['normalized'][0],y=l['normalized'][1],z=l['normalized'][2]) for l in h['landmarks']] for h in obs['hands']],
                     handedness=[[NS(category_name=h['handedness_raw'],score=h['handedness_score'])] for h in obs['hands']])
        track=analyze_result(detection,raw.shape,board)
        track.update(image=upstream['image_file'],board_result=str(path),image_size=upstream['image_size'],
                     canvas_size=upstream['canvas_size'],M=upstream['M'],M_inv=upstream['M_inv'],
                     corners=upstream['corners'],frets=upstream['frets'])
        joined_strings=string_interface(strings,track)
        quality={}
        if track['selected_hand_index'] is not None:
            if track['selected_hand_index']!=obs['selected_hand_index']:
                from hand_quality import location_gate
                for name,tip in {'thumb':4,'index':8,'middle':12,'ring':16,'pinky':20}.items():
                    q=location_gate(track['hands'][track['selected_hand_index']],obs['roi_observations'],tip)
                    q['decision']='abstain';q['reasons'].append('hand_selection_changed_after_geometry_join')
                    quality[name]=apply_geometry_gate(q,geometry)
            else:quality={name:apply_geometry_gate(q,geometry) for name,q in obs['raw_location_quality'].items()}
        candidates=analyze(track,[6.],strings)
        # Never present provisional upstream wire numbers as confirmed physical identity.
        for finger in candidates['fingers']:
            for entry in finger['sensitivity']:
                for cell in entry['candidates']:
                    cell['physical_fret_candidate']=cell.pop('fret_num')
                    cell['confirmed_physical_fret_num']=None
                    cell['capo_relative_fret']=None
                    cell['numbering_status']='upstream_provisional'
            finger['location_quality']=quality[finger['finger']]
            finger['decision']='abstain' if not geometry['contact_fret_decision_allowed'] else quality[finger['finger']]['decision']
        result=dict(source_id=obs['source_id'],frame_index=index,frame_pts_s=obs['frame_pts_s'],
                    frame_pixel_sha256=obs['frame_pixel_sha256'],case_id=upstream['case_id'],
                    geometry=geometry,location_quality=quality,candidates=candidates,
                    status=track['status'],raw_hand_observation_source=str(args.run/'observations.jsonl'),
                    observation_reuse='same_frame_cached_observation_not_temporal_imputation',
                    reused_previous_frame_observation=False,strings_identity_verification=joined_strings.get('identity_verification','not_provided'),
                    upstream_board_path=str(path),upstream_board_sha256=file_sha256(path),
                    upstream_strings_path=str(strings_path) if strings is not None else None,upstream_strings_sha256=file_sha256(strings_path) if strings is not None else None,
                    contact='unknown',precise_fret_decision=None)
        write_json(out/f'frame_{index:06d}_joined.json',result)
        if quality and strings is not None:combined(raw,track,joined_strings,quality,out/f'frame_{index:06d}')
        results.append(dict(frame_index=index,frame_pts_s=obs['frame_pts_s'],geometry_status=geometry['status'],
            roi_alignment_status=geometry['upstream_validity'].get('roi_alignment_status'),
            contact_fret_decision_allowed=geometry['contact_fret_decision_allowed'],
            source_kind=geometry['source_kind'],status=track['status'],strings=len(strings['strings']) if strings is not None else None,
            joined_json=str(out/f'frame_{index:06d}_joined.json')))
    write_json(out/'manifest.json',dict(source_id=next(iter(observations.values()))['source_id'],
        upstream=str(args.upstream),matched_frames=len(results),frames=results,pending_upstream=pending,api_calls=0))
    with (args.run/'joined_observations.jsonl').open('w',encoding='utf-8') as stream:
        lookup={r['frame_index']:r for r in results}
        for index,obs in observations.items():
            final=dict(obs)
            if index in lookup:
                joined=json.loads(Path(lookup[index]['joined_json']).read_text())
                final.update(geometry=joined['geometry'],location_quality=joined['location_quality'],
                             same_frame_upstream_join=lookup[index]['joined_json'],
                             hands=joined['candidates']['hands'],
                             selected_hand_index=joined['candidates']['selected_hand_index'],
                             projection_basis='same_frame_upstream_geometry',
                             candidate_evidence=joined['candidates']['fingers'])
            stream.write(json.dumps(final,allow_nan=False)+'\n')
    print('joined',len(results),'same-frame upstream fixtures')


if __name__=='__main__':main()
