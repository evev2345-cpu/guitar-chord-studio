import unittest
import numpy as np
from temporal_audio_pool import pooled_chroma

class PoolTests(unittest.TestCase):
    def test_sequential_notes_collected_without_reference(self):
        grid=np.arange(101)/100;v=np.zeros((101,88));v[40,60-21]=.8;v[50,64-21]=.8;v[59,67-21]=.8
        s=pooled_chroma(grid,v,[.5],.2,'max')
        self.assertEqual(set(np.where(s[0]>0)[0]),{0,4,7})
        self.assertEqual(np.count_nonzero(pooled_chroma(grid,v,[.5])),1)
    def test_half_open_end_does_not_include_later_note(self):
        grid=np.arange(101)/100;v=np.zeros((101,88));v[60,60-21]=1
        self.assertFalse(pooled_chroma(grid,v,[.5],.2,'max').any())
    def test_incomplete_window_rejected(self):
        with self.assertRaises(ValueError):pooled_chroma([0,.01],np.zeros((2,88)),[0],.2)
    def test_frequency_range_and_silence(self):
        v=np.zeros((101,88));v[:,0]=1
        self.assertFalse(pooled_chroma(np.arange(101)/100,v,[.5],.2).any())

if __name__=='__main__':unittest.main()
