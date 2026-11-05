"""Evaluation-only IDMT snapshots. No labels enter feature extraction or scoring."""
import json
import hashlib
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.io import wavfile
from audio_analysis import features
from guitarset_benchmark import parse_chord,TEMPLATES
from chord_score_variants import score_variants

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/integration_review/runs/idmt_chords_scores_20261105_v2'

def parse_label(label):
    # Expand the documented power-chord shorthand without changing frozen GuitarSet code.
    return parse_chord(label.replace(':5',':(1,5)'))

def pcm_float(x):
    if np.issubdtype(x.dtype,np.signedinteger):return x.astype(float)/(2**(np.iinfo(x.dtype).bits-1))
    if np.issubdtype(x.dtype,np.floating) and np.isfinite(x).all():return x.astype(float)
    raise ValueError('Unsupported PCM')

def snapshot(x,rate,t):
    start=round(t*rate)-4096
    if start<0 or start+8192>len(x):raise ValueError('Incomplete snapshot')
    ev,_=features(pcm_float(x[start:start+8192]),rate,offset=start/rate)
    return ev['pitch_class_salience'][0]['salience']

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True);records=[]
    base=ROOT/'IDMT_SMT_Chords/extracted/IDMT-SMT-CHORDS'
    for path in sorted(base.rglob('*.wav')):
        rate,x=wavfile.read(path,mmap=True)
        if rate!=44100 or x.ndim!=1:raise ValueError('Unexpected format')
        labels=[(float(a),float(b),c) for a,b,c in (l.split() for l in next(path.parent.glob('*.lab')).read_text().splitlines() if l.strip())]
        if labels[-1][1]>len(x)/rate:raise ValueError('Annotation outside audio')
        rows=[]
        for a,b,label in labels:
            mid=(a+b)/2
            # Three real audio windows, not duplicated frames. Context never crosses segment boundaries.
            sal=np.array([snapshot(x,rate,mid+d) for d in [-.1,0,.1]])
            ref=parse_label(label);pred={}
            for name,(scores,rank,usable) in score_variants(sal).items():
                top=[TEMPLATES[j] for j in rank[1,:3]] if usable[1] else []
                match=lambda c:c['root_pc']==ref['root_pc'] and tuple(c['pcs'])==ref['pcs']
                pred[name]=dict(top1=bool(top and match(top[0])),top3=any(match(c) for c in top),
                    root_top1=bool(top and top[0]['root_pc']==ref['root_pc']),abstain=not bool(usable[1]),
                    predictions=[c['symbol'] for c in top])
            rows.append(dict(time_s=mid,label=label,quality=label.split(':')[1].split('/')[0],representable=ref['representable'],variants=pred))
        record=dict(file=str(path),domain=path.parent.name,rate=rate,dtype=str(x.dtype),duration_s=len(x)/rate,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=rows)
        records.append(record);(OUT/(path.stem+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
        print('Completed',len(records),path.name,flush=True)
    summary={}
    for domain in ['guitar','non_guitar']:
        rows=[r for rec in records if rec['domain']==domain for r in rec['rows']]
        group={}
        for variant in ['legacy','cosine','cosine_context']:
            def counts(items):
                c=Counter(evaluated=len(items),representable=sum(r['representable'] for r in items))
                for r in items:c.update({k:int(v) for k,v in r['variants'][variant].items() if k!='predictions'})
                return dict(c)
            group[variant]=dict(counts=counts(rows),per_quality={q:counts([r for r in rows if r['quality']==q]) for q in sorted({r['quality'] for r in rows})})
        summary[domain]=group
    config=dict(training=False,parameter_fitting=False,windows='8192 samples centered at segment midpoint +-100ms; center scored',
                frequency_candidates_hz=[65,1600],waveform_bandcut=False,inversion_metric=False,
                limitations='Synthetic MIDI-rendered audio; midpoint only; not comparable to bandcut GuitarSet protocol. Literal Harte bass parsing: non_guitar minor/7/hdim7 inversion labels may add non-chord tones. OOV kept in denominator; do not interpret as clean quality ground truth.',
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                scorer_sha256=hashlib.sha256((ROOT/'chord_score_variants.py').read_bytes()).hexdigest())
    (OUT/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    assert sum(len(r['rows']) for r in records)==7398
    assert all(r['representable'] for rec in records if rec['domain']=='guitar' for r in rec['rows'])

if __name__=='__main__':main()
