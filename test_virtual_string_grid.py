import copy
import unittest

import cv2
import numpy as np

from virtual_string_grid import build_grid, area, assert_grid_compatible


def fixture(reverse=False):
    corners = [[0., 0.], [800., 0.], [800., 150.], [0., 150.]]
    if reverse:
        corners = [[800., 0.], [0., 0.], [0., 150.], [800., 150.]]
    matrix = cv2.getPerspectiveTransform(np.asarray(corners, np.float32),
                                         np.asarray([[0, 0], [800, 0], [800, 150], [0, 150]], np.float32))
    identity = dict(source_id='a'*64, frame_index=120, frame_pts_s=5.041667,
                    frame_pixel_sha256='b'*64, image_size=[800, 150])
    board = dict(**identity, frame_identity=identity, canvas_size=[800, 150], corners=corners,
                 M=matrix.tolist(), M_inv=np.linalg.inv(matrix).tolist(),
                 synthetic=True, frets=[dict(physical_fret_candidate=n, xt=n*100., xb=n*100.+n*2,
                             source='synthetic', confirmed_physical_fret_num=None) for n in range(4)])
    config = dict(six_side='top', anchor_y=[15., 18.], opposite_margin=[15., 24.],
                  anchor_status='assumed_not_observed')
    return board, config


class GridTests(unittest.TestCase):
    def test_five_intervals_and_independent_endpoints(self):
        b, c = fixture()
        g = build_grid(b, c)
        self.assertEqual(g['endpoint_spacing'], [24, 21.6])
        lines = g['virtual_lines']
        self.assertAlmostEqual(lines[-1]['y_nut']-lines[0]['y_nut'], 5*24)
        self.assertAlmostEqual(lines[-1]['y_body'], 126)

    def test_partition_no_overlap_or_missing_area(self):
        b, c = fixture()
        g = build_grid(b, c)
        self.assertEqual(len(g['cells']), 18)
        self.assertAlmostEqual(g['covered_fret_area'], g['partition_area'], places=5)
        self.assertAlmostEqual(sum(area(s['polygon']) for s in g['string_regions']), 800*150)
        self.assertGreater(g['unassigned_board_area'], 0)
        for cell in g['cells']:
            self.assertTrue(cell['is_virtual'])
            self.assertIsNone(cell['physical_string_num'])
            self.assertEqual(cell['contact'], 'unknown')

    def test_missing_and_unknown_number_no_bridge(self):
        b, c = fixture()
        b['frets'][1]['physical_fret_candidate'] = None
        g = build_grid(b, c)
        self.assertEqual({z['physical_fret_candidate'] for z in g['cells']}, {3})
        self.assertEqual(len(g['unresolved_fret_boundaries']), 2)

    def test_crossing_duplicate_and_invalid_spacing(self):
        b, c = fixture()
        b['frets'][2]['xb'] = 50
        g = build_grid(b, c)
        self.assertTrue(any(z['reason']=='crossing_or_reversed_boundaries' for z in g['unresolved_fret_boundaries']))
        b, c = fixture()
        b['frets'].append(copy.deepcopy(b['frets'][0]))
        with self.assertRaises(ValueError): build_grid(b, c)
        b, c = fixture()
        c['opposite_margin'] = [140, 140]
        with self.assertRaises(ValueError): build_grid(b, c)
        c['opposite_margin'] = [15, 15]
        c['spacing_scale'] = 2
        with self.assertRaises(ValueError): build_grid(b, c)

    def test_original_left_right_direction_and_bottom_six(self):
        b, c = fixture(reverse=True)
        g = build_grid(b, c)
        p = cv2.perspectiveTransform(np.array([[[0., 0.], [800., 0.]]]), np.asarray(g['M_inv']))[0]
        self.assertGreater(p[0, 0], p[1, 0])
        c.update(six_side='bottom', anchor_y=[135, 132])
        g = build_grid(b, c)
        self.assertGreater(g['virtual_lines'][0]['b'], g['virtual_lines'][-1]['b'])
        self.assertAlmostEqual(g['partition_area'], g['covered_fret_area'])

    def test_same_frame_geometry_and_grid_rejection(self):
        b, c = fixture()
        g = build_grid(b, c)
        self.assertTrue(assert_grid_compatible(g, copy.deepcopy(g)))
        for key, value in [('source_id', 'c'*64), ('frame_pts_s', 5.1), ('frame_pixel_sha256', 'c'*64),
                           ('grid_id', 'different'), ('grid_version', 'different'), ('canvas_size', [800, 151])]:
            other = copy.deepcopy(g)
            other[key] = value
            with self.assertRaises(ValueError): assert_grid_compatible(g, other)
        other = copy.deepcopy(g)
        other['M'][0][2] += 1
        with self.assertRaises(ValueError): assert_grid_compatible(g, other)
        b['M_inv'][0][2] += 1
        with self.assertRaises(ValueError): build_grid(b, c)

    def test_sensitivity_identity_and_no_confirmation_promotion(self):
        b, c = fixture()
        b['frets'][1]['confirmed_physical_fret_num'] = 1
        g = build_grid(b, c)
        c['anchor_y'][0] += 3
        changed = build_grid(b, c)
        self.assertNotEqual(g['grid_id'], changed['grid_id'])
        self.assertIsNone(g['spacing_error_px'])
        self.assertFalse(g['contact_fret_decision_allowed'])
        self.assertTrue(all(x['relative_fret'] is None and x['confirmed_physical_fret_num'] is None for x in g['cells']))
        self.assertFalse(g['confidence_calibrated'])
        self.assertTrue(g['synthetic'])

    def test_unverified_capo_value_is_not_applied(self):
        b, c = fixture()
        b['capo'] = dict(value=1, independently_verified=False, user_confirmed_stop_fret=False)
        self.assertTrue(all(z['relative_fret'] is None for z in build_grid(b, c)['cells']))
        b['capo']['user_confirmed_stop_fret'] = True
        self.assertEqual(build_grid(b, c)['cells'][0]['relative_fret'], 0)

    def test_observed_layer_remains_separate(self):
        b, c = fixture()
        obs = dict(**b, strings=[dict(source='observed', string_num=None, m=0., b=15.)])
        g = build_grid(b, c, obs)
        self.assertEqual(len(g['observed_string_layer']), 1)
        self.assertEqual(len(g['virtual_lines']), 6)
        obs['frame_index'] = 121
        with self.assertRaises(ValueError): build_grid(b, c, obs)

    def test_consistent_geometry_change_is_separate_grid(self):
        b, c = fixture()
        original = build_grid(b, c)
        b['corners'] = [[x+10, y] for x, y in b['corners']]
        matrix = cv2.getPerspectiveTransform(np.asarray(b['corners'], np.float32),
                                             np.asarray([[0, 0], [800, 0], [800, 150], [0, 150]], np.float32))
        b.update(M=matrix.tolist(), M_inv=np.linalg.inv(matrix).tolist())
        changed = build_grid(b, c)
        self.assertNotEqual(original['grid_id'], changed['grid_id'])
        with self.assertRaises(ValueError): assert_grid_compatible(original, changed)
        point = np.array([[[100., 50.]]])
        old = cv2.perspectiveTransform(point, np.asarray(original['M_inv']))
        new = cv2.perspectiveTransform(point, np.asarray(changed['M_inv']))
        self.assertAlmostEqual(new[0, 0, 0]-old[0, 0, 0], 10)
        with self.assertRaises(ValueError): build_grid(b, c, dict(**original, strings=[]))


if __name__ == '__main__':
    unittest.main()
