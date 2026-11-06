import unittest
import numpy as np
from audio_change_pool import detect_changes,clipped_pool

class ChangeTests(unittest.TestCase):
    def test_detect_true_pc_change(self):
        t=np.arange(201)/100;v=np.zeros((201,88));v[:100,np.array([60,64,67])-21]=.8;v[100:,np.array([62,66,69])-21]=.8
        b,_,_=detect_changes(t,v);self.assertTrue(any(abs(b-1)<.05))
    def test_repeated_same_pc_no_change(self):
        t=np.arange(201)/100;v=np.zeros((201,88));v[:,np.array([60,64,67])-21]=.8
        b,_,_=detect_changes(t,v);self.assertEqual(len(b),0)
    def test_clipping_keeps_opposite_chord_out(self):
        t=np.arange(201)/100;v=np.zeros((201,88));v[:100,60-21]=.8;v[100:,62-21]=.8
        s,support=clipped_pool(t,v,[.95],.4,[1.]);self.assertGreater(s[0,0],0);self.assertEqual(s[0,2],0);self.assertTrue(support[0]['clipped'])
    def test_no_boundary_equals_max(self):
        from temporal_audio_pool import pooled_chroma
        t=np.arange(201)/100;v=np.random.default_rng(1).random((201,88))
        s,_=clipped_pool(t,v,[1.],.2,[]);np.testing.assert_allclose(s,pooled_chroma(t,v,[1.],.2))
    def test_noise_gated_detector_finds_change_with_weak_background(self):
        from calibrated_audio_changes import detect_changes as gated
        t=np.arange(201)/100;v=np.full((201,88),.1);v[:100,np.array([60,64,67])-21]=.8;v[100:,np.array([62,66,69])-21]=.8
        b,_,_=gated(t,v,.4);self.assertTrue(any(abs(b-1)<.05))

if __name__=='__main__':unittest.main()
