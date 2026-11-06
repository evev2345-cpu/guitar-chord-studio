import copy
import json
from pathlib import Path
import unittest

from hand_quality import location_gate, reviewed_gate
from chord_photo_validation import string_interface


ROOT=Path(__file__).resolve().parent


class HandQualityTests(unittest.TestCase):
    def test_frozen_csharp_m7_abstains_despite_concentrated_fret_distribution(self):
        fixture=json.loads((ROOT/'dataset/regression/csharp_m7_wrong_center.json').read_text())
        gate=location_gate(fixture['hand'],fixture['roi_hands'],fixture['tip'],fixture['radius'])
        gate=reviewed_gate(gate,fixture['visual_label_pixel'],fixture['radius'])
        self.assertEqual(gate['decision'],fixture['expected_decision'])
        self.assertGreater(gate['review_error_px'],23)
        self.assertEqual(gate['reasons'],fixture['expected_reasons'])

    def test_cross_view_gate_is_general_and_never_averages_centers(self):
        hand=dict(landmarks=[dict(pixel=[100,100])])
        roi=[dict(landmarks=[dict(pixel=[111,100])])]
        gate=location_gate(hand,roi,0)
        self.assertEqual(gate['decision'],'abstain')
        self.assertEqual(gate['full_pixel'],[100,100])
        gate=location_gate(hand,[hand],0)
        self.assertEqual(gate['decision'],'candidate_only')
        self.assertEqual(gate['contact'],'unknown')

    def test_motion_and_bad_timestamp(self):
        hand=dict(landmarks=[dict(pixel=[100,100])])
        prior=dict(timestamp_ms=1000,pixel=[80,100])
        self.assertIn('rapid_landmark_change',location_gate(hand,[hand],0,previous=prior,timestamp_ms=1040)['reasons'])
        with self.assertRaises(ValueError):location_gate(hand,[hand],0,previous=prior,timestamp_ms=1000)

    def test_latest_string_schema_null_numbers_and_same_frame_verification(self):
        tracking=json.loads((ROOT/'dataset/chord_video_review/case_0194.86_tracking.json').read_text())
        payload=json.loads((ROOT/'dataset/string_review/case_0194.86_high.json').read_text())
        result=string_interface(payload,tracking)
        self.assertEqual(result['identity_verification'],'decoded_bgr_pixel_sha256_and_homography')
        self.assertEqual(result['unresolved'],payload['unresolved'])
        self.assertTrue(any(s['string_num'] is None for s in result['strings']))
        altered=copy.deepcopy(payload);altered['M'][0][2]+=1
        with self.assertRaises(ValueError):string_interface(altered,tracking)
        altered=copy.deepcopy(payload);altered['image_sha256']='0'*64
        with self.assertRaises(ValueError):string_interface(altered,tracking)

    def test_sequence_has_no_carried_observations(self):
        summary=json.loads((ROOT/'dataset/chord_sequence_review/sequence_summary.json').read_text())
        self.assertEqual(len(summary['frames']),49)
        for row in summary['frames']:
            frame=json.loads((ROOT/f'dataset/chord_sequence_review/frame_{row["frame_index"]}.json').read_text())
            self.assertFalse(frame['reused_observation'])
            self.assertEqual(frame['observation'],'fresh_mediapipe_image_inference')
            if frame['status']!='selected':
                self.assertEqual(frame['location_quality'],{})
            self.assertIsNone(frame['physical_fret_decision'])


if __name__=='__main__':unittest.main()
