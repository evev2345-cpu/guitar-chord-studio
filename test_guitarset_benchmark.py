import unittest
import numpy as np
from guitarset_benchmark import parse_chord,rank_saliences,TEMPLATES,evaluate_pitches,evaluate_layer,load_reference
from harmony_engine import provisional_audio_harmony
from joint_evidence_review import ROOT


class GuitarSetBenchmarkTests(unittest.TestCase):
    def test_harte_additions_omissions_and_bass(self):
        self.assertEqual(parse_chord('G:maj(*3,2)/5')['pcs'],(2,7,9))
        self.assertTrue(parse_chord('D#:maj7/1')['representable'])
        self.assertEqual(parse_chord('A:maj/2')['pcs'],(1,4,9,11))
        self.assertFalse(parse_chord('C:(1,5,#11)/b5')['representable'])
        self.assertIsNone(parse_chord('N'))
        with self.assertRaises(ValueError):parse_chord('C:unsupported')

    def test_vectorized_scores_match_current_engine(self):
        sal=np.random.default_rng(4).random((15,12));sal[0]=0;sal[1]=[1,0,0,0,1,0,0,1,0,0,0,0]
        scores,order,usable=rank_saliences(sal)
        data=dict(start_s=0,end_s=20,pitch_class_salience=[dict(time_s=float(i),salience=x.tolist()) for i,x in enumerate(sal)])
        reference=provisional_audio_harmony(data,top_k=192)['salience_frames']
        for i,frame in enumerate(reference):
            self.assertEqual(bool(frame['chord_candidates']),bool(usable[i]))
            if not usable[i]:continue
            actual=[TEMPLATES[j] for j in order[i,:3]]
            self.assertEqual([(c['root_pc'],c['quality']) for c in actual],[(c['root_pc'],c['quality']) for c in frame['chord_candidates'][:3]])
            for c in frame['chord_candidates']:
                j=next(j for j,t in enumerate(TEMPLATES) if t['root_pc']==c['root_pc'] and t['quality']==c['quality'])
                self.assertAlmostEqual(scores[i,j],c['score'],places=13)

    def test_pitch_sets_do_not_double_count_same_note(self):
        notes=[dict(start=0,end=1,midi=40.),dict(start=0,end=1,midi=40.)]
        result=evaluate_pitches([.5],[[40.,52.,59.]],notes)['counts']
        self.assertEqual(result['tp'],1);self.assertEqual(result['fp'],2)
        self.assertEqual(result['false_pitches_near_reference_harmonics'],2)

    def test_unrepresentable_reference_not_silently_excluded(self):
        sal=np.ones((1,12));scores,rank,usable=rank_saliences(sal)
        result=evaluate_layer([.5],rank,scores,usable,[dict(time=0,duration=1,value='C:(1,5,#11)/b5')])
        self.assertEqual(result['counts']['evaluated'],1)
        self.assertEqual(result['counts'].get('representable',0),0)
        self.assertEqual(result['counts']['top1'],0)

    def test_real_reference_layers_remain_distinct(self):
        layers,notes=load_reference(ROOT/'GuitarSet/annotation/00_BN1-129-Eb_comp.jams')
        self.assertEqual(set(layers),{'nominal','performed'})
        self.assertNotEqual(layers['nominal'][0]['value'],layers['performed'][0]['value'])
        self.assertEqual({n['string_source'] for n in notes},set('012345'))

    def test_completed_run_keeps_oov_and_known_issue_accounting(self):
        from joint_evidence_review import read
        path=ROOT/'dataset/integration_review/runs/guitarset_benchmark_20261105_v1/summary.json'
        if not path.exists():self.skipTest('Completed corpus run not available')
        data=read(path)
        self.assertEqual(data['processed_files'],180)
        self.assertEqual(data['scopes']['primary_without_known_timing']['files'],178)
        self.assertEqual(set(data['known_timing_issue_files']),{'04_BN3-154-E_comp','04_Jazz1-200-B_comp'})
        for branch in data['scopes']['primary_without_known_timing']['branches'].values():
            nominal,performed=branch['nominal'],branch['performed']
            self.assertEqual(nominal['counts']['evaluated'],performed['counts']['evaluated'])
            self.assertLess(performed['counts']['representable'],performed['counts']['evaluated'])
            self.assertEqual(performed['unparsed'],{})
            for layer in [nominal,performed]:
                self.assertLessEqual(layer['counts']['top1'],layer['counts']['top3'])
                self.assertLessEqual(layer['counts']['top3'],layer['counts']['representable'])


if __name__=='__main__':unittest.main()
