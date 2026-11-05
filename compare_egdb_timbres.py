"""Paired EGDB demo timbre diagnostics. DI is a comparator, never truth."""
import hashlib
import json
from pathlib import Path
import subprocess
import warnings
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from render_audio_video_review import predictions
from chord_display_cleanup import stabilize

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'dataset/integration_review/runs/egdb_timbre_20261105_v1'
SOURCE = ROOT / 'EGDB_repo/Guitar_Transcription_sample/Training'
TONES = ['DI', 'ft', 'marshall', 'mesa']
PAIRS = ['0503_1_a', '0701_3_c']


def read_audio(path):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        rate, pcm = wavfile.read(path)
    if np.issubdtype(pcm.dtype, np.signedinteger):
        x = pcm.astype(float) / 2**(np.iinfo(pcm.dtype).bits-1)
    else:
        x = pcm.astype(float)
    if x.ndim == 2:
        x = x.mean(axis=1)
    hop = round(rate / 100)
    chunks = x[:len(x)//hop*hop].reshape(-1, hop)
    rms = np.sqrt(np.mean(chunks**2, axis=1))
    onset = np.maximum(0, np.diff(np.log(np.maximum(rms, 1e-5)), prepend=np.log(max(rms[0], 1e-5))))
    return rate, x, rms, onset


def align_envelopes(reference, target):
    # target time = reference time + lag; audio-derived only, no chord fitting.
    a = np.asarray(reference); b = np.asarray(target)
    scores = []
    for lag in range(-100, 101):
        i = np.arange(max(0, -lag), min(len(a), len(b)-lag))
        score = float(np.corrcoef(a[i], b[i+lag])[0, 1]) if len(i)>10 and np.std(a[i])>0 and np.std(b[i+lag])>0 else -1.
        scores.append(score if np.isfinite(score) else -1.)
    best = int(np.argmax(scores))-100
    windows = []
    for block in np.array_split(np.arange(max(0,-best), min(len(a),len(b)-best)), 3):
        candidates = []
        for lag in range(max(-100,best-20),min(100,best+20)+1):
            i = block[(block+lag>=0)&(block+lag<len(b))]
            score = float(np.corrcoef(a[i],b[i+lag])[0,1]) if len(i)>10 and np.std(a[i])>0 and np.std(b[i+lag])>0 else -1.
            candidates.append((score if np.isfinite(score) else -1.,lag))
        windows.append(max(candidates)[1]/100)
    correlation = scores[best+100]
    # Prespecified exploratory quality gates, not calibrated alignment confidence.
    reliable = correlation >= .35 and max(windows)-min(windows) <= .04 and abs(best)<100
    return dict(target_offset_s=best/100, onset_correlation=correlation, local_offsets_s=windows,
                status='provisional_usable' if reliable else 'uncertain',
                thresholds=dict(min_correlation=.35,max_local_spread_s=.04,max_abs_search_s=1),
                method='100Hz positive log-RMS difference correlation; target=DI+offset',
                independently_verified=False)


def top_ids(row):
    if not row['top3']:return set()
    score = row['top3'][0]['score']
    return {(c['root_pc'],c['quality']) for c in row['top3'] if abs(c['score']-score)<=1e-10}


def pooled_notes(grid, values, queries, width):
    midi=np.arange(38,89); notes=[]
    for t in queries:
        selected=values[(grid>=t-width/2)&(grid<t+width/2),17:68]
        notes.append(set(midi[selected.max(axis=0)>=.3].tolist()))
    return notes


def compare_pair(di_grid, di_frames, tone_grid, tone_frames, offset, width):
    start=max(di_grid[0]+width/2,tone_grid[0]+width/2-offset)
    end=min(di_grid[-1]-width/2,tone_grid[-1]-width/2-offset)
    times=np.arange(np.ceil(start*24),np.floor(end*24)+1)/24
    a=predictions(di_grid,di_frames,times,width); b=predictions(tone_grid,tone_frames,times+offset,width)
    da=stabilize(times,a);db=stabilize(times,b)
    na=pooled_notes(di_grid,di_frames,times,width);nb=pooled_notes(tone_grid,tone_frames,times+offset,width)
    both=[i for i in range(len(times)) if a[i]['top3'] and b[i]['top3']]
    active=[i for i in range(len(times)) if na[i] and nb[i]]
    agree=sum((a[i]['top3'][0]['root_pc'],a[i]['top3'][0]['quality'])==(b[i]['top3'][0]['root_pc'],b[i]['top3'][0]['quality']) for i in both)
    tieagree=sum(bool(top_ids(a[i])&top_ids(b[i])) for i in both)
    rows=[dict(di_time_s=float(t),tone_time_s=float(t+offset),di=a[i],tone=b[i],di_display=da[i],tone_display=db[i],
               di_midi=sorted(na[i]),tone_midi=sorted(nb[i])) for i,t in enumerate(times)]
    summary=dict(common_centers=len(times),both_have_chord=len(both),di_abstain=sum(not r['top3'] for r in a),
        tone_abstain=sum(not r['top3'] for r in b),di_top_tie=sum(r['tied_top1_count']>1 for r in a),
        tone_top_tie=sum(r['tied_top1_count']>1 for r in b),raw_top1_agree=agree,
        raw_top1_agreement_given_both=agree/len(both) if both else None,
        top_tie_set_overlap_among_shown3=tieagree/len(both) if both else None,
        note_active_centers=len(active),median_di_note_count=float(np.median([len(n) for n in na])),
        median_tone_note_count=float(np.median([len(n) for n in nb])),
        mean_tone_notes_not_in_di=float(np.mean([len(y-x) for x,y in zip(na,nb)])),
        mean_di_notes_not_in_tone=float(np.mean([len(x-y) for x,y in zip(na,nb)])),
        mean_midi_jaccard_given_both_active=float(np.mean([len(na[i]&nb[i])/len(na[i]|nb[i]) for i in active])) if active else None)
    return summary,rows


def main():
    if (OUT/'summary.json').exists():raise FileExistsError(OUT/'summary.json')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'records').mkdir(exist_ok=True)
    tasks=[dict(id=f'{pair}_{tone}',audio=str(SOURCE/f'{pair}_{tone}.wav')) for pair in PAIRS for tone in TONES]
    (OUT/'tasks.json').write_text(json.dumps(tasks,indent=2),encoding='utf-8')
    with (OUT/'inference.log').open('ab') as log:
        subprocess.run([str(ROOT/'.venv-audio-model/Scripts/python.exe'),str(ROOT/'basic_pitch_worker.py'),
                        '--tasks',str(OUT/'tasks.json'),'--output',str(OUT/'predictions'),'--modes','raw'],
                       cwd=ROOT,stdout=log,stderr=log,check=True)
    result={};audio={};loaded={}
    for task in tasks:
        path=Path(task['audio']);audio[task['id']]=read_audio(path)
        meta=json.loads((OUT/'predictions'/f"{task['id']}_raw.json").read_text())
        assert meta['source_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(OUT/'predictions'/f"{task['id']}_raw.npz") as d:loaded[task['id']]=(d['times'],d['note'])
    for pair in PAIRS:
        result[pair]={}
        for tone in TONES[1:]:
            di=f'{pair}_DI';target=f'{pair}_{tone}';alignment=align_envelopes(audio[di][3],audio[target][3]);branches={}
            # Uncertain alignment remains diagnostic-only and is explicitly flagged.
            for width in [.2,.4]:
                summary,rows=compare_pair(*loaded[di],*loaded[target],alignment['target_offset_s'],width)
                branches[str(width)]=summary
                (OUT/'records'/f'{target}_w{width}.json').write_text(json.dumps(rows),encoding='utf-8')
            result[pair][tone]=dict(alignment=alignment,branches=branches)
        fig,axes=plt.subplots(4,2,figsize=(13,10))
        for i,tone in enumerate(TONES):
            sr,x,rms,onsets=audio[f'{pair}_{tone}'];offset=0 if tone=='DI' else result[pair][tone]['alignment']['target_offset_s']
            axes[i,0].plot(np.arange(len(rms))/100-offset,rms,lw=.7);axes[i,0].set_title(f'{tone} original RMS envelope (not loudness normalized)');axes[i,0].set_xlim(0,len(audio[f'{pair}_DI'][1])/sr)
            freq,t,z=stft(x,sr,nperseg=2048,noverlap=1536)
            axes[i,1].pcolormesh(t-offset,freq,20*np.log10(np.maximum(abs(z),1e-6)),shading='auto',vmin=-80,vmax=-10,cmap='magma');axes[i,1].set_ylim(65,5000);axes[i,1].set_yscale('log');axes[i,1].set_title(f'{tone} spectrum / same dBFS scale')
        for ax in axes[-1]:ax.set_xlabel('DI-relative time (s); provisional audio-derived offset')
        fig.suptitle(f'EGDB {pair}: original audio evidence, not labels or accuracy');fig.tight_layout();fig.savefig(OUT/f'{pair}_audio.png',dpi=125);plt.close(fig)
        fig,axes=plt.subplots(4,1,figsize=(13,8),sharex=True)
        for i,tone in enumerate(TONES):
            if tone=='DI':
                temp=json.loads((OUT/'records'/f'{pair}_ft_w0.2.json').read_text());times=[r['di_time_s'] for r in temp];rows=[r['di'] for r in temp]
            else:
                temp=json.loads((OUT/'records'/f'{pair}_{tone}_w0.2.json').read_text());times=[r['di_time_s'] for r in temp];rows=[r['tone'] for r in temp]
            for t,row in zip(times,rows):
                if row['top3']:axes[i].scatter(t,row['top3'][0]['root_pc'],s=5,c='#b46a21' if row['tied_top1_count']>1 else '#247f73')
            axes[i].set_ylabel(tone);axes[i].set_yticks(range(12),['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']);axes[i].grid(alpha=.15)
        axes[-1].set_xlabel('DI-relative time (s)');fig.suptitle(f'{pair}: raw top-1 root, 0.2s / orange=tied / gaps=abstain / DI is not truth');fig.tight_layout();fig.savefig(OUT/f'{pair}_roots.png',dpi=125);plt.close(fig)
    summary=dict(pairs=result,ground_truth_available=False,accuracy_computed=False,
        model_input='Original unmodified WAV, raw model mode; output MIDI38..88; no waveform bandcut',
        comparison='DI agreement only; DI may also be wrong; amp model names do not certify distortion/gain levels',
        config=dict(sample_hz=24,pool_widths=[.2,.4],alignment_independent_of_predictions=True,training=False),
        input_sha256={t['id']:hashlib.sha256(Path(t['audio']).read_bytes()).hexdigest() for t in tasks})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
