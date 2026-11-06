import copy
import unittest

from investigate_joint_failures import roi_candidate


class RecoveryTests(unittest.TestCase):
    def fixture(self):
        points = [dict(index=i, pixel=[100., 60.]) for i in range(21)]
        record = dict(source_id='s', frame_index=215, frame_pts_s=9., frame_pixel_sha256='p',
                      status='no_hand_near_board', hands=[{'hand_index': 0}],
                      roi_observations=[dict(hand_index=7, landmarks=points)])
        board = dict(image_size=[800, 150], canvas_size=[800, 150],
                     corners=[[0, 0], [800, 0], [800, 150], [0, 150]], frets=[])
        return record, board

    def test_recovery_preserves_raw_state_and_unknown_contact(self):
        record, board = self.fixture()
        original = copy.deepcopy(record)
        candidate, reason = roi_candidate(record, board)
        self.assertEqual(record, original)
        self.assertEqual(candidate['original_roi_hand_index'], 7)
        self.assertEqual(candidate['production_status'], 'no_hand_near_board')
        self.assertEqual(candidate['contact'], 'unknown')
        self.assertFalse(candidate['observation_reused_from_previous_frame'])
        self.assertEqual(candidate['confirmed_guitar_notes'], [])

    def test_no_roi_or_multiple_rois_does_not_force_selection(self):
        record, board = self.fixture()
        record['roi_observations'] *= 2
        self.assertIsNone(roi_candidate(record, board)[0])
        record['roi_observations'] = []
        self.assertEqual(roi_candidate(record, board)[1], 'roi_missing')

    def test_distant_roi_is_not_selected(self):
        record, board = self.fixture()
        for point in record['roi_observations'][0]['landmarks']:
            point['pixel'] = [5000., 5000.]
        self.assertEqual(roi_candidate(record, board)[1], 'roi_not_near_current_board')

    def test_existing_full_selection_not_replaced_by_roi(self):
        record, board = self.fixture()
        record['status'] = 'selected'
        self.assertEqual(roi_candidate(record, board)[1], 'original_full_frame_selection_available')


if __name__ == '__main__':
    unittest.main()
