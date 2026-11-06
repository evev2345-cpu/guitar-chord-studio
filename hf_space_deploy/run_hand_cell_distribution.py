"""Replay real A-grid and saved robust hand evidence into B-owned artifacts."""
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from hand_cell_distribution import cell_distribution,segment_distribution,points_in_polygon
from virtual_string_grid import assert_grid_compatible

OUT=Path('dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4')
GRID_ROOT=Path('dataset/virtual_string_grid/runs/clip_003_012_20261103_v2')
ROBUST=Path('dataset/integration_review/runs/robust_candidates_20261103_v2/result.json')
RAW=Path('dataset/hand_analysis/runs/clip_003_012_20261103_v1/observations.jsonl')
NAMES={4:'thumb',8:'index',12:'middle',16:'ring',20:'pinky'}


def write(path,data):
    path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')


def observations_for_frame(raw,robust):
    identity={k:robust[k] for k in ['source_id','frame_index','frame_pts_s','frame_pixel_sha256']}
    observations=[];segments=[]
    if raw['selected_hand_index']is not None:
        hand=raw['hands'][raw['selected_hand_index']]
        for tip,name in NAMES.items():
            evidence=copy.deepcopy(robust['tip_decisions'][str(tip)])
            observations.append(dict(**identity,observation_id='full_'+name,finger=name,landmark_index=tip,
                pixel=hand['landmarks'][tip]['pixel'],branch='full_observation',evidence=evidence,
                coordinate_system='original_pixels',
                raw_position_not_replaced=True))
        for a,b in [(5,6),(6,7),(7,8)]:
            segments.append(dict(**identity,segment_id=f'full_index_{a}_{b}',branch='full_observation',landmark_indices=[a,b],
                endpoints=[hand['landmarks'][a]['pixel'],hand['landmarks'][b]['pixel']],
                evidence=copy.deepcopy(robust['tip_decisions']['8'])))
    for tip,name in NAMES.items():
        evidence=robust['tip_decisions'][str(tip)]
        if evidence.get('selected_pixel')is not None:
            observations.append(dict(**identity,observation_id='crop_medoid_'+name,finger=name,landmark_index=tip,
                pixel=evidence['selected_pixel'],branch='crop_medoid_actual_observation',evidence=copy.deepcopy(evidence),
                coordinate_system='original_pixels',
                raw_position_not_replaced=True))
    # For the segment, preserve one actual whole-hand crop, not a chimera of tip medoids.
    index_evidence=robust['tip_decisions']['8'];view_index=index_evidence.get('medoid_view_index')
    if view_index is not None:
        valid_views=[view for view in robust['views']if len(view['hands'])==1]
        view=valid_views[view_index]
        if len(view['hands'])==1:
            hand=view['hands'][0]
            for a,b in [(5,6),(6,7),(7,8)]:
                segments.append(dict(**identity,segment_id=f'crop_index_{a}_{b}',branch='one_actual_crop_hand',
                    view_id=view['view_id'],landmark_indices=[a,b],endpoints=[hand[a],hand[b]],evidence=copy.deepcopy(index_evidence)))
    return observations,segments


def spatial_cells(grid,pixel):
    point=cv2.perspectiveTransform(np.array(pixel,float).reshape(1,1,2),np.array(grid['M']))[0,0]
    width,height=grid['canvas_size']
    inside=bool(0<=point[0]<width and 0<=point[1]<height)
    return dict(flat_pixel=point.tolist(),inside_board=inside,
                cell_ids=[c['cell_id']for c in grid['cells']if inside and points_in_polygon(point[None],c['polygon'])[0]])


def render(grid,result,raw,out,stem,review=None):
    width,height=grid['canvas_size'];matrix=np.array(grid['M']);inverse=np.array(grid['M_inv'])
    flat=cv2.warpPerspective(raw,matrix,(width,height));original=raw.copy()
    selected=next((o for o in result['observations']if o['observation']['observation_id']=='full_index'),None)
    if selected is None:selected=next((o for o in result['observations']if o['observation']['observation_id']=='crop_medoid_index'),None)
    masses={c['cell_id']:c['position_mass']for c in selected['cells']} if selected else {}
    for cell in grid['cells']:
        polygon=np.array(cell['polygon']);mass=masses.get(cell['cell_id'],0.)
        if mass:
            mask=np.zeros((height,width),np.uint8);cv2.fillConvexPoly(mask,np.rint(polygon).astype(int),255)
            alpha=min(.8,.15+.65*mass)
            flat[mask>0]=np.rint(flat[mask>0]*(1-alpha)+np.array([0,0,255])*alpha).astype(np.uint8)
        cv2.polylines(flat,[np.rint(polygon).astype(int)],True,(170,100,0),1)
        p=cv2.perspectiveTransform(polygon[:,None],inverse)[:,0]
        cv2.polylines(original,[np.rint(p).astype(int)],True,(170,100,0),1)
    # Cyan virtual centers; yellow observed support, never equated with numbered strings.
    for line in grid.get('virtual_lines',[]):
        for x in range(0,width-12,16):cv2.line(flat,(x,round(line['m']*x+line['b'])),(x+8,round(line['m']*(x+8)+line['b'])),(255,255,0),1)
    for line in grid.get('observed_string_layer',[]):
        for a,b in line.get('observed_intervals',[]):
            cv2.line(flat,(round(a),round(line['m']*a+line['b'])),(round(b),round(line['m']*b+line['b'])),(0,220,220),1)
    for observation in result['observations']:
        p=tuple(np.rint(observation['observation']['pixel']).astype(int))
        color=(0,150,255)if observation['observation']['branch']=='full_observation'else(255,0,255)
        cv2.circle(original,p,5,color,1)
        ellipse=observation['geometric_ellipse']
        if ellipse['status']=='ok':cv2.polylines(flat,[np.rint(np.clip(ellipse['exact_boundary'],-100000,100000)).astype(np.int32)],True,color,1)
    for segment in result['index_segment_hypotheses']:
        endpoints=np.array(segment['distribution']['pixel_endpoints'],float)
        projected=cv2.perspectiveTransform(endpoints[:,None],matrix)[:,0]
        cv2.line(original,tuple(np.rint(endpoints[0]).astype(int)),tuple(np.rint(endpoints[1]).astype(int)),(255,255,0),2)
        cv2.line(flat,tuple(np.rint(projected[0]).astype(int)),tuple(np.rint(projected[1]).astype(int)),(255,255,0),2)
    if review is not None:
        for label in review['landmarks']:
            if label['visibility']!='visible':continue
            point=np.array(label['pixel'],float)
            mapped=cv2.perspectiveTransform(point.reshape(1,1,2),matrix)[0,0]
            cv2.drawMarker(original,tuple(np.rint(point).astype(int)),(255,255,255),cv2.MARKER_CROSS,12,1)
            if np.max(abs(mapped))<100000:cv2.drawMarker(flat,tuple(np.rint(mapped).astype(int)),(255,255,255),cv2.MARKER_CROSS,10,1)
    cv2.putText(original,f"frame{grid['frame_index']} PTS{grid['frame_pts_s']:.6f} / virtual cells / contact unknown",(5,20),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,255),1)
    cv2.putText(original,'orange=full; magenta=crop; cyan/dark grid=virtual, yellow=observed support',(5,40),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,255),1)
    cv2.imwrite(str(out/(stem+'_original.png')),original);cv2.imwrite(str(out/(stem+'_flat.png')),flat)
    # Cell mass heatmap, common scale [0,1]; each row is a conditional spatial model.
    cols=sorted({c['physical_fret_candidate']for c in grid['cells']});heat=np.zeros((6,len(cols)),np.float32)
    for cell in selected['cells']if selected else []:heat[6-cell['virtual_string_num'],cols.index(cell['physical_fret_candidate'])]=cell['position_mass']
    heat=cv2.applyColorMap(np.rint(heat*255).astype(np.uint8),cv2.COLORMAP_INFERNO)
    heat=cv2.resize(heat,(max(600,len(cols)*70),240),interpolation=cv2.INTER_NEAREST)
    pane=np.full((300,heat.shape[1]+60,3),235,np.uint8);pane[30:270,60:]=heat
    for i in range(6):cv2.putText(pane,'V'+str(6-i),(5,55+i*40),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1)
    for i,fret in enumerate(cols):cv2.putText(pane,'F?'+str(fret),(65+round(i*heat.shape[1]/len(cols)),290),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,0),1)
    cv2.putText(pane,'Index spatial mass [0,1] / not contact probability',(5,18),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,0),1)
    cv2.imwrite(str(out/(stem+'_heatmap.png')),pane)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--grid-root',type=Path,default=GRID_ROOT);parser.add_argument('--samples',type=int,default=8192)
    args=parser.parse_args();out=args.output
    if (out/'manifest.json').exists():raise FileExistsError('Use a new output; existing run preserved')
    out.mkdir(parents=True,exist_ok=True)
    raw={r['frame_index']:r for r in map(json.loads,RAW.read_text().splitlines())}
    robust=json.loads(ROBUST.read_text());review=json.loads(Path('dataset/hand_analysis/human_review_20261103/validated_review.json').read_text())['reviews'][0]
    records=[];kim=[];direct=[]
    fixture=json.loads((args.grid_root/'same_frame_fixture.json').read_text())
    fixture_frames={entry['frame_identity']['frame_index']:entry for entry in fixture['frames']}
    for frame in robust['frames']:
        index=frame['frame_index'];observations,segments=observations_for_frame(raw[index],frame)
        upstream_board=json.loads(Path(fixture_frames[index]['board_json']).read_text())
        paths=[Path(model['grid_json'])for model in fixture_frames[index]['models']]
        for path in paths:
            grid=json.loads(path.read_text())
            if 'cells'not in grid:continue
            model_reference=next(model for model in fixture_frames[index]['models']if Path(model['grid_json'])==path)
            assert_grid_compatible(grid,dict(fixture_frames[index]['frame_identity'],
                grid_id=model_reference['grid_id'],grid_version=fixture['grid_version'],
                canvas_size=upstream_board['canvas_size'],M=upstream_board['M'],M_inv=upstream_board['M_inv']))
            result=dict(schema_version='hand_cell_frame.v1',grid_id=grid['grid_id'],grid_version=grid['grid_version'],
                **{k:grid[k]for k in ['source_id','frame_index','frame_pts_s','frame_pixel_sha256']},
                grid_path=str(path),grid_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                hand_source=str(RAW),crop_source=str(ROBUST),synthetic=False,
                observations=[cell_distribution(grid,o,samples=args.samples)for o in observations],
                index_segment_hypotheses=[dict(segment_id=s['segment_id'],landmark_indices=s['landmark_indices'],branch=s['branch'],
                    distribution=segment_distribution(grid,s,s['endpoints'],samples=4096))for s in segments],
                assumptions_separate=True,contact='unknown',sounding='unknown',confidence_calibrated=False)
            for observation in result['observations']:assert_grid_compatible(grid,observation)
            stem=path.stem;write(out/(stem+'_hand_cells.json'),result)
            records.append(dict(frame_index=index,grid_id=grid['grid_id'],model=grid['assumptions']['model_name'],
                grid_version=grid['grid_version'],result_path=str(out/(stem+'_hand_cells.json')),
                observations=[dict(observation_id=o['observation']['observation_id'],top3=o['top3'],outside=o['outside_board_mass'],
                    unassigned=o['unassigned_mass'],decision=o['decision'],reasons=o['reasons'])for o in result['observations']]))
            if grid['assumptions']['model_name']=='candidate_anchor':
                image=Path(grid['frame_identity']['image_file']);original=cv2.imread(str(image))
                if hashlib.sha256(original.tobytes()).hexdigest()!=grid['frame_pixel_sha256']:raise ValueError('Grid source image mismatch')
                render(grid,result,original,out,stem,review if index==120 else None)
                # Previous direct evidence remains separate: no fixed strings assigned.
                direct.append(dict(frame_index=index,detected_line_count=len(grid.get('observed_string_layer',[])),
                    physically_numbered_observed_lines=sum(l.get('string_num')is not None for l in grid.get('observed_string_layer',[])),
                    virtual_cell_count=len(grid['cells']),same_as_direct_contact=False,
                    full_center_legacy_diagnostics=raw[index]['hands'][raw[index]['selected_hand_index']]['legacy_reference_center_diagnostics'] if raw[index]['selected_hand_index']is not None else []))
            if index==120:
                for point in review['landmarks']:
                    if point['visibility']!='visible':continue
                    reference=spatial_cells(grid,point['pixel'])
                    rows=[]
                    for o in result['observations']:
                        if o['observation']['landmark_index']==point['index']:
                            rows.append(dict(observation_id=o['observation']['observation_id'],top3=o['top3'],
                                top1_in_same_estimated_grid_human_cell=bool(o['top1']and o['top1'][0]['cell_id']in reference['cell_ids'])))
                    if point['index']in [5,6,7]and raw[index]['selected_hand_index']is not None:
                        hand=raw[index]['hands'][raw[index]['selected_hand_index']]
                        rows.append(dict(observation_id='full_joint_'+str(point['index']),
                            model_point_spatial_cells=spatial_cells(grid,hand['landmarks'][point['index']]['pixel']),
                            comparison_type='same_estimated_grid_point_membership_only'))
                    kim.append(dict(frame_index=120,grid_id=grid['grid_id'],model=grid['assumptions']['model_name'],
                        landmark_index=point['index'],human_spatial_reference=reference,model_comparison=rows,
                        evaluation_only=True,actual_string_fret_contact_accuracy=None))
        print('processed frame',index,flush=True)
    write(out/'manifest.json',dict(schema_version='hand_cell_run.v1',frames=sorted({r['frame_index']for r in records}),
        models=len(records),records=records,api_calls=0,new_model_inferences=0,synthetic=False,
        note='Only A-supplied real grid JSON; synthetic adapter tests are separate'))
    write(out/'kim_same_estimated_grid_evaluation.json',dict(visible_points=8,comparisons=kim,evaluation_only=True,
        labels_used_in_runtime=False,contact_ground_truth=False))
    write(out/'direct_string_comparison.json',direct)
    print('models',len(records),'real frames',len({r['frame_index']for r in records}))


if __name__=='__main__':main()
