import unittest
import numpy as np
from benchmark_harmonic_chords import diagnose

class DiagnosisTests(unittest.TestCase):
    def test_supported_seventh_is_not_called_absent(self):
        sal=np.zeros((1,12));sal[0,[0,4,7,10]]=[.4,.25,.25,.1]
        layer={'frames':[dict(time_s=1.,reference='C:7',correct_top1=False,top3=[dict(root_pc=0)])]}
        d=diagnose(sal,np.array([1.]),layer)['counts']
        self.assertEqual(d['wrong_seventh_pc_present'],1)
        sal[0,10]=0
        self.assertEqual(diagnose(sal,np.array([1.]),layer)['counts']['wrong_seventh_pc_weak'],1)
    def test_major_is_not_seventh_sample(self):
        layer={'frames':[dict(time_s=1.,reference='C:maj',correct_top1=False,top3=[])]}
        self.assertEqual(diagnose(np.ones((1,12)),np.array([1.]),layer)['counts'],{})

if __name__=='__main__':unittest.main()
