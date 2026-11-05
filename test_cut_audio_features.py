import unittest
import numpy as np
from audio_analysis import features
from cut_audio_features import cut_features,cut_dictionary
from harmonic_chord_features import WINDOW
from sweep_bandcut_vision_weights import band_cut,LOW_HZ,HIGH_HZ

class CutTests(unittest.TestCase):
    def test_same_baseline(self):
        t=np.arange(WINDOW*3)/44100
        x=band_cut(sum(np.cos(2*np.pi*f*t) for f in [196,247,294,349])/10,44100)[WINDOW:2*WINDOW]
        arrays,_,_=cut_features(x,44100)
        old,_=features(x,44100,min_frequency=LOW_HZ,max_frequency=HIGH_HZ)
        np.testing.assert_array_equal(arrays['peak'],old['pitch_class_salience'][0]['salience'])
        self.assertGreater(arrays['harmonic'][5],.1)
    def test_model_only_retained_band(self):
        model,valid=cut_dictionary(44100);freq=np.fft.rfftfreq(WINDOW,1/44100)[valid]
        self.assertEqual(model.shape,(len(freq),51))
        self.assertGreaterEqual(freq.min(),LOW_HZ);self.assertLessEqual(freq.max(),HIGH_HZ)
    def test_silence_validation(self):
        arrays,amp,res=cut_features(np.zeros(WINDOW),44100)
        self.assertTrue(all(not s.any() for s in arrays.values()))
        with self.assertRaises(ValueError):cut_features(np.zeros(12),44100)

if __name__=='__main__':unittest.main()
