"""One preregistered evidence gate; no threshold sweep or production changes."""
import json
import hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import Counter
import numpy as np
from scipy.io import wavfile
from benchmark_harmonic_chords import ROOT,diagnose
from harmonic_chord_features import WINDOW
from supported_harmonic_features import supported_salience
from idmt_chords_benchmark import pcm_float
from chord_score_variants import score_variants
from guitarset_benchmark import evaluate_layer,load_reference,parse_chord,TEMPLATES,KNOWN_TIMING

BASE=ROOT/'dataset/integration_review/runs/harmonic_ablation_20261105_v1'
OUT=ROOT/'dataset/integration_review/runs/supported_harmonics_20261105_v1'

def process(path):
    old=json.loads(path.read_text());rate,x=wavfile.read(old['audio'],mmap=True);times=np.array(old['times']);sal=[]
    for t in times:
        start=round(t*rate)-WINDOW//2;s,_,_=supported_salience(pcm_float(x[start:start+WINDOW]),rate);sal.append(s)
    sal=np.array(sal)
    if old['domain']=='guitarset':layers,_=load_reference(old['annotation'])
    else:
        layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (l.split() for l in Path(old['annotation']).read_text().splitlines() if l.strip())]}
    branches={}
    for scorer,(scores,rank,usable) in score_variants(sal).items():
        if scorer not in ('legacy','cosine'):continue
        name='supported_'+scorer;branches[name]={}
        for layer,events in layers.items():
            result=evaluate_layer(times,rank,scores,usable,events);result['seventh_diagnosis']=diagnose(sal,times,result);qs={}
            for f in result['frames']:
                ref=parse_chord(f['reference']);q=next((c['quality'] for c in TEMPLATES if c['root_pc']==ref['root_pc'] and tuple(c['pcs'])==ref['pcs']),'OOV')
                cc=qs.setdefault(q,Counter());cc['evaluated']+=1;cc['top1']+=int(f['correct_top1'])
            result['per_quality']={q:dict(c) for q,c in qs.items()};branches[name][layer]=result
    return dict(id=old['id'],domain=old['domain'],audio=old['audio'],annotation=old['annotation'],times=old['times'],salience=sal.tolist(),branches=branches)

def main():
    if OUT.exists():raise FileExistsError(OUT)
    (OUT/'records').mkdir(parents=True)
    config=dict(hypothesis='Harmonic NNLS reduces seventh weakness but increases false notes. Require fundamental local peak using existing12%global threshold,65..1600Hz; MIDI candidatesD2..E6',
        training=False,parameter_sweep=False,source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['supported_harmonic_features.py','benchmark_supported_harmonics.py','harmonic_chord_features.py']})
    (OUT/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    paths=sorted((BASE/'records').glob('*.json'));records=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for i,future in enumerate(as_completed([pool.submit(process,p) for p in paths])):
            r=future.result();records.append(r);(OUT/'records'/(r['id']+'.json')).write_text(json.dumps(r,indent=2),encoding='utf-8')
            if i%25==0:print(i+1,'/',len(paths),flush=True)
    summary={}
    for domain in ['guitarset','idmt']:
        items=[r for r in records if r['domain']==domain and r['id'] not in KNOWN_TIMING];branches={}
        for b in ['supported_legacy','supported_cosine']:
            branches[b]={}
            for layer in (['nominal','performed'] if domain=='guitarset' else ['nominal']):
                c=Counter();d=Counter();qs={}
                for r in items:
                    result=r['branches'][b][layer];c.update(result['counts']);d.update(result['seventh_diagnosis']['counts'])
                    for q,v in result['per_quality'].items():qs.setdefault(q,Counter()).update(v)
                branches[b][layer]=dict(counts=dict(c),seventh_diagnosis=dict(d),per_quality={q:dict(v) for q,v in qs.items()})
        summary[domain]=dict(files=len(items),branches=branches)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print('Completed',len(records),flush=True)

if __name__=='__main__':main()
