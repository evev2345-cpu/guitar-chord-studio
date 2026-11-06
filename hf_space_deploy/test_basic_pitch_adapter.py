import unittest
import numpy as np
from basic_pitch_adapter import sample_prediction,build_evidence

class AdapterTests(unittest.TestCase):
    def test_range_and_threshold(self):
        v=np.zeros((2,88));v[0,[37-21,38-21,88-21,89-21]]=[1,.3,.5,1]
        sal,d,notes=sample_prediction([0,.01],v,[],[0])
        self.assertEqual(notes,[[38,88]]);self.assertAlmostEqual(sal[0].sum(),1)
        self.assertEqual(set(np.where(sal[0]>0)[0]),{2,4})
    def test_events_end_exclusive_and_octave_merge(self):
        ev=[dict(start_s=0,end_s=.01,midi=60,amplitude=.5),dict(start_s=0,end_s=.02,midi=72,amplitude=.4)]
        s,_,n=sample_prediction([0,.01],np.zeros((2,88)),ev,[.01],'events')
        self.assertEqual(n,[[72]]);self.assertEqual(s[0,0],1)
    def test_silence(self):
        s,_,n=sample_prediction([0,.01],np.zeros((2,88)),[],[0])
        self.assertFalse(s.any());self.assertEqual(n,[[]])
    def test_validation(self):
        with self.assertRaises(ValueError):sample_prediction([0,.01],np.zeros((2,88)),[],[1])
        with self.assertRaises(ValueError):sample_prediction([.01,0],np.zeros((2,88)),[],[0])
        with self.assertRaises(ValueError):sample_prediction([0,.01],np.full((2,88),np.nan),[],[0])
    def test_export_offset_no_confirmation(self):
        v=np.zeros((20,88));v[:,60-21]=.8
        e=build_evidence(np.arange(20)*.01,v,[dict(start_s=0,end_s=.1,midi=60,amplitude=.8)],source_id='video',start_s=194.,duration_s=.2)
        self.assertEqual(e['pitch_class_salience'][0]['time_s'],194.)
        self.assertEqual(e['pitch_candidates'][0]['end_s'],194.1)
        self.assertEqual(e['pitch_candidates'][0]['pitch_status'],'provisional')
        self.assertEqual(e['evidence']['observed_audio_notes'],[])

if __name__=='__main__':unittest.main()
