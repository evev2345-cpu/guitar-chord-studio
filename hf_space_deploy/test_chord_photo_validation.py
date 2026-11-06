import unittest
from pathlib import Path
import numpy as np
from chord_photo_validation import probability_candidates, string_interface, calibrate
from fingertip_probability import circle_distribution


class ChordPhotoTests(unittest.TestCase):
    def test_multiple_candidates_and_explicit_unassigned_mass(self):
        distribution = circle_distribution([100, 2], 6, np.eye(3))
        wires = [dict(fret_num=i, m=0, b=x, source='observed') for i,x in [(0,0),(1,100),(2,200)]]
        result = probability_candidates(distribution, wires, [200,150])
        self.assertGreater(result['candidates'][0]['probability'], .1)
        self.assertGreater(result['candidates'][1]['probability'], .1)
        self.assertGreater(result['outside_board_probability'], .1)
        self.assertAlmostEqual(sum(r['probability'] for r in result['candidates'])+result['unassigned_probability'],1)

    def test_unresolved_cell_not_nearest_assignment(self):
        d = circle_distribution([100, 70], 3, np.eye(3))
        r = probability_candidates(d, [dict(fret_num=0,m=0,b=0),dict(fret_num=2,m=0,b=200)], [200,150])
        self.assertEqual(r['candidates'], [])
        self.assertEqual(r['unresolved_geometry_probability'], 1.)

    def test_external_strings_keep_estimates_and_require_matching_geometry(self):
        track = dict(board_result='board.json', canvas_size=[800,150])
        payload = dict(input_geometry='board.json', status='partial', strings=[dict(string_num=6,m=0,b=20,source='estimated')])
        result = string_interface(payload, track)
        self.assertEqual(result['strings'][0]['source'], 'estimated')
        self.assertEqual(string_interface(None,track)['status'], 'not_provided')
        payload['input_geometry']='different.json'
        with self.assertRaises(ValueError): string_interface(payload,track)

    def test_calibration_needs_actual_review_and_error(self):
        self.assertIsNone(calibrate([], {})['calibrated_radius_px'])
        tracks = {'a':dict(hands=[dict(hand_index=0,landmarks=[dict(pixel=[0,0])])])}
        labels=[dict(case_id='a', review_status='reviewed', reviewer='human', fretting_hand_index=0,
                     landmarks=[dict(index=0,pixel=[3,4],visibility='visible')])]
        self.assertEqual(calibrate(labels,tracks)['calibrated_radius_px'],5)


if __name__ == '__main__': unittest.main()
