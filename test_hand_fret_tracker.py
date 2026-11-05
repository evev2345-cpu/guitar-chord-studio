import unittest
from types import SimpleNamespace as NS

import numpy as np

from hand_fret_tracker import FretboardGeometry, analyze_result, project


def wire(n, b, m=0, source='observed'):
    return dict(fret_num=n, m=m, b=b, source=source)


class HandGeometryTests(unittest.TestCase):
    def setUp(self):
        self.board = FretboardGeometry([[0, 0], [800, 0], [800, 150], [0, 150]],
                                      [wire(4, 100), wire(5, 200, .1, 'interpolated'),
                                       dict(fret_num=6, source='occluded'), wire(7, 400)])

    def detection(self, positions):
        return NS(hand_landmarks=[[NS(x=x / 800, y=y / 150, z=0) for _ in range(21)]
                                  for x, y in positions],
                  handedness=[[NS(category_name='Left', score=.9)] for _ in positions])

    def test_physical_number_sloped_wire_and_evidence(self):
        result = self.board.candidate([205, 100])
        self.assertEqual(result['fret_num'], 5)
        self.assertEqual(result['boundary_wires'][1]['source'], 'interpolated')
        self.assertFalse(result['contact_confirmed'])

    def test_no_assignment_outside_or_across_missing_wire(self):
        for p in ([-1, 50], [800, 50], [150, 150]):
            self.assertEqual(self.board.candidate(p)['status'], 'outside_board')
        self.assertEqual(self.board.candidate([300, 50])['status'], 'unresolved_fret_geometry')
        self.assertEqual(self.board.candidate([np.nan, 50])['status'], 'invalid_projection')

    def test_temporary_string_direction(self):
        self.assertEqual(self.board.candidate([150, 1], True)['string_estimate'], 6)
        self.assertEqual(self.board.candidate([150, 149], True)['string_estimate'], 1)
        self.assertNotIn('string_estimate', self.board.candidate([150, 1]))

    def test_no_stale_observation_and_ambiguous_selection(self):
        good = analyze_result(self.detection([(150, 50)]), (150, 800), self.board)
        self.assertEqual(good['status'], 'selected')
        empty = analyze_result(self.detection([]), (150, 800), self.board)
        self.assertEqual(empty['status'], 'no_hands')
        self.assertEqual(empty['hands'], [])
        ambiguous = analyze_result(self.detection([(150, 50), (160, 60)]), (150, 800), self.board)
        self.assertEqual(ambiguous['status'], 'ambiguous_hand_selection')
        self.assertTrue(all(not h['candidates'] for h in ambiguous['hands']))

    def test_mirror_prior_and_player_setting(self):
        detection = self.detection([(150, 50)])
        for mirror, expected in [('yes', 'Left'), ('no', 'Right'), ('unknown', None)]:
            result = analyze_result(detection, (150, 800), self.board, 'left', mirror)
            self.assertEqual(result['hands'][0]['anatomical_handedness'], expected)
        far = analyze_result(self.detection([(2000, 1000)]), (150, 800), self.board)
        self.assertEqual(far['status'], 'no_hand_near_board')

    def test_projection_roundtrip_and_pole(self):
        board = FretboardGeometry([[10, 20], [500, 50], [450, 140], [20, 150]], [])
        points = np.array([[100., 80.], [200., 90.]])
        np.testing.assert_allclose(project(project(points, board.M), board.M_inv), points)
        matrix = np.eye(3)
        matrix[2] = [1, 0, 0]
        self.assertTrue(np.isnan(project([[0, 1]], matrix)).all())


if __name__ == '__main__':
    unittest.main()
