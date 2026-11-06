import unittest
import numpy as np
from sweep_bandcut_vision_weights import band_cut,LOW_HZ,HIGH_HZ
from audio_analysis import features
from joint_evidence_review import ROOT,read


class BandcutSweepTests(unittest.TestCase):
    def test_stereo_cut_rejects_outside_tones_without_delaying_inside(self):
        rate=8000;t=np.arange(rate)/rate
        inside=np.sin(2*np.pi*440*t)
        x=inside+np.sin(2*np.pi*50*t)+np.sin(2*np.pi*2000*t)
        result=band_cut(np.c_[x,-x],rate)
        np.testing.assert_allclose(result[:,0],inside,atol=1e-11)
        np.testing.assert_allclose(result[:,1],-inside,atol=1e-11)
        self.assertEqual(result.shape,(rate,2))

    def test_peak_candidates_obey_requested_band(self):
        rate=44100;t=np.arange(rate)/rate
        x=np.sin(2*np.pi*440*t)+np.sin(2*np.pi*1600*t)+np.sin(2*np.pi*65*t)
        evidence,_=features(x,rate,min_frequency=LOW_HZ,max_frequency=HIGH_HZ)
        self.assertTrue(evidence['pitch_candidates'])
        self.assertTrue(all(LOW_HZ<=p['frequency_hz']<=HIGH_HZ for p in evidence['pitch_candidates']))
        with self.assertRaises(ValueError):features(x,rate,min_frequency=2000,max_frequency=1000)

    def test_actual_sweep_same_labels_and_all_ratios(self):
        d=read(ROOT/'dataset/integration_review/runs/bandcut_weight_sweep_20261105_v1/result.json')
        base=read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/result.json')
        self.assertEqual(len(d['summary']),11);self.assertEqual(len(d['frames']),9)
        self.assertEqual(d['provenance']['references_sha256'],base['reference_sha256'])
        self.assertFalse(d['production_gates_modified'])
        for old,new in zip(base['frames'],d['frames']):
            self.assertEqual(old['visual_pc_mass'],new['visual_pc_mass'])
            self.assertEqual(old['reference'],new['reference'])
            for vision in range(11):
                self.assertIn(f'{vision}:{10-vision}',new['ratios'])
            self.assertEqual(new['ratios']['0:10']['cut']['top3'][0]['score'],new['cut_audio'][0]['score'])
        for s in d['summary']:
            self.assertAlmostEqual(s['vision_weight']+s['audio_weight'],1)
            for branch in ['cut','uncut']:
                for metric in ['exact_top1','exact_top3','root_top1']:
                    self.assertEqual(s[branch][metric],sum(r['ratios'][s['vision_to_audio']][branch]['evaluation'][metric] for r in d['frames']))


if __name__=='__main__':unittest.main()
