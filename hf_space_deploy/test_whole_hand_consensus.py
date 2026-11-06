import unittest
import numpy as np
from whole_hand_consensus import choose_candidate

def candidate(name,shift):return dict(candidate_id=name,hands=[dict(pixel_landmarks=(np.arange(42).reshape(21,2)+shift).tolist())])

class WholeTests(unittest.TestCase):
    def test_selected_points_belong_to_one_current_observation(self):
        views=[candidate('a',0),candidate('b',1),candidate('c',80)];r=choose_candidate(views)
        self.assertIn(r['selected'],views);self.assertFalse(r['coordinates_adjusted'])
    def test_missing_views_do_not_copy_previous_positions(self):
        self.assertIsNone(choose_candidate([],np.zeros((21,2)))['selected'])
    def test_large_hand_motion_disables_history(self):
        r=choose_candidate([candidate('a',200),candidate('b',201)],np.arange(42).reshape(21,2))
        self.assertEqual(r['continuity_weight_used'],0)

if __name__=='__main__':unittest.main()
