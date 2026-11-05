import unittest

from joint_evidence_review import audio_matches, possible_strings, same_frame, select_frame, joint_string_scenarios


class JointEvidenceTests(unittest.TestCase):
    def test_source_pixel_and_pts_mismatch_rejected(self):
        a = dict(source_id='source', frame_index=120, frame_pixel_sha256='pixel', frame_pts_s=5.041667)
        same_frame(a, dict(a))
        for key, value in [('source_id', 'other'), ('frame_pixel_sha256', 'other'),
                           ('frame_index', 121), ('frame_pts_s', 5.083333)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                same_frame(a, dict(a, **{key: value}))

    def test_no_pose_carried_across_half_open_window(self):
        hands = [dict(frame_index=120, frame_pts_s=5.041667, status='selected'),
                 dict(frame_index=128, frame_pts_s=5.375, status='selected')]
        self.assertIsNone(select_frame(hands, 5.05, 5.35, {120}))
        self.assertEqual(select_frame(hands, 5.041667, 5.375, set())['frame_index'], 120)

    def test_missing_strings_do_not_become_fixed_six_observations(self):
        r = possible_strings([], [100, 30], 'low_e_top')
        self.assertEqual(r['status'], 'no_same_frame_string_evidence')
        self.assertIsNone(r['nearest_line_id'])
        lines = [dict(m=0, b=y, line_id=str(i), observed_intervals=[[0, 200]])
                 for i, y in enumerate([10, 30, 50, 70, 90])]
        r = possible_strings(lines, [100, 50], 'low_e_top')
        self.assertEqual(r['strings'], [3, 4])
        self.assertEqual(r['mapping_count'], 6)
        self.assertIsNone(r['physical_string_confirmed'])

    def test_matches_keep_spectral_provenance_and_reject_octave(self):
        candidates = [dict(candidate_id='a', median_frequency_hz=440,
                           evidence_ids=['peak1'], pitch_status='spectral_peak_candidate')]
        self.assertEqual(audio_matches(69, candidates)[0]['evidence_ids'], ['peak1'])
        self.assertEqual(audio_matches(69, candidates)[0]['instrument_attribution'], 'unknown')
        self.assertEqual(audio_matches(57, candidates), [])

    def test_fingers_cannot_choose_inconsistent_numbers_for_same_line(self):
        lines = [dict(m=0, b=i*20, line_id=str(i)) for i in range(5)]
        fingers = []
        for finger, string in [('index', 5), ('middle', 6)]:
            fingers.append(dict(finger=finger, nearest_line_diagnostic={'nearest_line_id': '0'},
                                hypotheses=[dict(string_hypothesis=string, physical_fret_candidate=3,
                                  midi_if_fretted_and_standard_tuning=48,
                                  audio_matches=[{'evidence_ids': ['p']}])]))
        scenarios = joint_string_scenarios(lines, fingers, 'low_e_top', 800)
        self.assertEqual(len(scenarios), 6)
        self.assertTrue(all(len(s['compatible_finger_hypotheses']) <= 1 for s in scenarios))
        self.assertTrue(all(not s['contact_confirmed'] for s in scenarios))


if __name__ == '__main__':
    unittest.main()
