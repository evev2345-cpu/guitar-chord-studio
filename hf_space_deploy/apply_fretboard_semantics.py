"""New scoped-semantic fixture version; immutable parent results, no API."""
import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path
import cv2
import numpy as np
from fretboard_frame_identity import sha256_file,assert_same_frame
from fretboard_semantic_review import WIRE_CATALOG,validate_semantic_review,original_wire_support,exposed_wire_sequence,apply_scoped_review
from review_fretboard_clip import project,track,REFERENCE_CORNERS
from string_geometry import analyze_saved_board
from string_detector import render_strings

ROOT=Path(__file__).resolve().parent
PARENT=ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1'
DEFAULT_OUT=ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v2_semantic'
REVIEW=ROOT/'dataset/fretboard_review/human_semantic_review_frame120_20261103.json'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def local_evidence(parent,review):
    reference=read(parent/'frames/clip003012_f000120_board.json')
    clear=read(parent/'frames/clip003012_f000071_board.json')
    im=cv2.imread(reference['image_file']);uncovered=cv2.imread(clear['image_file'])
    sequence=exposed_wire_sequence(uncovered)
    if len(sequence['selected_visible_metals'])<6:raise ValueError('Exposed sequence insufficient')
    motion={r['frame_index']:r for r in read(parent/'motion_evidence.json')}
    clear_to_reference=np.linalg.inv(np.asarray(motion[71]['affine']))
    catalog={}
    for entry in WIRE_CATALOG:
        physical=entry['physical_candidate']
        source=next(f for f in reference['frets'] if abs(np.mean(np.asarray(f['reference_endpoints'])[:,0])-entry['reference_x'])<2)
        clear_source=next(f for f in clear['frets'] if f.get('legacy_fret_num')==source.get('legacy_fret_num'))
        target=sequence['selected_visible_metals'][physical-1]
        expected=float(np.mean(np.asarray(clear_source['original_endpoints'])[:,0]))
        if abs(target['x']-expected)>10:raise ValueError('Visible sequence conflicts with geometry correspondence')
        catalog[entry['wire_id']]=dict(**entry,
            parent_fret_num=source['fret_num'],historical_alias=source.get('legacy_fret_num'),
            reference_endpoints=source['reference_endpoints'],
            source_frame120_pixel_sha256=reference['frame_pixel_sha256'],
            source_frame071_pixel_sha256=clear['frame_pixel_sha256'],
            frame120_support=original_wire_support(im,source['original_endpoints'],
                visible=entry['frame120_visibility']!='occluded',partial=entry['frame120_visibility']=='partial'),
            exposed_frame071_support=original_wire_support(uncovered,clear_source['original_endpoints']),
            exposed_sequence_peak=target,
            human_confirmation='semantic first-wire number only' if physical==1 else None,
            independent_pixel_ground_truth=False)
        clear_support=catalog[entry['wire_id']]['exposed_frame071_support']
        if clear_support.get('fitted_endpoints'):
            projected=project(clear_support['fitted_endpoints'],clear_to_reference)
            base=np.asarray(source['reference_endpoints'],float)
            m=(base[1,0]-base[0,0])/(base[1,1]-base[0,1]);b=base[0,0]-m*base[0,1]
            delta=np.abs(projected[:,0]-(m*projected[:,1]+b))
            catalog[entry['wire_id']]['transfer_evidence']=dict(
                from_frame_index=71,from_frame_pts_s=clear['frame_pts_s'],to_frame_index=120,
                to_frame_pts_s=reference['frame_pts_s'],matrix_clear_to_reference=clear_to_reference.tolist(),
                projected_segment_to_reference=projected.tolist(),manual_model_disagreement_px=delta.tolist(),
                coordinates_human_verified=False,note='Agent image-support/texture-transfer evidence, not original-pixel GT')
    return catalog,sequence,reference


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--parent',type=Path,default=PARENT)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUT);args=parser.parse_args()
    parent,out=args.parent,args.output
    if (out/'manifest.json').exists():raise SystemExit('Run exists; select another output to preserve it')
    out.mkdir(parents=True,exist_ok=True)
    dense=read(parent/'frame_index_manifest.json');parent_manifest=read(parent/'manifest.json')
    review=read(REVIEW);review_hash=sha256_file(REVIEW)
    video=Path(parent_manifest['source_path'])
    if sha256_file(video)!=dense['source_id']:raise ValueError('Source video changed')
    parent_hashes={str(p.relative_to(parent)):sha256_file(p) for p in [parent/'manifest.json',parent/'same_frame_fixture.json',parent/'frames/clip003012_f000120_board.json']}
    catalog,sequence,reference=local_evidence(parent,review)
    validate_semantic_review(review,reference)
    write(out/'semantic_review_input_snapshot.json',review)
    write(out/'per_wire_original_review.json',catalog);write(out/'exposed_sequence_frame071.json',sequence)
    # Capture mixed-version legacy numbering without modifying the other module.
    snapshots=[]
    for path in [ROOT/'dataset/chord_video_review/case_0005.00_board.json',parent/'legacy_case0005_identity_adapter.json']:
        raw=path.read_bytes();data=json.loads(raw)
        snapshots.append(dict(source_path=str(path),file_sha256=hashlib.sha256(raw).hexdigest(),
            matching_first_wire_records=[dict(fret_num=f['fret_num'],original_endpoints=f.get('original_endpoints')) for f in data['frets'] if f.get('original_endpoints') and abs(np.mean(np.asarray(f['original_endpoints'])[:,0])-1057)<3]))
    write(out/'mixed_version_numbering_evidence.json',snapshots)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=pts,pts_time','-of','json',str(video)],capture_output=True,text=True,check=True).stdout)['frames']
    ref_image=cv2.imread(reference['image_file'])
    by_index={r['frame_index']:r for r in dense['frames']}
    representatives={r['frame_index'] for r in read(parent/'same_frame_fixture.json')['frames']}
    cap=cv2.VideoCapture(str(video));records=[];validation=[];panels=[]
    for index in range(max(by_index)+1):
        ok,image=cap.read()
        if not ok:raise RuntimeError('Source decode failed')
        if index not in by_index:continue
        prior_record=by_index[index];board=read(prior_record['board_json'])
        pixel=hashlib.sha256(image.tobytes()).hexdigest()
        if pixel!=board['frame_pixel_sha256']:raise ValueError('Fresh decode pixel mismatch')
        if sha256_file(board['image_file'])!=board['image_file_sha256']:raise ValueError('PNG bytes changed')
        if abs(float(probe[index]['pts_time'])-board['frame_pts_s'])>5e-7:raise ValueError('Fresh PTS mismatch')
        motion,new_affine=track(ref_image,image)
        # The parent's motion matrix is stored in its dense motion evidence.
        if index==min(by_index):
            motion_map={r['frame_index']:r for r in read(parent/'motion_evidence.json')}
        old_affine=np.asarray(motion_map[index]['affine'])
        disagreement=float(np.linalg.norm(project(REFERENCE_CORNERS,new_affine)-project(REFERENCE_CORNERS,old_affine),axis=1).max())
        board['identity_validation']=dict(status='verified_against_redecoded_source',source_file_hash_verified=True,
            pixel_hash_verified=True,image_file_hash_verified=True,pts_verified=True)
        consistent=motion['status']=='valid' and disagreement<=1
        board['motion_validation']=dict(status='consistent_with_recomputed_motion' if consistent else 'not_verified',
            recomputed_roi_alignment=motion,maximum_parent_recompute_corner_disagreement_px=disagreement,
            note='Reproducibility of motion, not independent endpoint ground truth')
        updated=apply_scoped_review(board,review,reference,catalog,review_hash)
        updated.update(run_id=out.name,parent_run=str(parent),parent_board_sha256=sha256_file(prior_record['board_json']))
        board_path=out/'frames'/f"{board['case_id']}_board.json";write(board_path,updated)
        strings_path=None
        if index in representatives:
            strings,flat,_,_,inv=analyze_saved_board(image,updated,source_id=updated['case_id'])
            for line in strings['strings']:
                line['string_num']=None;line['number_source']='not_confirmed_by_semantic_object_review'
            strings['numbering_status']='unresolved'
            strings['unresolved']=[dict(string_num=n,source='unresolved',geometry=None,reason='No human string-identity confirmation') for n in range(1,7)]
            strings.update(geometry_validity=updated['geometry_validity'],capo=updated['capo'],semantic_review=updated['semantic_review'])
            strings_path=out/'frames'/f"{board['case_id']}_strings.json";write(strings_path,strings)
            flatvis,rawvis=render_strings(flat,image,inv,strings)
            cv2.polylines(rawvis,[np.round(updated['capo']['original_polygon']).astype(int)],True,(0,150,255),1)
            for fret in updated['frets']:
                if not fret.get('original_endpoints'):continue
                a,b=np.round(fret['original_endpoints']).astype(int)
                color=(0,255,0) if fret.get('confirmed_physical_fret_num')==1 else (255,100,255)
                cv2.line(rawvis,tuple(a),tuple(b),color,1)
            cv2.imwrite(str(out/'frames'/f"{board['case_id']}_overlay.png"),rawvis)
            cv2.imwrite(str(out/'frames'/f"{board['case_id']}_flat.png"),flatvis)
            tile=np.full((195,820,3),25,np.uint8)
            cv2.putText(tile,f"{board['case_id']} PTS={board['frame_pts_s']:.6f} first-semantic={'user' if index==120 else 'reference-only'}",(8,22),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1)
            tile[35:185,10:810]=flatvis;panels.append(tile)
        record=copy.deepcopy(prior_record);record.update(board_json=str(board_path.resolve()),
            strings_json=str(strings_path.resolve()) if strings_path else None,
            geometry_validity=updated['geometry_validity'],semantic_confirmation_direct=index==120,
            identity_validation=updated['identity_validation'],motion_validation=updated['motion_validation'])
        records.append(record);validation.append(dict(frame_index=index,identity='verified',motion_consistent=consistent,corner_disagreement_px=disagreement))
    cap.release()
    for page,start in enumerate(range(0,len(panels),4),1):cv2.imwrite(str(out/f'overview_{page}.jpg'),np.vstack(panels[start:start+4]))
    for path,original_hash in parent_hashes.items():
        if sha256_file(parent/path)!=original_hash:raise ValueError('Parent result modified during update')
    write(out/'parent_preservation_check.json',dict(status='pass',sha256=parent_hashes))
    write(out/'validation.json',dict(status='pass',frames=validation,verified_frames=len(records),api_calls=0))
    write(out/'frame_index_manifest.json',dict(source_id=dense['source_id'],frames=records,primary_interval_frames=216,boundary_audit_frames=1,api_calls=0))
    write(out/'same_frame_fixture.json',dict(source_id=dense['source_id'],frames=[r for r in records if r['frame_index'] in representatives],
        dense_frame_index=str((out/'frame_index_manifest.json').resolve()),join_keys=['source_id','frame_index','frame_pts_s','frame_pixel_sha256'],
        pts_float_join_tolerance_s=5e-7,api_calls=0))
    write(out/'manifest.json',dict(run_id=out.name,parent_run=str(parent),review_file=str(REVIEW),review_file_sha256=review_hash,
        source_id=dense['source_id'],frames=records,api_calls=0,scope='one-frame semantic labels; unverified precise geometry and other-frame identities retained'))
    print('Published',len(records),'frames;',sum(r['semantic_confirmation_direct'] for r in records),'direct semantic frame;',sum(v['motion_consistent'] for v in validation),'motion-consistent frames')
    print('First metal support:',catalog['metal_x1057']['frame120_support']['status'])


if __name__=='__main__':main()
