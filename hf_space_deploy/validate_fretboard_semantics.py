"""Validate real new-version fixtures and scope restrictions."""
import json
from pathlib import Path
import cv2
import numpy as np
from apply_fretboard_semantics import DEFAULT_OUT,PARENT,REVIEW
from fretboard_frame_identity import assert_same_frame,sha256_file


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    manifest=read(DEFAULT_OUT/'frame_index_manifest.json')
    semantics=read(DEFAULT_OUT/'semantic_review_input_snapshot.json')
    counts=dict(frames=0,strings=0,direct_semantic_frames=0,semantic_confirmed_first_wires=0,
        precise_geometry_valid=0,contact_allowed=0,confirmed_capo=0,assigned_string_numbers=0,
        source_pixel_pts_conflicts=0,renumbered_existing_physical_indices=0)
    for r in manifest['frames']:
        board=read(r['board_json']);assert_same_frame(board,r)
        parent=read(PARENT/'frames'/Path(r['board_json']).name)
        assert_same_frame(board,parent)
        assert sha256_file(board['image_file'])==board['image_file_sha256']
        assert board['semantic_review']['independent_pixel_ground_truth'] is False
        assert board['geometry_validity']['status']=='suspect'
        assert board['identity_validation']['status']=='verified_against_redecoded_source'
        assert board['motion_validation']['status']=='consistent_with_recomputed_motion'
        np.testing.assert_array_equal(board['M'],parent['M'])
        np.testing.assert_array_equal(board['M_inv'],parent['M_inv'])
        assert board['geometry_validity']['contact_fret_decision_allowed'] is False
        assert board['capo']['value'] is None
        for f in board['frets']:
            assert f['relative_fret'] is None
            if f.get('parent_fret_num') is not None:assert f['parent_fret_num']==f['fret_num']
            if f['confirmed_physical_fret_num'] is not None:
                assert board['frame_index']==120 and f['fret_num']==1 and f['confirmed_physical_fret_num']==1
                assert f['coordinate_human_verified'] is False
                counts['semantic_confirmed_first_wires']+=1
        if board['frame_index']==120:
            counts['direct_semantic_frames']+=1
            assert next(f for f in board['frets'] if f['fret_num']==3)['source']=='estimated'
        else:assert board['semantic_review']['applies_directly_to_this_frame'] is False
        if r['strings_json']:
            strings=read(r['strings_json']);assert_same_frame(board,strings)
            assert all(s['string_num'] is None for s in strings['strings'])
            counts['strings']+=1
        counts['frames']+=1
    assert counts['frames']==217 and counts['strings']==13
    assert counts['direct_semantic_frames']==1 and counts['semantic_confirmed_first_wires']==1
    for path,old_hash in read(DEFAULT_OUT/'parent_preservation_check.json')['sha256'].items():
        assert sha256_file(PARENT/path)==old_hash
    report=dict(status='pass',checks=counts,api_calls=0,
        user_semantic_labels=3,independent_pixel_GT_labels=0,
        report_scope='one-frame semantic number only, not original-pixel precise geometry')
    (DEFAULT_OUT/'scope_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
