"""Validate actual clip fixtures, not just synthetic identity tests."""
import json
import hashlib
from pathlib import Path
import cv2
import numpy as np
from fretboard_frame_identity import assert_same_frame,sha256_file
from review_fretboard_clip import DEFAULT_OUT


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=DEFAULT_OUT)
    out=parser.parse_args().run
    manifest=json.loads((out/'frame_index_manifest.json').read_text(encoding='utf-8'))
    cases=json.loads((out/'same_frame_fixture.json').read_text(encoding='utf-8'))
    assert manifest['primary_interval_frames']==216
    assert manifest['boundary_audit_frames']==1
    expected=manifest['source_id'];counts={'frames':0,'strings':0,'source_conflicts':0,'pixel_hash_conflicts':0,'file_hash_conflicts':0,'geometry_valid':0,'geometry_suspect':0,'geometry_unknown':0}
    string_ids=[]
    for record in manifest['frames']:
        image=Path(record['image_file']);raw=cv2.imread(str(image))
        assert sha256_file(image)==record['image_file_sha256']
        assert hashlib.sha256(raw.tobytes()).hexdigest()==record['frame_pixel_sha256']
        board=json.loads(Path(record['board_json']).read_text(encoding='utf-8'))
        assert_same_frame(record,board)
        assert record['source_id']==expected
        assert not board['geometry_validity']['contact_fret_decision_allowed']
        assert board['capo']['value'] is None
        assert board['capo']['physical_fret_candidate']==1
        assert all(f['relative_fret'] is None and f['confirmed_physical_fret_num'] is None for f in board['frets'])
        assert next(f for f in board['frets'] if f['fret_num']==1)['legacy_fret_num']==2
        M=np.asarray(board['M']);inv=np.asarray(board['M_inv']);corners=np.asarray(board['corners'],np.float64)[:,None]
        returned=cv2.perspectiveTransform(cv2.perspectiveTransform(corners,M),inv)
        np.testing.assert_allclose(returned,corners,atol=1e-6)
        counts['frames']+=1;counts['geometry_'+board['geometry_validity']['status']]+=1
        if record['strings_json']:
            strings=json.loads(Path(record['strings_json']).read_text(encoding='utf-8'))
            assert_same_frame(record,strings)
            assert all(s['string_num'] is None for s in strings['strings'])
            assert all(s['source']=='observed' for s in strings['strings'])
            assert len(strings['unresolved'])==6
            counts['strings']+=1;string_ids.append(record['frame_index'])
    assert len(cases['frames'])==13
    assert all(i in string_ids for i in [71,81,120,179,286,287])
    check=json.loads((out/'decode_identity_check.json').read_text())
    assert check['forced601_exact_matches']==[True,True,True]
    assert len(check['expanded_same_index_validation'])==7
    assert all(r['hash_matches'] for r in check['expanded_same_index_validation'])
    (out/'validation.json').write_text(json.dumps(dict(status='pass',checks=counts,
        real_fixture=True,api_calls=0),indent=2),encoding='utf-8')
    print(json.dumps(counts,indent=2))


if __name__=='__main__':main()
