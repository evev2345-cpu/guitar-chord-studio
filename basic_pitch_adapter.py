"""Convert fixed pretrained note evidence to the existing chord input contract.

Model activations are not calibrated confidence or verified string/contact data.
The official default frame threshold .3 and D2-E6 output range are fixed here.
"""
import numpy as np

def sample_prediction(frame_times,note_frames,events,sample_times,representation='frames'):
    times=np.asarray(frame_times,float);values=np.asarray(note_frames,float);query=np.asarray(sample_times,float)
    if values.shape!=(len(times),88) or not len(times) or not np.isfinite(values).all() or not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('Invalid model grid')
    if query.ndim!=1 or not np.isfinite(query).all():raise ValueError('Invalid query')
    if representation not in ('frames','events'):raise ValueError('Unknown representation')
    midi=np.arange(21,109);allowed=(midi>=38)&(midi<=88);result=[];deltas=[];note_sets=[]
    for t in query:
        i=int(np.argmin(abs(times-t)))
        if abs(times[i]-t)>.03:raise ValueError('Query outside model support')
        weights=np.zeros(88)
        if representation=='frames':weights=np.where((values[i]>=.3)&allowed,values[i],0.)
        else:
            for e in events:
                if e['start_s']<=t<e['end_s'] and 38<=e['midi']<=88:
                    if not np.isfinite(e['amplitude']) or e['amplitude']<0:raise ValueError('Invalid note amplitude')
                    weights[e['midi']-21]+=e['amplitude']
        sal=np.bincount(midi%12,weights=weights,minlength=12);sal/=max(sal.sum(),1e-12)
        result.append(sal);deltas.append(float(times[i]-t));note_sets.append(midi[weights>0].tolist())
    return np.array(result).reshape(-1,12),deltas,note_sets

def build_evidence(frame_times,note_frames,events,*,source_id,start_s,duration_s):
    """Explicit video offset; model candidates never become confirmed guitar notes."""
    if not source_id or not np.isfinite(start_s) or start_s<0 or not np.isfinite(duration_s) or duration_s<=0:raise ValueError('Invalid source interval')
    times=np.asarray(frame_times,float);valid=np.where((times>=0)&(times<duration_s))[0][::10]
    query=times[valid];sal,_,_=sample_prediction(times,note_frames,events,query)
    pitches=[]
    for i,e in enumerate(events):
        if not 38<=e['midi']<=88:continue
        a=max(0.,float(e['start_s']));b=min(duration_s,float(e['end_s']))
        if a>=b:continue
        pitches.append(dict(event_id=f'basic_pitch_note_{i}',start_s=start_s+a,end_s=start_s+b,midi=int(e['midi']),
            frequency_hz=float(440*2**((e['midi']-69)/12)),score=float(e['amplitude']),score_type='mean_model_note_activation',
            method='basic_pitch_0.4.0_pretrained_onnx',pitch_status='provisional',status='candidate',
            instrument_attribution='unknown',string_num=None,contact='unknown'))
    return dict(schema_version='guitar_evidence.v1',run_id='basic_pitch_pretrained',source_id=source_id,
        timebase='source_video_seconds',start_s=start_s,end_s=start_s+duration_s,tuning=None,capo=None,
        assumptions=['Tuning and capo are unverified; source offset is supplied explicitly'],
        pitch_class_salience=[dict(event_id=f'basic_pitch_chroma_{i}',time_s=float(start_s+t),salience=s.tolist(),
                                 score_type='normalized_thresholded_model_note_activation') for i,(t,s) in enumerate(zip(query,sal))],
        pitch_candidates=pitches,tentative_notes=pitches,onsets=[],pitch_tracks=[],acoustic_events=[],
        evidence=dict(observed_audio_notes=[],manual_notes=[],string_states=[]),
        limitations=['Pretrained model estimates are not confirmed notes or guitar attribution.',
                     'No finger, string, fret, mute, open-string or contact conclusion.',
                     'Model context and decoded durations may include timing errors.'])
