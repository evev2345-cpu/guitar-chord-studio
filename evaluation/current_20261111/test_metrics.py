import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'engine'))
from metrics import reference,score,collect,temporal


class EvaluationMetricsTests(unittest.TestCase):
    def test_root_and_quality_are_independent(self):
        ref=reference('C:maj')
        pred=dict(root_pc=2,quality='major',pcs=[2,6,9],symbol='D')
        s=score(ref,[pred]);self.assertEqual((s['exact'],s['root'],s['quality']),(0,0,1))

    def test_equal_pitch_classes_with_different_root_are_wrong(self):
        ref=reference('A:min7');c=dict(root_pc=0,quality='6',pcs=[0,4,7,9],symbol='C6')
        self.assertEqual(score(ref,[c])['exact'],0)

    def test_ambiguous_output_does_not_get_oracle_credit(self):
        r=reference('C:maj');c=dict(root_pc=0,pcs=[0,4,7],quality='major',symbol='C')
        s=score(r,[c,c]);self.assertEqual(s['exact'],0);self.assertEqual(s['ambiguous'],1)

    def test_absent_prediction_and_oov_stay_in_denominator(self):
        s=score(reference('C:11'),[]);self.assertEqual(s['n'],1);self.assertEqual(s['oov'],1);self.assertEqual(s['exact'],0)

    def test_past_boundary_mask_and_no_chord(self):
        stats,_=collect([], [.01,.5,1.99,2.5],[dict(time=0,duration=2,value='C:maj'),dict(time=2,duration=2,value='N')],'guitarset')
        self.assertEqual(stats['counts']['A']['n'],1);self.assertEqual(stats['excluded']['N_or_X'],1)


if __name__=='__main__':unittest.main()
