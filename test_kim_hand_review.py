import copy
import json
from pathlib import Path
import unittest

from evaluate_kim_hand_review import associate_visible_points,evaluate,validate_identity

ROOT=Path(__file__).resolve().parent


class KimReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review=json.loads((ROOT/'dataset/hand_analysis/human_review_20261103/validated_review.json').read_text())['reviews'][0]
        cls.obs=next(json.loads(l)for l in (ROOT/'dataset/hand_analysis/runs/clip_003_012_20261103_v1/observations.jsonl').read_text().splitlines() if json.loads(l)['frame_index']==120)

    def test_null_wrist_not_invented_multi_point_association(self):
        result=associate_visible_points(self.review,self.obs['hands'])
        self.assertEqual(result['derived_hand_index'],0)
        self.assertIsNone(result['original_fretting_hand_index'])
        self.assertGreater(result['runner_up_median_margin_px'],700)
        self.assertEqual(result['candidates'][0]['inliers_within_30px'],8)

    def test_tied_hands_remain_ambiguous(self):
        first=copy.deepcopy(self.obs['hands'][0]);second=copy.deepcopy(first);second['hand_index']=99
        self.assertIsNone(associate_visible_points(self.review,[first,second])['derived_hand_index'])
        short=dict(self.review,landmarks=self.review['landmarks'][:3])
        self.assertIsNone(associate_visible_points(short,self.obs['hands'])['derived_hand_index'])

    def test_error_evaluation_does_not_move_predictions_or_change_gates(self):
        obs=copy.deepcopy(self.obs);review=copy.deepcopy(self.review)
        result=evaluate(review,obs)
        self.assertEqual(obs,self.obs);self.assertEqual(review,self.review)
        self.assertEqual(result['visible_points'],8)
        self.assertEqual(result['unknown_points'],1)
        self.assertAlmostEqual(result['full_error']['mean_px'],9.33029393377,places=7)
        self.assertEqual(result['current_fingertip_gate']['excessive_withholding_count'],2)
        self.assertEqual(result['current_fingertip_gate']['withheld'],5)
        self.assertTrue(result['current_thresholds_unchanged'])
        ablation=result['development_gate_ablations'][-1]
        self.assertEqual(ablation['passed'],5)
        self.assertEqual(ablation['passed_but_error_over_6px'],3)

    def test_matching_frame_identity_required(self):
        path=ROOT/'dataset/chord_video_review/case_0005.00.png'
        validate_identity(self.review,self.obs,path)
        with self.assertRaises(ValueError):validate_identity(dict(self.review,frame_index=121),self.obs,path)


if __name__=='__main__':unittest.main()
