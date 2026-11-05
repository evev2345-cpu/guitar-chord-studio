import unittest
from robust_candidate_review import consensus_point, cluster_paths, link_paths


def view(pad, values):
    return dict(padding_detector_px=pad, strings=[dict(m=0.,b=y,observed_intervals=[[0,799]]) for y in values])


class RobustCandidateTests(unittest.TestCase):
    def test_one_crop_cannot_become_high_confidence(self):
        r=consensus_point([[10,20]])
        self.assertEqual(r['evidence_grade'],'insufficient_views')
        self.assertIsNone(r['calibrated_probability'])

    def test_medoid_is_observation_and_full_disagreement_abstains(self):
        observations=[[10,20],[11,20],[10,21],[10,20]]
        r=consensus_point(observations,full=[40,40])
        self.assertIn(r['selected_pixel'],observations)
        self.assertEqual(r['evidence_grade'],'abstain_full_crop_disagreement')
        self.assertFalse(r['full_observation_replaced'])

    def test_roi_dispersion_detects_view_instability(self):
        r=consensus_point([[10,20],[10,20],[10,20],[50,60]])
        self.assertEqual(r['evidence_grade'],'abstain_crop_disagreement')

    def test_padding_count_is_distinct_views_and_not_six_template(self):
        paths=cluster_paths([view(12,[10,10.2]),view(20,[10]),view(28,[10])])
        self.assertEqual(sum(p['status']=='repeated_padding_candidate' for p in paths),1)
        self.assertTrue(all(p['vote_count']<=3 for p in paths))
        self.assertTrue(all(p['physical_string_num'] is None for p in paths))
        self.assertEqual(cluster_paths([]),[])

    def test_transitive_edge_chain_not_merged(self):
        paths=cluster_paths([view(12,[0]),view(20,[3]),view(28,[6])],tolerance=4)
        self.assertTrue(all(p['vote_count']<3 for p in paths))

    def test_lost_track_not_imputed_and_long_gap_resets(self):
        p=dict(m=0.,b=140.,status='repeated_padding_candidate',frame_pts_s=1.)
        active,lost,n=link_paths([], [p],1)
        self.assertEqual(len(active),1)
        old=active[0]['track_id']
        empty,lost,n=link_paths(active,[],n)
        self.assertEqual(empty,[]);self.assertEqual(lost,[old])
        active2,_,_=link_paths(active,[dict(p,frame_pts_s=2.)],n)
        self.assertNotEqual(active2[0]['track_id'],old)
        self.assertFalse(active2[0]['observation_reused'])


if __name__=='__main__':unittest.main()
