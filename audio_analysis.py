"""Spectral evidence baseline: peaks are not confirmed fundamental notes."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import scipy
from scipy import signal
from scipy.io import wavfile


def features(samples, rate, offset=0., window=8192, hop=441, *, min_frequency=65., max_frequency=1600.):
    x=np.asarray(samples,dtype=float)
    if x.ndim != 1 or len(x)<window or not np.isfinite(x).all():
        raise ValueError('Require finite mono audio of at least one window')
    if not (np.isfinite(min_frequency) and np.isfinite(max_frequency) and 0<min_frequency<max_frequency<rate/2):
        raise ValueError('Invalid candidate frequency bounds')
    frames=np.lib.stride_tricks.sliding_window_view(x,window)[::hop]
    magnitude=np.abs(np.fft.rfft(frames*np.hanning(window),axis=1))
    freq=np.fft.rfftfreq(window,1/rate)
    times=offset+(np.arange(len(frames))*hop+window/2)/rate
    rms=np.sqrt(np.mean(frames**2,axis=1))
    flux=np.r_[0,np.maximum(np.diff(magnitude,axis=0),0).sum(axis=1)]
    scale=max(float(flux.max()),1e-12)
    peaks,_=signal.find_peaks(flux/scale,height=.12,prominence=.08,distance=max(1,round(.08*rate/hop)))
    onsets=[dict(event_id=f'onset_{i}',time_s=float(times[k]),score=float(flux[k]/scale),score_type='relative_positive_spectral_flux',method='hann_stft_flux',status='candidate') for i,k in enumerate(peaks)]
    notes=[]; chroma=[]; events=[]
    valid=(freq>=min_frequency)&(freq<=max_frequency)
    for k,t in enumerate(times):
        sal=np.zeros(12)
        bins,_=signal.find_peaks(magnitude[k])
        bins=[b for b in bins if valid[b] and magnitude[k,b]>max(magnitude[k].max()*.12,1e-7)]
        bins=sorted(bins,key=lambda b:magnitude[k,b],reverse=True)[:12]
        for b in bins:
            # Quadratic interpolation improves peak location, not physical resolution.
            logs=np.log(np.maximum(magnitude[k,b-1:b+2],1e-15))
            denom=logs[0]-2*logs[1]+logs[2]
            delta=float(np.clip(.5*(logs[0]-logs[2])/denom,-.5,.5)) if denom else 0.
            hz=(b+delta)*rate/window
            if not min_frequency<=hz<=max_frequency:continue
            midi=69+12*np.log2(hz/440)
            score=float(magnitude[k,b]/max(magnitude[k].max(),1e-12))
            sal[round(midi)%12]+=score
            notes.append(dict(event_id=f'peak_{k}_{b}',start_s=float(t-window/2/rate),end_s=float(t+window/2/rate),midi=float(midi),frequency_hz=float(hz),score=score,score_type='relative_spectral_peak_amplitude',method='hann_stft_local_peak',pitch_status='spectral_peak_candidate',status='candidate',offset_status='analysis_window_only',frequency_resolution_hz=rate/window))
        chroma.append(dict(time_s=float(t),salience=(sal/max(sal.sum(),1e-12)).tolist()))
        if k%10==0:
            flatness=float(np.exp(np.mean(np.log(magnitude[k]+1e-15)))/max(np.mean(magnitude[k]),1e-15))
            events.append(dict(event_id=f'acoustic_{k}',start_s=float(t-window/2/rate),end_s=float(t+window/2/rate),score=flatness,score_type='spectral_flatness',method='spectral_flatness_and_rms',status='candidate',acoustic_state='silent' if rms[k]<1e-5 else 'unknown',rms=float(rms[k]),decay_status='not_estimated'))
    return dict(onsets=onsets,pitch_candidates=notes,pitch_class_salience=chroma,acoustic_events=events), (times,rms,freq,magnitude,flux)


def short_onsets(samples, rate, offset=0., window=1024, hop=220):
    """Offline short-window flux, independently timestamped at window center."""
    x=np.asarray(samples,dtype=float)
    if x.ndim != 1 or len(x)<window or not np.isfinite(x).all():
        raise ValueError('Require finite mono samples and a complete onset window')
    frames=np.lib.stride_tricks.sliding_window_view(x,window)[::hop]
    mag=np.abs(np.fft.rfft(frames*np.hanning(window),axis=1))
    flux=np.r_[0,np.maximum(np.diff(mag,axis=0),0).sum(axis=1)]
    relative=flux/max(float(flux.max()),1e-12)
    peaks,_=signal.find_peaks(relative,height=.12,prominence=.08,
                              distance=max(1,round(.08*rate/hop)))
    return [dict(event_id=f'short_onset_{i}',time_s=float(offset+(k*hop+window/2)/rate),
                 uncorrected_time_s=float(offset+(k*hop+window/2)/rate),
                 applied_correction_s=0.,score=float(relative[k]),
                 score_type='relative_positive_spectral_flux',method='short_hann_stft_flux',
                 status='candidate') for i,k in enumerate(peaks)]


def persistent_peaks(candidates, hop_s, minimum_frames=5):
    """Link rounded-MIDI spectral peaks over consecutive windows; not note tracking."""
    by_midi={}
    for p in candidates:
        by_midi.setdefault(round(p['midi']),[]).append(p)
    tracks=[]
    for midi,peaks in sorted(by_midi.items()):
        group=[]
        def emit(items):
            if len(items)<minimum_frames:
                return
            tracks.append(dict(event_id=f'track_{len(tracks)}',start_s=items[0]['start_s'],
                end_s=items[-1]['end_s'],midi=float(np.median([p['midi'] for p in items])),
                frequency_hz=float(np.median([p['frequency_hz'] for p in items])),
                score=float(np.median([p['score'] for p in items])),
                score_type='median_relative_spectral_peak_amplitude',
                pitch_status='persistent_spectral_peak_candidate',status='candidate',
                method='consecutive_window_rounded_midi_link',frame_count=len(items),
                center_span_s=(len(items)-1)*hop_s,
                evidence_ids=[p['event_id'] for p in items],offset_status='window_support_only',
                harmonic_ambiguities=[]))
        for p in sorted(peaks,key=lambda p:p['start_s']):
            if group and p['start_s']-group[-1]['start_s']>hop_s*1.5:
                emit(group); group=[]
            group.append(p)
        emit(group)
    for high in tracks:
        for low in tracks:
            if low['frequency_hz']>=high['frequency_hz'] or max(low['start_s'],high['start_s'])>=min(low['end_s'],high['end_s']):
                continue
            ratio=high['frequency_hz']/low['frequency_hz']; harmonic=round(ratio)
            if 2<=harmonic<=6 and abs(1200*np.log2(ratio/harmonic))<35:
                high['harmonic_ambiguities'].append(dict(lower_event_id=low['event_id'],possible_harmonic=harmonic))
    return tracks


def time_local_evidence(record, start_s, end_s):
    """Keep complete analysis supports only; never combine separate time intervals."""
    import copy
    if not record['start_s'] <= start_s < end_s <= record['end_s']:
        raise ValueError('Requested interval must be inside source evidence')
    keys=['schema_version','run_id','source_id','timebase','tuning','capo','assumptions','limitations']
    result={k:copy.deepcopy(record[k]) for k in keys}
    for key in ['source_identity']:
        if key in record: result[key]=copy.deepcopy(record[key])
    result.update(start_s=start_s,end_s=end_s,status='insufficient_evidence')
    result['onsets']=[copy.deepcopy(x) for x in record['onsets'] if start_s<=x['time_s']<end_s]
    for key in ['pitch_candidates','pitch_tracks','acoustic_events']:
        result[key]=[copy.deepcopy(x) for x in record.get(key,[]) if start_s<=x['start_s'] and x['end_s']<=end_s]
    half=record['provenance']['window_support_s']/2
    result['pitch_class_salience']=[copy.deepcopy(x) for x in record['pitch_class_salience'] if start_s<=x['time_s']-half and x['time_s']+half<=end_s]
    result['evidence']={'observed_audio_notes':[],'audio':'../analysis.wav'}
    result['provenance']=copy.deepcopy(record['provenance'])
    result['provenance'].update(parent_evidence='../evidence.json',selection='automatic_review_target_not_validated_stable',
        interval_policy='complete_window_support_inside_interval; tracks crossing boundary withheld')
    return result


def evaluate_onsets(predicted, reference, tolerance=.05, reviewed=False):
    """Ordered optimal one-to-one matching: maximize count then minimize total error.

    Unreviewed empty references are missing ground truth, never perfect silence.
    """
    if not reviewed:
        return dict(status='pending_review',reference_count=len(reference),precision=None,recall=None,mae_s=None)
    pred=sorted(float(x) for x in predicted); ref=sorted(float(x) for x in reference)
    dp=[[ (0,0.,[]) for _ in range(len(ref)+1)] for _ in range(len(pred)+1)]
    for i in range(1,len(pred)+1):
        for j in range(1,len(ref)+1):
            options=[dp[i-1][j],dp[i][j-1]]
            error=abs(pred[i-1]-ref[j-1])
            if error<=tolerance+1e-12:
                n,cost,pairs=dp[i-1][j-1]
                options.append((n+1,cost+error,pairs+[(pred[i-1],ref[j-1])]))
            dp[i][j]=max(options,key=lambda z:(z[0],-z[1]))
    n,cost,pairs=dp[-1][-1]
    return dict(status='evaluated',reference_count=len(ref),prediction_count=len(pred),matches=pairs,
                true_positive=n,false_positive=len(pred)-n,false_negative=len(ref)-n,
                precision=n/len(pred) if pred else None,recall=n/len(ref) if ref else None,
                mae_s=cost/n if n else None,tolerance_s=tolerance)


def analyze(manifest, split_windows=False):
    started=time.perf_counter()
    path=Path(manifest); m=json.loads(path.read_text(encoding='utf-8'))
    rate,x=wavfile.read(path.parent/m['files']['analysis'])
    evidence,arrays=features(x,rate,m['start_s'])
    result={k:m[k] for k in ['schema_version','run_id','source_id','start_s','end_s','timebase','tuning','capo','assumptions']}
    result.update(evidence)
    if split_windows:
        result['legacy_long_window_onsets']=result['onsets']
        result['onsets']=short_onsets(x,rate,m['start_s'])
        result['pitch_tracks']=persistent_peaks(result['pitch_candidates'],441/rate)
    result.update(status='insufficient_evidence',evidence={'audio':'analysis.wav'},provenance={'manifest':'manifest.json','method':'spectral_baseline_v1','window_samples':8192,'hop_samples':441,'frame_timestamp':'window_center','window_support_s':8192/rate,'nominal_flux_lookahead_s':4096/rate,'numpy':np.__version__,'scipy':scipy.__version__},limitations=['Spectral peaks include harmonics and octave duplicates; not fundamental-note transcription','No string, contact, chord, intentional mute, or instrument identity inferred','Window boundaries are not note onset/offset labels','Heuristic scores are not calibrated probabilities','Listening, independent annotations and audiovisual synchronization remain pending'])
    if split_windows:
        result['provenance'].update(method='spectral_baseline_v2',onset_window_samples=1024,
            onset_hop_samples=220,onset_timestamp='window_center',onset_window_support_s=1024/rate,
            onset_lookahead_s=512/rate,applied_av_correction_s=0.,av_correction_status='unverified_no_correction')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    times,rms,freq,mag,flux=arrays
    fig,axes=plt.subplots(3,1,figsize=(14,9),sharex=True)
    axes[0].plot(m['start_s']+np.arange(len(x))/rate,x,lw=.3); axes[0].set_ylabel('Waveform')
    axes[1].plot(times,rms,label='RMS'); axes[1].plot(times,flux/max(flux.max(),1e-12),label='Relative flux'); axes[1].legend()
    axes[2].pcolormesh(times,freq,20*np.log10(np.maximum(mag.T,1e-8)),shading='auto',vmin=-70,vmax=30); axes[2].set_ylim(50,2000); axes[2].set_ylabel('Hz'); axes[2].set_xlabel('Source video seconds')
    fig.tight_layout(); fig.savefig(path.parent/'overview.png'); plt.close(fig)
    result['provenance']['analysis_elapsed_s']=time.perf_counter()-started
    (path.parent/'evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--manifest',required=True)
    p.add_argument('--split-windows',action='store_true')
    a=p.parse_args(); analyze(a.manifest,a.split_windows)
