"""D2-E6 cut and existing chord scorer held fixed; only features differ."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from audio_analysis import features
from cut_audio_features import cut_features
from harmonic_chord_features import WINDOW
from guitarset_benchmark import rank_saliences,evaluate_layer,parse_chord,TEMPLATES,load_reference,KNOWN_TIMING
from benchmark_harmonic_chords import diagnose
from idmt_chords_benchmark import pcm_float
from sweep_bandcut_vision_weights import band_cut,LOW_HZ,HIGH_HZ
from compare_guitar_stem_accuracy import safe_evaluate

ROOT=Path(__file__).resolve().parent
BASE=ROOT/'dataset/integration_review/runs/harmonic_ablation_20261105_v1'
NAMES=['peak','harmonic','supported']

def evaluate_arrays(arrays,times,layers):
    branches={}
    for name,sal in arrays.items():
        scores,rank,usable=rank_saliences(sal);branches[name]={}
        for layer,events in layers.items():
            r=evaluate_layer(times,rank,scores,usable,events);r['seventh_diagnosis']=diagnose(sal,times,r);qs={}
            for f in r['frames']:
                ref=parse_chord(f['reference']);q=next((c['quality'] for c in TEMPLATES if c['root_pc']==ref['root_pc'] and tuple(c['pcs'])==ref['pcs']),'OOV')
                c=qs.setdefault(q,Counter());c['evaluated']+=1;c['top1']+=int(f['correct_top1'])
            r['per_quality']={q:dict(c) for q,c in qs.items()};branches[name][layer]=r
    return branches

def process(old):
    rate,raw=wavfile.read(old['audio'],mmap=True)
    if rate!=44100 or raw.ndim!=1:raise ValueError('Expected 44.1kHz mono')
    sha=hashlib.sha256(Path(old['audio']).read_bytes()).hexdigest()
    if sha!=old['sha256']:raise ValueError('Input hash mismatch')
    x=band_cut(pcm_float(raw),rate);times=np.array(old['times']);arrays={name:[] for name in NAMES};residual=[]
    for t in times:
        start=round(t*rate)-WINDOW//2;win=x[start:start+WINDOW];rows,_,res=cut_features(win,rate)
        for name in NAMES:arrays[name].append(rows[name])
        residual.append(res)
    if old['domain']=='guitarset':layers,notes=load_reference(old['annotation'])
    else:
        layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (l.split() for l in Path(old['annotation']).read_text().splitlines() if l.strip())]};notes=[]
    arrays={n:np.array(a) for n,a in arrays.items()};pc={}
    if old['domain']=='guitarset':
        for name,sal in arrays.items():
            c=Counter()
            for t,s in zip(times,sal):
                truth={round(n['midi'])%12 for n in notes if n['start']<=t<n['end']};pred=set(np.where((s>0)&(s>=.1*s.max()))[0])
                c.update(tp=len(truth&pred),fp=len(pred-truth),fn=len(truth-pred),windows=1)
            pc[name]=dict(c)
    return dict(id=old['id'],domain=old['domain'],audio=old['audio'],annotation=old['annotation'],audio_sha256=sha,
        annotation_sha256=hashlib.sha256(Path(old['annotation']).read_bytes()).hexdigest(),times=times.tolist(),
        salience={k:v.tolist() for k,v in arrays.items()},residual=residual,note_pc_counts=pc,branches=evaluate_arrays(arrays,times,layers))

def aggregate(records):
    summary={}
    for domain in ['guitarset','idmt']:
        items=[r for r in records if r['domain']==domain and r['id'] not in KNOWN_TIMING];branches={}
        for name in NAMES:
            branches[name]={}
            for layer in (['nominal','performed'] if domain=='guitarset' else ['nominal']):
                c=Counter();d=Counter();qs={}
                for r in items:
                    result=r['branches'][name][layer];c.update(result['counts']);d.update(result['seventh_diagnosis']['counts'])
                    for q,v in result['per_quality'].items():qs.setdefault(q,Counter()).update(v)
                branches[name][layer]=dict(counts=dict(c),seventh_diagnosis=dict(d),per_quality={q:dict(v) for q,v in qs.items()})
            if domain=='guitarset':
                c=Counter()
                for r in items:c.update(r['note_pc_counts'][name])
                p=c['tp']/max(1,c['tp']+c['fp']);rec=c['tp']/max(1,c['tp']+c['fn'])
                branches[name]['note_pc']=dict(counts=dict(c),precision=p,recall=rec,f1=2*p*rec/max(p+rec,1e-12))
        summary[domain]=dict(files=len(items),branches=branches)
    return summary

def tutorial(out):
    audio=ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav'
    rate,raw=wavfile.read(audio);x=pcm_float(raw).mean(axis=1);cut=band_cut(x,rate)
    # Short review excerpts preserve amplitude; no gain normalization.
    wavfile.write(out/'tutorial_raw_198_202.wav',rate,x[4*rate:8*rate].astype(np.float32))
    wavfile.write(out/'tutorial_cut_198_202.wav',rate,cut[4*rate:8*rate].astype(np.float32))
    refs=json.loads((ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json').read_text())['references'];rows=[]
    for ref in refs:
        start=round((ref['pts']-194)*rate)-WINDOW//2;arrays,_,res=cut_features(cut[start:start+WINDOW],rate);branches={}
        for name,s in arrays.items():
            scores,rank,usable=rank_saliences(np.array([s]));ranked=[dict(root_pc=TEMPLATES[j]['root_pc'],quality=TEMPLATES[j]['quality'],concert_symbol=TEMPLATES[j]['symbol'],score=float(scores[0,j])) for j in rank[0]] if usable[0] else []
            branches[name]=dict(top3=ranked[:3],evaluation=safe_evaluate(ranked,ref))
        rows.append(dict(reference=ref,branches=branches,residual=res))
    result=dict(audio=str(audio),sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),offset_s=194,rows=rows,
                summary={n:{k:sum(r['branches'][n]['evaluation'][k] for r in rows) for k in ['exact_top1','exact_top3','root_top1']} for n in NAMES})
    (out/'tutorial.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output
    if (out/'summary.json').exists():raise FileExistsError(out)
    (out/'records').mkdir(parents=True,exist_ok=True)
    config=dict(training=False,parameter_sweep=False,branches=NAMES,scorer='Existing coverage scorer rank_saliences, unchanged for all branches',
        cut=dict(low_hz=LOW_HZ,high_hz=HIGH_HZ,method='Full recording FFT mask once before windowing, no gain normalization'),
        sampling='Exact previous1sGuitarSet and midpointIDMT grids;8192sample windows;no temporal smoothing',
        model='Existing1/h harmonic dictionary, observation and templates both cropped to D2-E6; no high-harmonic negative evidence',
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['benchmark_cut_audio.py','cut_audio_features.py','guitarset_benchmark.py','harmonic_chord_features.py','sweep_bandcut_vision_weights.py']})
    if (out/'config.json').exists() and json.loads((out/'config.json').read_text())!=config:raise ValueError('Config mismatch')
    (out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    sources=sorted((BASE/'records').glob('*.json'));records=[]
    for i,path in enumerate(sources):
        target=out/'records'/path.name
        if target.exists():r=json.loads(target.read_text())
        else:
            r=process(json.loads(path.read_text()));target.write_text(json.dumps(r,indent=2),encoding='utf-8')
        records.append(r)
        if i%10==0 or r['domain']=='idmt':print(i+1,'/',len(sources),r['id'],flush=True)
    tutorial(out);(out/'summary.json').write_text(json.dumps(aggregate(records),indent=2),encoding='utf-8');print('Completed',len(records),flush=True)

if __name__=='__main__':main()
