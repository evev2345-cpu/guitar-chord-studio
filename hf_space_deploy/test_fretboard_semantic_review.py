import copy
import json
import unittest
from pathlib import Path
from fretboard_semantic_review import apply_scoped_review,validate_semantic_review,original_wire_support
from apply_fretboard_semantics import PARENT,DEFAULT_OUT,REVIEW


class SemanticScopeTests(unittest.TestCase):
    def setUp(self):
        if not (DEFAULT_OUT/'per_wire_original_review.json').exists():self.skipTest('Actual review fixture not present')
        self.reference=json.loads((PARENT/'frames/clip003012_f000120_board.json').read_text())
        self.review=json.loads(REVIEW.read_text(encoding='utf-8'))
        self.catalog=json.loads((DEFAULT_OUT/'per_wire_original_review.json').read_text())

    def test_semantic_first_only_and_no_geometric_promotion(self):
        result=apply_scoped_review(self.reference,self.review,self.reference,self.catalog,'review_hash')
        self.assertEqual([f['fret_num'] for f in result['frets']],[0,1,2,3,4,5,6])
        confirmed=[f['fret_num'] for f in result['frets'] if f['confirmed_physical_fret_num'] is not None]
        self.assertEqual(confirmed,[1])
        first=next(f for f in result['frets'] if f['fret_num']==1)
        self.assertEqual(first['parent_fret_num'],1)
        self.assertEqual(first['legacy_fret_num'],2)
        self.assertFalse(first['coordinate_human_verified'])
        self.assertFalse(result['geometry_validity']['contact_fret_decision_allowed'])
        self.assertFalse(result['semantic_review']['independent_pixel_ground_truth'])
        self.assertIsNone(result['capo']['value'])
        self.assertFalse(result['capo']['user_confirmed_stop_fret'])
        self.assertTrue(all(f['relative_fret'] is None for f in result['frets']))

    def test_no_confirmation_on_other_frames(self):
        board=json.loads((PARENT/'frames/clip003012_f000071_board.json').read_text())
        board['identity_validation']={'status':'verified_against_redecoded_source'}
        board['motion_validation']={'status':'consistent_with_recomputed_motion'}
        result=apply_scoped_review(board,self.review,self.reference,self.catalog,'review_hash')
        self.assertFalse(result['semantic_review']['applies_directly_to_this_frame'])
        self.assertTrue(all(f['confirmed_physical_fret_num'] is None for f in result['frets']))
        self.assertEqual(result['semantic_review']['transfer_status'],'candidate_only')
        del board['identity_validation']
        result=apply_scoped_review(board,self.review,self.reference,self.catalog,'review_hash')
        self.assertEqual(result['semantic_review']['transfer_status'],'unknown')
        self.assertEqual(result['geometry_validity']['status'],'unknown')

    def test_source_pts_and_review_number_mismatch_rejected(self):
        wrong=copy.deepcopy(self.review);wrong['source_id']='b'*64
        with self.assertRaises(ValueError):validate_semantic_review(wrong,self.reference)
        wrong=copy.deepcopy(self.review);wrong['frame_pts_s']+=1/24
        with self.assertRaises(ValueError):validate_semantic_review(wrong,self.reference)
        wrong=copy.deepcopy(self.review);wrong['confirmations'][-1]['physical_fret_number_confirmed']=2
        with self.assertRaises(ValueError):validate_semantic_review(wrong,self.reference)
        board=dict(self.reference,source_id='b'*64)
        with self.assertRaises(ValueError):apply_scoped_review(board,self.review,self.reference,self.catalog,'hash')

    def test_unmatched_geometry_not_confirmed(self):
        board=copy.deepcopy(self.reference)
        first=next(f for f in board['frets'] if f['fret_num']==1)
        first['reference_endpoints']=[[1090,210],[1090,273]]
        result=apply_scoped_review(board,self.review,self.reference,self.catalog,'hash')
        self.assertTrue(all(f['confirmed_physical_fret_num'] is None for f in result['frets']))
        self.assertEqual(next(f for f in result['frets'] if f['fret_num']==1)['numbering_status'],'unknown_unmatched_geometry')

    def test_reference_index_and_duplicate_binding_rejected(self):
        wrong=dict(self.reference,frame_index=121)
        with self.assertRaises(ValueError):validate_semantic_review(self.review,wrong)
        board=copy.deepcopy(self.reference)
        board['frets'].append(copy.deepcopy(next(f for f in board['frets'] if f['fret_num']==1)))
        with self.assertRaises(ValueError):apply_scoped_review(board,self.review,self.reference,self.catalog,'hash')

    def test_hidden_wire_is_not_image_observation(self):
        result=apply_scoped_review(self.reference,self.review,self.reference,self.catalog,'hash')
        hidden=next(f for f in result['frets'] if f['fret_num']==3)
        self.assertEqual(hidden['source'],'estimated')
        self.assertEqual(hidden['visibility_status'],'occluded')
        self.assertEqual(hidden['numbering_evidence']['frame120_support']['points'],[])
        self.assertEqual(hidden['numbering_evidence']['frame120_support']['status'],'not_measured_occluded')


if __name__=='__main__':unittest.main()
