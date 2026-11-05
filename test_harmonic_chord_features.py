import unittest
import numpy as np
from harmonic_chord_features import harmonic_salience,WINDOW
from supported_harmonic_features import supported_salience

class HarmonicTests(unittest.TestCase):
    def synth(self,midis):
        t=np.arange(WINDOW)/44100
        return sum(sum(np.cos(2*np.pi*440*2**((m-69)/12)*h*t)/h for h in range(1,9)) for m in midis)/30
    def test_silence(self):
        s,a,r=harmonic_salience(np.zeros(WINDOW),44100)
        self.assertFalse(s.any());self.assertFalse(a.any())
    def test_single_harmonic_stack(self):
        s,_,_=harmonic_salience(self.synth([43]),44100)
        self.assertEqual(int(s.argmax()),7)
        self.assertGreater(s[7],.8)
    def test_true_seventh_preserved(self):
        s,_,_=harmonic_salience(self.synth([43,47,50,53]),44100)
        self.assertGreater(s[5],.15)
        self.assertTrue(set(np.argsort(s)[-4:])=={7,11,2,5})
    def test_validation(self):
        with self.assertRaises(ValueError):harmonic_salience(np.zeros(10),44100)
        with self.assertRaises(ValueError):harmonic_salience(np.full(WINDOW,np.nan),44100)
    def test_support_gate_single_sine(self):
        t=np.arange(WINDOW)/44100
        s,a,_=supported_salience(.1*np.cos(2*np.pi*440*t),44100)
        self.assertEqual(int(s.argmax()),9)
        self.assertEqual(int(np.count_nonzero(a)),1)
    def test_support_gate_keeps_true_seventh(self):
        s,_,_=supported_salience(self.synth([43,47,50,53]),44100)
        self.assertGreater(s[5],.15)

if __name__=='__main__':unittest.main()
