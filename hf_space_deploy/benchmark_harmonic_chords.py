"""Frozen four-way feature/scorer ablation on two guitar corpora. Evaluation only."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from scipy.io import wavfile
from audio_analysis import features
from harmonic_chord_features import harmonic_salience,WINDOW
from chord_score_variants import score_variants
from guitarset_benchmark import TEMPLATES,KNOWN_TIMING,parse_chord,load_reference,evaluate_layer
from idmt_chords_benchmark import pcm_float

ROOT=Path(__file__).resolve().parent
BRANCHES=['peak_legacy','peak_cosine','harmonic_legacy','harmonic_cosine']

def diagnose(sal,times,layer):
    """Absence means threshold absence in evidence, never proof of physical absence."""
    counts=Counter();quality_counts={}
    for f in layer['frames']:
        ref=parse_chord(f['reference'])
        template=next((c for c in TEMPLATES if c['root_pc']==ref['root_pc'] and tuple(c['pcs'])==ref['pcs']),None)
        if not template or template['quality'] not in ('7','maj7','m7','m7b5'):continue
        i=int(np.argmin(abs(times-f['time_s'])));s=sal[i];seventh=(ref['root_pc']+(11 if template['quality']=='maj7' else 10))%12
        supported=bool(s[seventh]>0 and s[seventh]>=.1*s.max())
        category='correct' if f['correct_top1'] else 'wrong_seventh_pc_weak' if not supported else 'wrong_seventh_pc_present'
        counts['evaluated']+=1;counts[category]+=1
        if not f['correct_top1'] and f['top3']:
            counts['wrong_root']+=int(f['top3'][0]['root_pc']!=ref['root_pc'])
        q=quality_counts.setdefault(template['quality'],Counter());q['evaluated']+=1;q[category]+=1
    return dict(counts=dict(counts),per_quality={k:dict(v) for k,v in quality_counts.items()})

def process(task):
    path=Path(task['audio']);rate,x=wavfile.read(path,mmap=True)
    if rate!=44100 or x.ndim!=1:raise ValueError('Expected 44.1kHz mono')
    if task['domain']=='idmt':
        events=[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)'))
                for a,b,c in (line.split() for line in Path(task['annotation']).read_text().splitlines() if line.strip())]
        layers={'nominal':events};times=np.array([e['time']+e['duration']/2 for e in events])
    else:
        layers,_=load_reference(task['annotation']);times=np.arange(.5,len(x)/rate-.1,1.)
    peak=[];harmonic=[];residual=[]
    for t in times:
        start=round(t*rate)-WINDOW//2;win=pcm_float(x[start:start+WINDOW])
        evidence,_=features(win,rate)
        peak.append(evidence['pitch_class_salience'][0]['salience'])
        h,_,r=harmonic_salience(win,rate);harmonic.append(h);residual.append(r)
    arrays={'peak':np.array(peak),'harmonic':np.array(harmonic)};branches={}
    for feature,sal in arrays.items():
        for scorer,(scores,rank,usable) in score_variants(sal).items():
            if scorer not in ('legacy','cosine'):continue
            name=feature+'_'+scorer;branches[name]={}
            for layer,events in layers.items():
                result=evaluate_layer(times,rank,scores,usable,events)
                result['seventh_diagnosis']=diagnose(sal,times,result)
                qcounts={}
                for f in result['frames']:
                    ref=parse_chord(f['reference']);q=next((c['quality'] for c in TEMPLATES if c['root_pc']==ref['root_pc'] and tuple(c['pcs'])==ref['pcs']),'OOV')
                    c=qcounts.setdefault(q,Counter());c['evaluated']+=1;c['top1']+=int(f['correct_top1'])
                result['per_quality']={k:dict(v) for k,v in qcounts.items()};branches[name][layer]=result
    return dict(id=task['id'],domain=task['domain'],audio=str(path),annotation=task['annotation'],
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),times=times.tolist(),
                peak_salience=arrays['peak'].tolist(),harmonic_salience=arrays['harmonic'].tolist(),
                residual=residual,branches=branches)

def aggregate(records):
    summary={}
    for domain in ['guitarset','idmt']:
        items=[r for r in records if r['domain']==domain and r['id'] not in KNOWN_TIMING];group={}
        for branch in BRANCHES:
            group[branch]={}
            for layer in (['nominal','performed'] if domain=='guitarset' else ['nominal']):
                counts=Counter();diag=Counter();qualities={}
                for r in items:
                    result=r['branches'][branch][layer];counts.update(result['counts']);diag.update(result['seventh_diagnosis']['counts'])
                    for q,c in result['per_quality'].items():qualities.setdefault(q,Counter()).update(c)
                group[branch][layer]=dict(counts=dict(counts),seventh_diagnosis=dict(diag),per_quality={q:dict(v) for q,v in qualities.items()})
        summary[domain]=dict(files=len(items),branches=group)
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output
    out.mkdir(parents=True,exist_ok=True);(out/'records').mkdir(exist_ok=True)
    sources=['benchmark_harmonic_chords.py','harmonic_chord_features.py','chord_score_variants.py','guitarset_benchmark.py','audio_analysis.py']
    config=dict(training=False,fitting='Per-window nonnegative note amplitudes only; fixed harmonic templates 1/h, h=1..8, equal temperament A440',
        input='raw mono, no waveform bandcut; baseline spectral peaks65..1600Hz; harmonic fit50..6000Hz, fundamental D2..E6',
        sampling='GuitarSet fixed 1s grid starting0.5s; IDMT guitar every segment midpoint; no temporal smoothing',
        boundaries='score only center windows >=0.05s from reference boundaries; no labels used in prediction',
        branches=BRANCHES,source_hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in sources})
    if (out/'config.json').exists() and json.loads((out/'config.json').read_text())!=config:raise ValueError('Config mismatch')
    (out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    manifest=json.loads((ROOT/'dataset/integration_review/runs/guitarset_audio_ready_20261105_v1/manifest.json').read_text())
    tasks=[dict(id=r['recording_id'],domain='guitarset',audio=r['audio_file'],annotation=r['annotation_file']) for r in manifest['rows'] if r['performance']=='comp']
    base=ROOT/'IDMT_SMT_Chords/extracted/IDMT-SMT-CHORDS/guitar'
    tasks += [dict(id=f.stem,domain='idmt',audio=str(f),annotation=str(base/'guitar_annotation.lab')) for f in sorted(base.glob('*.wav'))]
    todo=[t for t in tasks if not (out/'records'/(t['id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for i,future in enumerate(as_completed([pool.submit(process,t) for t in todo])):
            r=future.result();(out/'records'/(r['id']+'.json')).write_text(json.dumps(r,indent=2),encoding='utf-8')
            if i%10==0 or r['domain']=='idmt':print(i+1,'/',len(todo),r['id'],flush=True)
    records=[json.loads((out/'records'/(t['id']+'.json')).read_text()) for t in tasks]
    (out/'summary.json').write_text(json.dumps(aggregate(records),indent=2),encoding='utf-8')
    print('Completed',len(records),flush=True)

if __name__=='__main__':main()
