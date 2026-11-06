import unittest
import numpy as np
from idmt_chords_benchmark import parse_label,pcm_float,snapshot

class IDMTTests(unittest.TestCase):
    def test_power(self):
        self.assertEqual(parse_label('E:5')['pcs'],(4,11))
        self.assertTrue(parse_label('E:5')['representable'])
    def test_inversion(self):
        self.assertEqual(parse_label('C:maj/3')['pcs'],(0,4,7))
    def test_pcm(self):
        np.testing.assert_allclose(pcm_float(np.array([-32768,0,16384],dtype=np.int16)),[-1,0,.5])
        np.testing.assert_allclose(pcm_float(np.array([.25],dtype=np.float32)),[.25])
        with self.assertRaises(ValueError):pcm_float(np.array([np.nan]))
    def test_bounds_and_silence(self):
        with self.assertRaises(ValueError):snapshot(np.zeros(44100),44100,0)
        np.testing.assert_array_equal(snapshot(np.zeros(44100),44100,.5),np.zeros(12))

if __name__=='__main__':unittest.main()
