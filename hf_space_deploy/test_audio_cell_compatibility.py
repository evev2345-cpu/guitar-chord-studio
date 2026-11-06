import copy
import unittest
from audio_cell_compatibility import compare, possible_pitch, STANDARD

SID='a'*64
TUNING=dict(midi_6_to_1=STANDARD,status='assumed',source='test_standard')

def fixture():
    cell=dict(cell_id='s1p5',virtual_string_num=1,physical_fret_candidate=5,is_virtual=True,estimated=True)
    cells=dict(source_id=SID,timebase='source_video_seconds',start_s=3.,end_s=3.3,grid_id='synthetic',grid_version='v1',data_origin='synthetic_cell_hypotheses',tuning=TUNING,capo=None,cells=[cell])
    audio=dict(source_id=SID,timebase='source_video_seconds',start_s=3.,end_s=4.,run_id='test',provenance=dict(window_support_s=.1),
        pitch_candidates=[dict(event_id='p',frequency_hz=440.,midi=69.,start_s=3.05,end_s=3.15,score=.8,score_type='relative_spectral_peak_amplitude',pitch_status='spectral_peak_candidate',frequency_resolution_hz=5.38)],
        pitch_tracks=[dict(event_id='t',frequency_hz=440.,start_s=3.,end_s=3.3,score=.6,score_type='median_relative_spectral_peak_amplitude',pitch_status='persistent_spectral_peak_candidate',evidence_ids=['p'],harmonic_ambiguities=[])],
        pitch_class_salience=[dict(event_id='pc',time_s=3.1,salience=[0.]*9+[1.]+[0.]*2)])
    return cells,audio

class CompatibilityTests(unittest.TestCase):
    def test_physical_fret_not_double_capo(self):
        c=dict(virtual_string_num=6,physical_fret_candidate=3,relative_fret_candidate=2,is_virtual=True,estimated=True)
        self.assertEqual(possible_pitch(c,TUNING,dict(fret=1,status='assumed'))['midi'],43)
        with self.assertRaises(ValueError):possible_pitch(c,TUNING,dict(fret=2,status='assumed'))
    def test_unknown_relative_capo_and_tuning(self):
        c=dict(virtual_string_num=6,relative_fret_candidate=0,is_virtual=True,estimated=True)
        self.assertIsNone(possible_pitch(c,TUNING,None)['midi'])
        self.assertIsNone(possible_pitch(c,TUNING,dict(fret=None,status='unknown'))['midi'])
        c['physical_fret_candidate']=2
        self.assertIsNone(possible_pitch(c,None,None)['midi'])
        self.assertEqual(possible_pitch(c,TUNING,None)['midi'],42)
    def test_exact_support_and_unknown_instrument(self):
        c,a=fixture();r=compare(c,a)['cells'][0]
        self.assertAlmostEqual(r['exact_frequency_score'],.8)
        self.assertAlmostEqual(r['persistent_frequency_score'],.6)
        self.assertEqual(r['pitch_class_score'],1.)
        self.assertEqual(r['contact'],'unknown');self.assertEqual(r['instrument_attribution'],'unknown')
    def test_octave_pc_not_promoted(self):
        c,a=fixture();c['cells'][0].update(virtual_string_num=3,physical_fret_candidate=2)
        r=compare(c,a)['cells'][0] # G3+2=A3, same PC as A4
        self.assertEqual(r['exact_frequency_score'],0.)
        self.assertEqual(r['pitch_class_score'],1.)
        self.assertEqual(r['octave_alternatives'][0]['octave_difference'],1)
        self.assertEqual(r['status'],'pitch_class_only_support')
    def test_missing_vs_empty(self):
        c,a=fixture();del a['pitch_candidates'];r=compare(c,a)['cells'][0]
        self.assertIsNone(r['audio_compatibility_score']);self.assertEqual(r['status'],'missing_frequency_evidence')
        a['pitch_candidates']=[];r=compare(c,a)['cells'][0]
        self.assertEqual(r['audio_compatibility_score'],0.)
        self.assertEqual(r['evidence_availability']['pitch_candidates'],'present_empty')
        self.assertEqual(r['sounding'],'unknown')
    def test_time_and_source_mismatch_rejected(self):
        c,a=fixture();a['source_id']='b'*64
        with self.assertRaises(ValueError):compare(c,a)
        c,a=fixture();c['end_s']=5.
        with self.assertRaises(ValueError):compare(c,a)
    def test_partial_window_peak_withheld(self):
        c,a=fixture();a['pitch_candidates'][0]['start_s']=2.99
        self.assertEqual(compare(c,a)['cells'][0]['exact_frequency_score'],0)
    def test_frequency_cents_and_score_range(self):
        c,a=fixture();a['pitch_candidates'][0]['frequency_hz']=440*2**(25/1200)
        r=compare(c,a)['cells'][0];self.assertAlmostEqual(r['frequency_matches'][0]['cents_error'],25)
        self.assertAlmostEqual(r['exact_frequency_score'],.4)
        a['pitch_candidates'][0]['score']=1.1
        with self.assertRaises(ValueError):compare(c,a)
    def test_invalid_real_frame_context_rejected(self):
        c,a=fixture();c['data_origin']='real_grid'
        with self.assertRaises(ValueError):compare(c,a)
        c.update(frame_index=124,frame_pts_s=3.1,frame_pixel_sha256='c'*64)
        self.assertEqual(compare(c,a)['grid_context']['frame_index'],124)
        c['frame_pts_s']=3.5
        with self.assertRaises(ValueError):compare(c,a)
    def test_no_mutation_or_duplicate_ids(self):
        c,a=fixture();before=copy.deepcopy((c,a));compare(c,a);self.assertEqual((c,a),before)
        c['cells']*=2
        with self.assertRaises(ValueError):compare(c,a)
    def test_no_frame_support_no_pc_claim(self):
        c,a=fixture();a['provenance']={}
        with self.assertRaises(ValueError):compare(c,a)


    def test_same_note_multiple_strings_remain_ambiguous(self):
        c,a=fixture();c['cells']=[dict(cell_id='a',virtual_string_num=1,physical_fret_candidate=5,is_virtual=True,estimated=True),dict(cell_id='b',virtual_string_num=2,physical_fret_candidate=10,is_virtual=True,estimated=True)]
        rows=compare(c,a)['cells']
        self.assertEqual(rows[0]['expected_pitch']['midi'],rows[1]['expected_pitch']['midi'])
        self.assertEqual(rows[0]['exact_frequency_score'],rows[1]['exact_frequency_score'])
        self.assertTrue(all(x['contact']=='unknown' for x in rows))
    def test_unknown_score_semantics_rejected(self):
        c,a=fixture();a['pitch_candidates'][0]['score_type']='unknown_scale'
        with self.assertRaises(ValueError):compare(c,a)
    def test_actual_grid_audio_fixture_provenance_and_links(self):
        import json
        from pathlib import Path
        p=Path('dataset/audio_analysis/runs/audio_cell_actual_grid_20261103_v2/fixtures/frame_124_accompaniment.json')
        if not p.exists():self.skipTest('actual grid/audio run unavailable')
        r=json.loads(p.read_text());self.assertEqual(r['data_origin'],'actual_upstream_virtual_grid_hypotheses')
        self.assertEqual(r['frame_index'],124);self.assertEqual(r['grid_context']['geometry_status'],'suspect')
        self.assertFalse(r['grid_context']['contact_fret_decision_allowed'])
        self.assertTrue(r['provenance']['frame_bgr_hash_verified'])
        self.assertEqual(len(r['cells']),6)
        for c in r['cells']:
            self.assertEqual(c['contact'],'unknown')
            self.assertTrue(0<=c['exact_frequency_score']<=1)
            for hit in c['frequency_matches']:
                self.assertTrue(hit['event_id'].startswith('accompaniment:'))
                self.assertTrue(r['start_s']<=hit['start_s']<hit['end_s']<=r['end_s'])


    def test_fusion_adapter_keeps_null_and_explicit_zero(self):
        from audio_cell_compatibility import to_fusion_audio
        c,a=fixture();r=compare(c,a);out=to_fusion_audio(r)
        self.assertEqual(out['score_type'],'normalized_compatibility_0_1')
        self.assertAlmostEqual(out['cells']['s1p5']['score'],.8)
        self.assertEqual(out['cells']['s1p5']['evidence_ids'],['p'])
        del a['pitch_candidates'];out=to_fusion_audio(compare(c,a))
        self.assertIsNone(out['cells']['s1p5']['score'])
    def test_real_multimodel_bundle_ids_and_d_adapter(self):
        import json
        from pathlib import Path
        from virtual_string_grid import assert_grid_compatible
        root=Path('dataset/audio_analysis/runs/audio_cell_actual_grid_20261103_v3');p=root/'bundle.json'
        if not p.exists():self.skipTest('multimodel run unavailable')
        bundle=json.loads(p.read_text());self.assertEqual(bundle['audio_comparisons'],54)
        keys=set()
        for frame in bundle['frames']:
            self.assertEqual(len(frame['models']),6)
            for model in frame['models']:
                self.assertNotIn(model['grid_id'],keys);keys.add(model['grid_id'])
                grid=json.loads(Path(model['grid_json']).read_text())
                for component,paths in model['components'].items():
                    r=json.loads(Path(paths['result']).read_text());assert_grid_compatible(grid,r)
                    adapter=json.loads(Path(paths['fusion_audio']).read_text())
                    self.assertEqual(adapter['grid_id'],grid['grid_id'])
                    self.assertEqual(len(adapter['cells']),36)
                    self.assertTrue(all(v['score'] is None or 0<=v['score']<=1 for v in adapter['cells'].values()))

if __name__=='__main__':unittest.main()
