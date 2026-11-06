import unittest
import numpy as np
from audio_analysis import features, short_onsets, persistent_peaks, evaluate_onsets, time_local_evidence

class AudioTests(unittest.TestCase):
    rate=44100
    def tone(self,hz):
        return .3*np.sin(2*np.pi*hz*np.arange(self.rate)/self.rate)
    def test_single_tone_frequency(self):
        e,_=features(self.tone(440),self.rate,3)
        self.assertTrue(all(abs(p['frequency_hz']-440)<1 for p in e['pitch_candidates']))
        self.assertGreater(e['pitch_candidates'][0]['start_s'],2.999)
    def test_mixture_keeps_both_octaves(self):
        e,_=features(self.tone(220)+self.tone(440),self.rate)
        hz=[p['frequency_hz'] for p in e['pitch_candidates']]
        for f in [220,440]: self.assertTrue(any(abs(v-f)<1 for v in hz))
    def test_silence_not_muted(self):
        e,_=features(np.zeros(self.rate),self.rate)
        self.assertEqual(e['pitch_candidates'],[])
        self.assertEqual(e['onsets'],[])
        self.assertEqual({v['acoustic_state'] for v in e['acoustic_events']},{'silent'})
    def test_attack_and_decay(self):
        x=np.zeros(self.rate*2); n=self.rate
        x[n:n+self.rate]=self.tone(330)*np.exp(-np.arange(n)/self.rate*8)
        e,_=features(x,self.rate,3)
        self.assertTrue(any(abs(o['time_s']-4)<.1 for o in e['onsets']))
        self.assertTrue(all(p['offset_status']=='analysis_window_only' for p in e['pitch_candidates']))
    def test_noise_not_intentional_mute(self):
        x=np.random.default_rng(1).normal(0,.1,self.rate)
        e,_=features(x,self.rate)
        self.assertEqual({v['acoustic_state'] for v in e['acoustic_events']},{'unknown'})
    def test_invalid(self):
        with self.assertRaises(ValueError): features(np.zeros(4),self.rate)


class ReviewTests(unittest.TestCase):
    def test_one_to_one_duplicates_and_missing_reference(self):
        e=evaluate_onsets([1.,1.01,2.],[1.,3.],reviewed=True)
        self.assertEqual((e['true_positive'],e['false_positive'],e['false_negative']),(1,2,1))
        self.assertIsNone(evaluate_onsets([1.],[])['precision'])
    def test_matching_maximizes_count_before_error(self):
        e=evaluate_onsets([1.,1.04],[1.03,1.08],reviewed=True)
        self.assertEqual(e['true_positive'],2)
    def test_short_window_attack_localization(self):
        sr=44100; t=np.arange(sr)/sr
        x=np.zeros(sr);x[sr//2:]=.3*np.sin(2*np.pi*440*t[sr//2:])
        events=short_onsets(x,sr,3.)
        self.assertTrue(any(abs(e['time_s']-3.5)<.025 for e in events))
    def test_persistence_gaps_and_harmonic_ambiguity(self):
        peaks=[]
        for hz,midi in [(220,57),(440,69)]:
            for k in range(6):
                peaks.append(dict(event_id=f'{hz}_{k}',start_s=k*.01,end_s=k*.01+.1,
                                  frequency_hz=hz,midi=midi,score=.5))
        tracks=persistent_peaks(peaks,.01)
        self.assertEqual(len(tracks),2)
        self.assertEqual(tracks[1]['harmonic_ambiguities'][0]['possible_harmonic'],2)
        self.assertEqual(tracks[1]['pitch_status'],'persistent_spectral_peak_candidate')
    def test_local_fixture_no_boundary_crossing_or_promotion(self):
        import json
        from pathlib import Path
        p=Path('dataset/audio_analysis/runs/clip_003_012_pts_v3/evidence.json')
        if not p.exists(): self.skipTest('real run unavailable')
        r=json.loads(p.read_text()); out=time_local_evidence(r,5.05,5.35)
        self.assertIsNone(out['capo']);self.assertEqual(out['evidence']['observed_audio_notes'],[])
        self.assertTrue(out['pitch_candidates'])
        self.assertTrue(all(5.05<=x['start_s']<x['end_s']<=5.35 for x in out['pitch_candidates']))
        self.assertTrue(all(x['pitch_status']=='spectral_peak_candidate' for x in out['pitch_candidates']))
        with self.assertRaises(ValueError):time_local_evidence(r,2.,4.)


class TimelineTests(unittest.TestCase):
    def test_pts_gap_changes_raw_sample_mapping(self):
        from audio_extract import decoded_timeline,sample_interval
        frames=[{'best_effort_timestamp_time':0,'nb_samples':1024},
                {'best_effort_timestamp_time':.064898,'nb_samples':1024},
                {'best_effort_timestamp_time':.088118,'nb_samples':1024}]
        segments,n=decoded_timeline(frames,44100)
        self.assertEqual(n,3072);self.assertEqual(len(segments),2)
        first,last,offset=sample_interval(segments,.07,.08,44100)
        self.assertAlmostEqual(offset,.04167804535)
        self.assertAlmostEqual(first/44100+offset,.07,delta=.5/44100)
        with self.assertRaises(ValueError):sample_interval(segments,.01,.08,44100)
    def test_real_pts_reextraction_preserves_pcm(self):
        from pathlib import Path
        from scipy.io import wavfile
        import json
        root=Path('dataset/audio_analysis/runs')
        new=root/'clip_003_012_pts_v3'; old=root/'clip_003_012'
        if not new.exists() or not old.exists(): self.skipTest('real runs unavailable')
        m=json.loads((new/'manifest.json').read_text());o=json.loads((old/'manifest.json').read_text())
        self.assertEqual(m['source_id'],o['source_id'])
        delta=o['clip_first_sample']-m['clip_first_sample']
        self.assertEqual(delta,1838)
        sr,a=wavfile.read(old/'original.wav');sr,b=wavfile.read(new/'original.wav')
        np.testing.assert_array_equal(a[:-delta],b[delta:])


class MixtureTests(unittest.TestCase):
    def test_soft_masks_reconstruct_with_no_sample_shift(self):
        from audio_mixture_diagnostics import hps_components
        sr=44100;t=np.arange(sr)/sr
        x=np.column_stack([.2*np.sin(2*np.pi*220*t),.3*np.sin(2*np.pi*330*t)])
        x[20000]+=1
        h,p=hps_components(x,sr)
        self.assertEqual(h.shape,x.shape);self.assertEqual(p.shape,x.shape)
        np.testing.assert_allclose(h+p,x,atol=1e-12)
    def test_center_cancellation_is_not_instrument_identity(self):
        from audio_mixture_diagnostics import channel_diagnostics
        x=np.arange(100,dtype=float)/100
        r=channel_diagnostics(np.column_stack([x,x]))
        self.assertEqual(r['side_energy_ratio'],0)
        self.assertEqual(r['mid_energy_ratio'],1)
    def test_listening_review_source_mismatch_rejected(self):
        from audio_mixture_diagnostics import validate_listening_review
        m=dict(source_id='a',timebase='source_video_seconds',sample_rate=44100,start_s=3,end_s=12)
        r=dict(source_id='b',timebase='source_video_seconds',start_s=3,end_s=12)
        with self.assertRaises(ValueError):validate_listening_review(m,r)
    def test_actual_mixture_fixture_preserves_unknown_attribution(self):
        import json
        from pathlib import Path
        p=Path('dataset/audio_analysis/runs/clip_003_012_mix_v4/harmonic_component/fixtures/audio_5.05_5.35.json')
        if not p.exists():self.skipTest('mixture run unavailable')
        r=json.loads(p.read_text());self.assertEqual(r['source_identity']['input_mix'],'vocal_and_guitar')
        local=time_local_evidence(r,5.05,5.35)
        self.assertEqual(local['source_identity']['instrument_attribution'],'unknown')
        self.assertEqual(local['evidence']['observed_audio_notes'],[])
        self.assertIsNone(local['capo'])
        self.assertTrue(all(p['instrument_attribution']=='unknown' and p['pitch_status']=='spectral_peak_candidate' for p in local['pitch_candidates']))


class StemTests(unittest.TestCase):
    def test_vocal_coincidence_is_not_guitar_attribution(self):
        from audio_stem_analysis import vocal_coincidences
        p=dict(event_id='a',frequency_hz=440.,start_s=3.,instrument_attribution='unknown')
        record=dict(start_s=3.,provenance=dict(hop_samples=441,window_samples=8192,window_support_s=8192/44100),pitch_candidates=[p])
        vocals=dict(pitch_candidates=[dict(event_id='v0',frequency_hz=440.,start_s=3.),dict(event_id='v1',frequency_hz=440.,start_s=3.01)])
        vocal_coincidences(record,vocals)
        self.assertEqual(p['coincident_vocal_stem_evidence_ids'],['v0'])
        self.assertEqual(p['instrument_attribution'],'unknown')
    def test_stem_event_namespacing_preserves_track_links(self):
        from audio_stem_analysis import namespace_events
        r=dict(pitch_candidates=[dict(event_id='p')],pitch_tracks=[dict(event_id='t',evidence_ids=['p'],harmonic_ambiguities=[dict(lower_event_id='t')])])
        namespace_events(r,'accompaniment')
        self.assertEqual(r['pitch_tracks'][0]['evidence_ids'],['accompaniment:p'])
        self.assertEqual(r['pitch_tracks'][0]['harmonic_ambiguities'][0]['lower_event_id'],'accompaniment:t')
        self.assertTrue(r['pitch_candidates'][0]['derived_from_separation'])
    def test_actual_stem_fixture_support_and_identity(self):
        import json
        from pathlib import Path
        p=Path('dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5/accompaniment/fixtures/audio_5.05_5.35.json')
        if not p.exists():self.skipTest('stem evidence unavailable')
        r=json.loads(p.read_text());self.assertTrue(r['source_identity']['derived_from_separation'])
        self.assertFalse(r['source_identity']['guitar_isolation_verified'])
        self.assertIsNone(r['capo']);self.assertEqual(r['evidence']['observed_audio_notes'],[])
        ids={x['event_id'] for x in r['pitch_candidates']}
        self.assertTrue(ids)
        for c in r['fingering_comparison_candidates']:
            self.assertTrue(set(c['evidence_ids'])<=ids)
            self.assertIsNone(c['string_num']);self.assertEqual(c['contact'],'unknown')
        self.assertTrue(all(r['start_s']<=x['start_s']<x['end_s']<=r['end_s'] for x in r['pitch_candidates']))

if __name__=='__main__': unittest.main()
