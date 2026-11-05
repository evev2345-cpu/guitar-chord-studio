import copy
import unittest
import json
import tempfile
from pathlib import Path
from harmony_engine import analyze, fret_note, STANDARD, QUALITIES
from harmony_input_adapter import adapt_legacy_hand, adapt_audio


def fixture(midis=()):
    return {'schema_version': 'guitar_evidence.v1', 'run_id': 'unit', 'source_id': None,
            'start_s': 0, 'end_s': 1, 'timebase': 'source_video_seconds',
            'capo': {'fret': 0, 'source': 'manual', 'confirmed': True},
            'evidence': {'manual_notes': [{'midi': m} for m in midis]}}


class HarmonyTests(unittest.TestCase):
    def test_actual_demucs_nine_fixture_replay(self):
        from harmony_demucs_review import replay
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'review'
            summary=replay('dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5',out)
            self.assertEqual(len(summary),9)
            results=json.loads((out/'results.json').read_text(encoding='utf-8'))
            for entry in results:
                result=entry['result']
                self.assertEqual(result['chord_candidates'],[])
                self.assertEqual(result['fingering_hypotheses']['chord_candidates'],[])
                self.assertTrue(result['provisional_audio_harmony']['salience_frames'])
                for frame in result['provisional_audio_harmony']['salience_frames']:
                    for candidate in frame['chord_candidates']:
                        self.assertEqual(candidate['pitch_status'],'provisional')
                        self.assertTrue(candidate['evidence_ids'][0].startswith(result['source_identity']['component']+':'))
            with self.assertRaises(ValueError):
                replay('dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5',out)
    def test_salience_piano_stays_provisional(self):
        f = fixture()
        f['source_context'] = dict(source_identity='accompaniment',derived_from_separation=True,guitar_isolation_verified=False,piano_audible=True)
        f['pitch_class_salience'] = [dict(time_s=.5,salience=[1 if i in (0,4,7) else 0 for i in range(12)])]
        out = analyze(f)
        self.assertEqual(out['chord_candidates'],[])
        frame=out['provisional_audio_harmony']['salience_frames'][0]
        self.assertEqual(frame['chord_candidates'][0]['concert_symbol'],'C')
        self.assertEqual(frame['chord_candidates'][0]['pitch_status'],'provisional')
        self.assertEqual(out['fingering_hypotheses']['chord_candidates'],[])

    def test_salience_time_frames_never_pool(self):
        f = fixture()
        f['pitch_class_salience'] = [dict(time_s=t,salience=[int(i==pc) for i in range(12)]) for t,pc in ((.1,0),(.3,4),(.5,7))]
        out=analyze(f)
        self.assertTrue(all(not x['chord_candidates'] for x in out['provisional_audio_harmony']['salience_frames']))
        f['pitch_class_salience'][0]['salience'][0]=float('nan')
        with self.assertRaises(ValueError): analyze(f)

    def test_tentative_notes_and_parent_separation(self):
        f=fixture()
        f['source_context']={'source_identity':'accompaniment','derived_from_separation':True}
        f['tentative_notes']=[dict(event_id=str(m),midi=m,start_s=0,end_s=1,pitch_status='provisional') for m in (60,64,67)]
        f['evidence']['observed_audio_notes']=[dict(n,pitch_status='confirmed',source_identity='guitar',source_attribution_status='verified') for n in f['tentative_notes']]
        out=analyze(f)
        self.assertEqual(out['chord_candidates'],[])
        self.assertTrue(out['provisional_audio_harmony']['tentative_note_candidates'])
    def test_actual_audio_minimal_contract(self):
        data = json.loads(Path('dataset/harmony_analysis/fixtures/actual_audio_minimal.json').read_text(encoding='utf-8'))
        original = copy.deepcopy(data)
        out = analyze(adapt_audio(data))
        self.assertEqual(out['status'], 'insufficient_evidence')
        self.assertEqual(out['chord_candidates'], [])
        self.assertEqual(out['pitch_candidates'], data['pitch_candidates'])
        self.assertEqual(out['pitch_candidates'][0]['pitch_status'], 'spectral_peak_candidate')
        self.assertEqual(data, original)

    def test_unknown_capo_independent_midi(self):
        for capo in (None, {}, {'fret': None, 'status': 'unknown'}):
            f = fixture([60,64,67]); f['capo'] = capo
            self.assertEqual(analyze(f)['chord_candidates'][0]['concert_symbol'], 'C')
            f['evidence'] = {'string_states':[dict(state='sounding',string=6,relative_fret=0)]}
            self.assertEqual(analyze(f)['status'], 'insufficient_evidence')
        f = fixture([60,64,67]); del f['capo']
        self.assertEqual(analyze(f)['chord_candidates'][0]['concert_symbol'], 'C')

    def test_candidate_in_observed_array_is_not_confirmed(self):
        f = fixture()
        f['evidence']['observed_audio_notes'] = [dict(midi=m,pitch_status='spectral_peak_candidate') for m in (60,64,67)]
        out = analyze(f)
        self.assertEqual(out['chord_candidates'], [])
        self.assertIsNone(out['lowest_detected_midi'])
        self.assertEqual(len(out['evidence']['excluded_note_evidence']),3)

    def test_time_local_no_sequential_chord(self):
        f = fixture()
        f['evidence']['observed_audio_notes'] = [dict(event_id=str(i),midi=m,start_s=i/3,end_s=(i+1)/3,pitch_status='confirmed') for i,m in enumerate((60,64,67))]
        self.assertEqual(analyze(f)['chord_candidates'], [])
        f['evidence']['observed_audio_notes'] = [dict(event_id=str(m),midi=m,start_s=0,end_s=1,pitch_status='confirmed',source_identity='guitar',source_attribution_status='verified') for m in (60,64,67)]
        out = analyze(adapt_audio(f,start_s=.2,end_s=.3,selection_source='synthetic_simultaneous_support'))
        self.assertEqual(out['chord_candidates'][0]['concert_symbol'],'C')
        self.assertEqual(out['chord_candidates'][0]['evidence_ids'], ['60','64','67'])

    def test_timed_string_states_not_pooled(self):
        f = fixture()
        f['evidence']['string_states'] = [dict(state='sounding',string=s,relative_fret=r,
            start_s=i/3,end_s=(i+1)/3) for i,(s,r) in enumerate(((5,3),(4,2),(3,0)))]
        out = analyze(f)
        self.assertEqual(out['chord_candidates'], [])
        self.assertEqual(len(out['evidence']['excluded_note_evidence']),3)

    def test_window_filter_and_source_required(self):
        f = json.loads(Path('dataset/harmony_analysis/fixtures/actual_audio_minimal.json').read_text(encoding='utf-8'))
        out = adapt_audio(f,start_s=3,end_s=3.2,selection_source='contract_smoke_not_stability_review')
        self.assertTrue(out['pitch_candidates'])
        self.assertEqual(analyze(out)['status'],'insufficient_evidence')
        with self.assertRaises(ValueError):
            adapt_audio(f,start_s=3,end_s=4)
        with self.assertRaises(ValueError):
            adapt_audio(f,start_s=2,end_s=4,selection_source='invalid')
        with self.assertRaises(ValueError):
            adapt_audio(fixture([60,64,67]),start_s=.1,end_s=.2,selection_source='untimed')

    def test_capo_physical_relative(self):
        for capo in (0, 1, 2):
            for string in range(1, 7):
                for r in (0, 2, 7):
                    a = fret_note(dict(state='sounding', string=string, relative_fret=r), STANDARD, capo)
                    b = fret_note(dict(state='sounding', string=string, physical_fret=capo+r), STANDARD, capo)
                    self.assertEqual(a, b)
                    self.assertEqual(a['midi'], STANDARD[6-string]+capo+r)
        self.assertEqual(fret_note(dict(state='sounding', string=6, relative_fret=0), STANDARD, 1)['note_name'], 'F2')

    def test_unknown_and_x(self):
        for state in ('unknown', 'muted', 'unplayed'):
            self.assertIsNone(fret_note(dict(state=state, relative_fret='X'), STANDARD, 0)['midi'])
        for capo, p in ((None, 2), (2, 1)):
            self.assertIsNone(fret_note(dict(state='possible', string=6, physical_fret=p), STANDARD, capo)['midi'])

    def test_invalid_frets(self):
        for r in (-1, 'X', True):
            with self.assertRaises(ValueError):
                fret_note(dict(state='sounding', string=6, relative_fret=r), STANDARD, 1)
        with self.assertRaises(ValueError):
            fret_note(dict(state='sounding', string=6, relative_fret=0, physical_fret=0), STANDARD, 1)

    def test_em7_g6(self):
        out = analyze(fixture([52, 55, 59, 62]))
        self.assertEqual(out['status'], 'ambiguous')
        self.assertTrue({'Em7', 'G6'} <= {c['concert_symbol'] for c in out['chord_candidates']})
        self.assertTrue(all(c['bass_midi'] is None for c in out['chord_candidates']))

    def test_duplicates(self):
        self.assertEqual(analyze(fixture([60,64,67]))['chord_candidates'],
                         [{**c, 'evidence_ids': ['note_0','note_1','note_2']} for c in
                          analyze(fixture([60,64,67,72]))['chord_candidates']])

    def test_confirmed_inversion(self):
        f = fixture([52,55,60])
        self.assertEqual(analyze(f)['chord_candidates'][0]['concert_symbol'], 'C')
        f['evidence']['confirmed_bass_midi'] = 52
        self.assertEqual(analyze(f)['chord_candidates'][0]['concert_symbol'], 'C/E')

    def test_insufficient(self):
        for notes in ([], [60], [60,67], [60,72]):
            self.assertEqual(analyze(fixture(notes))['chord_candidates'], [])

    def test_possible_never_observed(self):
        f = fixture()
        f['evidence']['string_states'] = [dict(state='possible',string=6,relative_fret=0)]
        out = analyze(f)
        self.assertEqual(out['chord_candidates'], [])
        self.assertEqual(out['lowest_possible_fingering_midi'], 40)
        self.assertIsNone(out['confirmed_bass_midi'])

    def test_g_shape_capo_one(self):
        f = fixture()
        f['capo']['fret'] = 1
        f['evidence']['string_states'] = [dict(state='sounding',string=s,relative_fret=r)
            for s,r in zip((6,5,4,3,2,1),(3,2,0,0,0,3))]
        out = analyze(f)
        self.assertEqual(out['chord_candidates'][0]['concert_symbol'], 'Ab')
        self.assertIsNone(out['chord_candidates'][0]['shape_symbol'])

    def test_conflict(self):
        f = fixture()
        f['evidence'].update(observed_audio_notes=[{'midi':m,'source_identity':'guitar','source_attribution_status':'verified'} for m in (60,64,67)],
            string_states=[dict(state='sounding',string=6,relative_fret=0)])
        self.assertEqual(analyze(f)['status'], 'evidence_conflict')

    def test_dictionary_exact_sets(self):
        for quality, intervals in QUALITIES.items():
            out = analyze(fixture([60+i for i in intervals]))
            if quality == '5':
                self.assertEqual(out['chord_candidates'], [])
            else:
                self.assertTrue(any(c['quality']==quality and c['root_pc']==0 and c['score']==1
                                    for c in out['chord_candidates']), quality)

    def test_adapter_no_reference_leak(self):
        f = adapt_legacy_hand('dataset/chord_video_review/case_0005.00_tracking.json')
        before = copy.deepcopy(f)
        out = analyze(f)
        self.assertEqual(f, before)
        self.assertNotIn('chord_shape_reference', str(f))
        self.assertEqual(out['chord_candidates'], [])
        self.assertTrue(out['evidence']['hand_position_candidates'])

    def test_source_identity_and_pitch_status_are_independent(self):
        for identity in ('mixed','vocal','accompaniment','unknown','guitar'):
            for status in ('spectral_peak_candidate','provisional','confirmed'):
                f = fixture()
                f['evidence']['observed_audio_notes'] = [dict(midi=m,pitch_status=status,source_identity=identity) for m in (60,64,67)]
                out = analyze(f)
                self.assertEqual(out['chord_candidates'], [])
                self.assertEqual(bool(out['mixed_audio_harmony']['chord_candidates']), status=='confirmed')

    def test_separated_stem_never_automatically_confirms_guitar(self):
        f = fixture()
        f['evidence']['observed_audio_notes'] = [dict(midi=m,pitch_status='confirmed',source_identity='guitar',source_attribution_status='verified',derived_from_separation=True) for m in (60,64,67)]
        out = analyze(f)
        self.assertEqual(out['chord_candidates'], [])
        self.assertTrue(out['mixed_audio_harmony']['chord_candidates'])

    def test_listening_review_identity_validation(self):
        f = fixture(); f['source_id']='source'
        review = dict(source_id='source',timebase=f['timebase'],start_s=0,end_s=1,instrument_mix='vocal_and_guitar')
        out = adapt_audio(f,listening_review=review)
        self.assertEqual(out['source_context']['source_identity'],'mixed')
        review['source_id']='other'
        with self.assertRaises(ValueError):
            adapt_audio(f,listening_review=review)

    def test_actual_pts_v3_mixed_fixture(self):
        f = json.loads(Path('dataset/harmony_analysis/fixtures/actual_pts_v3_mixed.json').read_text(encoding='utf-8'))
        out = analyze(adapt_audio(f))
        self.assertEqual(out['source_context']['instrument_mix'],'vocal_and_guitar')
        self.assertEqual(out['status'],'insufficient_evidence')
        self.assertEqual(out['chord_candidates'],[])
        self.assertEqual(out['pitch_candidates'],f['pitch_candidates'])
        self.assertEqual(out['mixed_audio_harmony']['status'],'insufficient_evidence')

    def test_possible_fingering_is_separate_hypothesis(self):
        f = fixture()
        f['evidence']['string_states'] = [dict(state='possible',string=s,relative_fret=r) for s,r in ((5,3),(4,2),(3,0))]
        out = analyze(f)
        self.assertEqual(out['chord_candidates'], [])
        self.assertEqual(out['fingering_hypotheses']['chord_candidates'][0]['concert_symbol'],'C')


if __name__ == '__main__':
    unittest.main()
