import unittest
import numpy as np
from compare_egdb_timbres import align_envelopes, compare_pair


class TimbreDiagnosticsTests(unittest.TestCase):
    def test_positive_offset_and_gain_do_not_use_chord_output(self):
        signal=np.random.default_rng(7).random(1800)**5
        target=np.r_[np.zeros(23),signal*3,np.zeros(30)]
        alignment=align_envelopes(signal,target)
        self.assertEqual(alignment['target_offset_s'],.23)
        self.assertEqual(alignment['status'],'provisional_usable')
        self.assertTrue(all(t==.23 for t in alignment['local_offsets_s']))

    def test_silence_has_no_trusted_alignment(self):
        alignment=align_envelopes(np.zeros(1200),np.zeros(1300))
        self.assertEqual(alignment['status'],'uncertain')

    def test_identical_notes_compare_equal_without_ground_truth(self):
        grid=np.arange(0,2,.01);notes=np.zeros((len(grid),88))
        notes[:,np.array([48,52,55])-21]=.8
        summary,rows=compare_pair(grid,notes,grid,notes,0.,.2)
        self.assertEqual(summary['raw_top1_agreement_given_both'],1.)
        self.assertEqual(summary['mean_midi_jaccard_given_both_active'],1.)
        self.assertEqual(summary['mean_tone_notes_not_in_di'],0.)
        self.assertEqual(summary['di_abstain'],0)
        self.assertTrue(all(r['di_midi']==r['tone_midi'] for r in rows))


if __name__=='__main__':unittest.main()
