import unittest
import numpy as np
from audio_note_calibrator import corrected_probabilities,probabilities_to_chroma
from train_audio_note_calibrator import split_for,choose_threshold

class CalibrationTests(unittest.TestCase):
    def test_zero_residual_preserves_model(self):
        p=np.linspace(.01,.99,102).reshape(2,51);w=dict(w1=np.zeros((32,51)),b1=np.zeros(32),w2=np.zeros((51,32)),b2=np.zeros(51))
        np.testing.assert_allclose(corrected_probabilities(p,w),p,atol=1e-12)
    def test_transpositions_and_players_stay_same_split(self):
        self.assertEqual(split_for('00_Jazz3-150-C_comp'),split_for('05_Jazz3-137-Eb_comp'))
        self.assertEqual(split_for('00_BN3-119-G_comp'),'validation')
        self.assertEqual(split_for('00_Jazz1-130-D_comp'),'train')
    def test_octaves_merge_and_silence_remains_empty(self):
        p=np.zeros((2,51));p[0,[60-38,72-38]]=[.4,.6];s=probabilities_to_chroma(p,.3)
        self.assertEqual(s[0,0],1);self.assertFalse(s[1].any())
    def test_threshold_selection_uses_passed_labels(self):
        p=np.array([[.21,.4],[.01,.02]]);y=np.array([[1,1],[0,0]])
        t,_=choose_threshold(p,y);self.assertEqual(t,.2)

if __name__=='__main__':unittest.main()
