import unittest
import numpy as np
from basic_pitch_clock import window_output_times

class ClockTests(unittest.TestCase):
    def test_first_frame_zero_and_real_input_hop(self):
        a=window_output_times(0,172);b=window_output_times(1,172)
        self.assertEqual(a[0],0)
        self.assertAlmostEqual(b[0],(43844-30*256)/22050)
        self.assertGreater(b[0],a[-1])
    def test_long_clip_covers_tail_without_stretch(self):
        hop=(43844-30*256)/22050
        times=np.concatenate([window_output_times(i,172) for i in range(int(np.ceil(546/hop))+1)])
        times=times[times<546]
        self.assertTrue(np.all(np.diff(times)>0))
        self.assertLess(546-times[-1],256/22050)
        self.assertAlmostEqual(window_output_times(300,172)[0],300*hop)

if __name__=='__main__':unittest.main()
