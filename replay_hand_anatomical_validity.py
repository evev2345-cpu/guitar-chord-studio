"""Offline replay of reviewed frame210 lineage into immutable new fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from hand_anatomical_validity import *
from hand_fret_tracker import EDGES

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2'
ROBUST=ROOT/'dataset/integration_review/runs/robust_candidates_20261103_v2/result.json'
RAW=ROOT/'dataset/hand_analysis/runs/clip_003_012_20261103_v1/observations.jsonl'
REVIEW=ROOT/'dataset/hand_analysis/human_review_20261103/frame210_finger_identity_review.json'
OLD=ROOT/'dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4'

def write(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    frame=next(f for f in json.loads(ROBUST.read_text())['frames'] if f['frame_index']==210)
    raw=next(r for r in map(json.loads,RAW.read_text().splitlines()) if r['frame_index']==210)
    review=json.loads(REVIEW.read_text())
    baseline=frame['views'][0]
    roi=raw['roi_observations'][0]
    points=[l['pixel'] for l in roi['landmarks']]
    assert points==baseline['hands'][0]
    assert same_frame(frame,raw)
    assert all(frame[k]==review[k] for k in ('source_id','frame_index','frame_pts_s'))
    reviewed_image=ROOT/review['reviewed_image']
    assert sha(reviewed_image)==review['reviewed_image_sha256']
    identity={k:frame[k] for k in IDENTITY}
    binding=dict(**identity,review_path=str(REVIEW),review_sha256=sha(REVIEW),
        reviewed_image_sha256=sha(reviewed_image),
        lineage=dict(view_id=baseline['view_id'],bounds=baseline['bounds'],hand_index=0,skeleton_sha256=skeleton_hash(points)),
        raw_points=points,scope='one reviewed baseline ROI hand only',recovery_completed=False)
    write(OUT/'review_binding.json',binding)
    lineage={str(t):resolve_medoid(frame,t) for t in (4,8,12,16,20)}
    write(OUT/'medoid_lineage.json',lineage)
    records=[];exports=[]
    for path in sorted(OLD.glob('clip003012_f000210_*_hand_cells.json')):
        result=json.loads(path.read_text()); before=copy.deepcopy(result)
        for i,d in enumerate(result['observations']):
            o=d['observation'];t=o['landmark_index'];ln=lineage[str(t)]
            assert o['pixel']==ln['raw_points'][t]
            validity=anatomical_validity(o,ln,[t],binding)
            result['observations'][i]=apply_validity(d,validity)
        for s in result['index_segment_hypotheses']:
            ln=resolve_medoid(frame,8)
            validity=anatomical_validity(result,ln,s['landmark_indices'],binding)
            assert s['distribution']['pixel_endpoints']==[ln['raw_points'][i] for i in s['landmark_indices']]
            s['distribution']=apply_validity(s['distribution'],validity)
        result['anatomical_validity_contract']='hand_anatomical_validity.v1'
        result['upstream_result_path']=str(path);result['upstream_result_sha256']=sha(path)
        result['review_binding_path']=str(OUT/'review_binding.json')
        write(OUT/path.name,result)
        for d in result['observations']:
            exported=copy.deepcopy(d)
            exported['review_binding_path']=result['review_binding_path']
            exported['upstream_result_path']=result['upstream_result_path']
            name=path.stem.replace('_hand_cells','')+'_'+d['observation']['observation_id']+'.json'
            write(OUT/name,exported)
            exports.append(dict(path=str(OUT/name),grid_id=d['grid_id'],observation_id=d['observation']['observation_id'],anatomical_validity_status=d['anatomical_validity']['status']))
        records.append(dict(path=str(OUT/path.name),grid_id=result['grid_id'],invalid=sum(d['anatomical_validity']['status']=='invalid' for d in result['observations'])))
        for a,b in zip(before['observations'],result['observations']):
            assert a['observation']==b['observation'] and a['cells']==[{k:v for k,v in c.items() if k not in ('anatomical_fingering_evidence_allowed','anatomical_validity_status')} for c in b['cells']]
    original=cv2.imread(str(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000210.png'));assert hashlib.sha256(original.tobytes()).hexdigest()==frame['frame_pixel_sha256']
    cv2.imwrite(str(OUT/'original.png'),original)
    panels=[];alternatives=[]
    for view in frame['views']:
        if len(view['hands'])!=1:continue
        canvas=original.copy();hand=view['hands'][0]
        for a,b in EDGES:
            cv2.line(canvas,tuple(np.rint(hand[a]).astype(int)),tuple(np.rint(hand[b]).astype(int)),(0,220,0),2)
        crop=cv2.resize(canvas[155:420,740:1135],None,fx=2,fy=2)
        name=f"view_{view['view_id']}_skeleton.png";cv2.imwrite(str(OUT/name),crop);panels.append(crop)
        alternatives.append(dict(view_id=view['view_id'],skeleton_sha256=skeleton_hash(hand),path=str(OUT/name),
            status='reviewed_chain_error' if view['view_id']==0 else 'unreviewed_alternative',raw_points=hand))
    cv2.imwrite(str(OUT/'whole_hand_comparison.png'),np.vstack([np.hstack(panels[:2]),np.hstack(panels[2:])]))
    write(OUT/'alternative_whole_hands.json',alternatives)
    write(OUT/'downstream_fixtures.json',dict(schema_version='hand_anatomical_fixture_index.v1',fixtures=exports,
        invalid_count=sum(e['anatomical_validity_status']=='invalid' for e in exports),
        unknown_count=sum(e['anatomical_validity_status']=='unknown' for e in exports),
        contract_document=str(ROOT/'docs/HAND_ANATOMICAL_VALIDITY_SCHEMA_2026-11-04.md')))
    write(OUT/'manifest.json',dict(schema_version='hand_anatomical_replay.v1',**identity,records=records,
        api_calls=0,new_inferences=0,coordinate_changes=0,relabeling=False,recovery_completed=False,
        inputs={str(p):sha(p) for p in [ROBUST,RAW,REVIEW,reviewed_image]},
        invalid_point_distributions=sum(r['invalid'] for r in records),other_crops_invalidated=False))
    print(OUT);print('6 grids, 18 invalid point distributions, 0 coordinate changes')
if __name__=='__main__':main()

