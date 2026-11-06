import copy
import json
from pathlib import Path
import unittest
import numpy as np

from hand_frame_contract import frame_identity,adapt_geometry,apply_geometry_gate
from import_minimum_hand_review import validate_review
from hand_fret_tracker import FretboardGeometry


class FrameContractTests(unittest.TestCase):
    def setUp(self):
        self.frame=frame_identity('abc',0,dict(pts=512),'1/12288',np.zeros((20,30,3),np.uint8))

    def test_actual_pts_not_index_over_fps(self):
        self.assertAlmostEqual(self.frame['frame_pts_s'],1/24)
        self.assertIsNone(self.frame['image_file_sha256'])
        with self.assertRaises(ValueError):frame_identity('abc',0,{},'1/24',np.zeros((1,1,3),np.uint8))

    def test_subpixel_numerical_boundary_noise_is_not_clamped(self):
        corners=[[0,0],[800,0],[800,150],[0,150]]
        wire=dict(fret_num=0,m=0,b=-.00004)
        board=FretboardGeometry(corners,[wire])
        self.assertEqual(board.wires[0]['b'],-.00004)
        with self.assertRaises(ValueError):FretboardGeometry(corners,[dict(wire,b=-.01)])

    def test_upstream_exact_permission_separate_from_roi_validity(self):
        board=dict(self.frame,source='agent_manual_approximation',geometry_validity=dict(status='valid',roi_alignment_status='valid',contact_fret_decision_allowed=False))
        geometry=adapt_geometry(self.frame,board)
        gate=apply_geometry_gate(dict(decision='candidate_only',reasons=[]),geometry)
        self.assertEqual(gate['decision'],'abstain')
        self.assertEqual(geometry['source_kind'],'manual_approximation')
        self.assertIn('upstream_exact_fret_permission_missing',gate['reasons'])

    def test_wrong_frame_and_unknown_are_not_certified(self):
        self.assertEqual(adapt_geometry(self.frame,None)['status'],'unknown')
        board=dict(self.frame,geometry_validity=dict(status='suspect'))
        for key,value in [('source_id','other'),('frame_index',1),('frame_pts_s',2.),('frame_pixel_sha256','wrong')]:
            wrong=dict(board,**{key:value})
            with self.assertRaises(ValueError):adapt_geometry(self.frame,wrong)

    def test_review_import_rejects_hidden_coordinates_and_wrong_source(self):
        case=dict(self.frame,case_id='a',image_file_sha256='f')
        queue=dict(cases=[case],required_landmark_indices=[0,8])
        review=dict(case,review_status='reviewed',model_blind=True,reviewer='person_1',landmarks=[dict(index=8,visibility='visible',pixel=[2,3])])
        self.assertEqual(validate_review([review],queue)['visible_points'],1)
        bad=copy.deepcopy(review);bad['landmarks'][0]['visibility']='hidden'
        with self.assertRaises(ValueError):validate_review([bad],queue)
        bad=dict(review,source_id='different')
        with self.assertRaises(ValueError):validate_review([bad],queue)
        with self.assertRaises(ValueError):validate_review([dict(review,reviewer='agent')],queue)

    def test_existing_same_frame_upstream_fixture(self):
        root=Path('dataset/hand_analysis/runs/clip_003_012_20261103_v1')
        manifest=json.loads((root/'upstream_join/manifest.json').read_text())
        self.assertGreaterEqual(manifest['matched_frames'],12)
        for frame in manifest['frames']:
            self.assertFalse(frame['contact_fret_decision_allowed'])
            self.assertEqual(frame['source_kind'],'manual_approximation')


if __name__=='__main__':unittest.main()
