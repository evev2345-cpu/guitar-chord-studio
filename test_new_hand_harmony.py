import unittest
import numpy as np
from compare_new_hand_harmony import rerank
from harmony_engine import provisional_audio_harmony,QUALITIES
from joint_evidence_review import ROOT,read


class NewHandHarmonyTests(unittest.TestCase):
    def test_audio_dictionary_expansion_preserves_existing_top3(self):
        data=dict(start_s=0,end_s=1,pitch_class_salience=[dict(time_s=.5,salience=[1,0,0,0,1,0,0,1,0,0,0,0])])
        old=provisional_audio_harmony(data)['salience_frames'][0]['chord_candidates']
        full=provisional_audio_harmony(data,top_k=192)['salience_frames'][0]['chord_candidates']
        self.assertEqual(old,full[:3]);self.assertEqual(len(full),12*len(QUALITIES))

    def test_visual_can_rerank_without_creating_audio_candidates(self):
        candidates=[dict(root_pc=0,quality='major',score=.6),dict(root_pc=2,quality='major',score=.59)]
        mass=np.zeros(12);mass[6]=1
        result=rerank(candidates,mass,.2)
        self.assertEqual(result[0]['root_pc'],2)
        self.assertEqual(len(result),len(candidates))

    def test_actual_sources_mass_and_withheld_contracts(self):
        d=read(ROOT/'dataset/integration_review/runs/new_hand_harmony_20261105_v3/result.json')
        self.assertEqual(len(d['frames']),18)
        self.assertFalse(d['production_gates_modified'])
        for r in d['frames']:
            self.assertEqual(r['conservative_fusion'],r['audio_only'])
            self.assertLessEqual(abs(r['audio_feature_delta_s']),.01)
            self.assertTrue(r['audio_support_s'][0]<=r['frame_pts_s']<r['audio_support_s'][1])
            self.assertEqual(r['ground_truth_status'],'no_independent_chord_reference')
            for s in r['exploratory_scenarios']:
                self.assertTrue(0<=sum(s['pc_mass'])<=1+1e-8)
                self.assertNotIn('middle',[f['finger'] for f in s['fingers']])
                for f in s['fingers']:self.assertAlmostEqual(f['mass_total'],1)
                if s['missing_visual']:self.assertEqual(s['rankings']['80audio_20visual'],r['audio_only'])
        missing=next(r for r in d['frames'] if r['frame_index']==4823)
        for s in missing['exploratory_scenarios']:
            self.assertTrue(s['missing_visual'])
            self.assertEqual(s['rankings']['80audio_20visual'],missing['audio_only'])


if __name__=='__main__':unittest.main()
