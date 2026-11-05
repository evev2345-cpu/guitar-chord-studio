"""Evaluate frozen Basic Pitch outputs using the existing unmodified chord scorer."""
import json
import hashlib
from collections import Counter
from pathlib import Path
import numpy as np
from basic_pitch_adapter import sample_prediction
from benchmark_cut_audio import evaluate_arrays,aggregate,ROOT
from guitarset_benchmark import load_reference,rank_saliences,TEMPLATES,KNOWN_TIMING
from compare_guitar_stem_accuracy import safe_evaluate

OUT=ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2'
BASE=ROOT/'dataset/integration_review/runs/cut_audio_features_20261105_v1'
BRANCHES=['raw_frames','raw_events','cut_frames','cut_events']

def load_model(id,mode):
    path=OUT/'predictions'/(id+'_'+mode+'.npz');meta=json.loads(path.with_suffix('.json').read_text())
    with np.load(path) as data:times=data['times'];frames=data['note']
    return times,frames,meta

def main():
    if (OUT/'summary.json').exists():raise FileExistsError(OUT/'summary.json')
    (OUT/'records').mkdir(exist_ok=True);records=[];read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    for path in sorted((BASE/'records').glob('*.json')):
        old=read(path);times=np.array(old['times']);branches={};pc={};deltas={}
        if old['domain']=='guitarset':layers,notes=load_reference(old['annotation'])
        else:
            notes=[];layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (l.split() for l in Path(old['annotation']).read_text().splitlines() if l.strip())]}
        for mode in ['raw','cut']:
            grid,frames,meta=load_model(old['id'],mode)
            if meta['source_sha256']!=old['audio_sha256']:raise ValueError('Source mismatch')
            for rep in ['frames','events']:
                name=mode+'_'+rep;sal,delta,sets=sample_prediction(grid,frames,meta['note_events'],times,rep)
                branches.update(evaluate_arrays({name:sal},times,layers));deltas[name]=max(abs(v) for v in delta);c=Counter()
                if notes:
                    for t,pred in zip(times,sets):
                        truth={round(n['midi'])%12 for n in notes if n['start']<=t<n['end']};est={m%12 for m in pred};c.update(tp=len(truth&est),fp=len(est-truth),fn=len(truth-est),windows=1)
                    pc[name]=dict(c)
        r=dict(id=old['id'],domain=old['domain'],times=old['times'],branches=branches,note_pc_counts=pc,max_frame_time_delta_s=deltas)
        records.append(r);(OUT/'records'/path.name).write_text(json.dumps(r,indent=2),encoding='utf-8')
    summary={}
    for domain in ['guitarset','idmt']:
        items=[r for r in records if r['domain']==domain and r['id'] not in KNOWN_TIMING];group={}
        for b in BRANCHES:
            group[b]={}
            for layer in (['nominal','performed'] if domain=='guitarset' else ['nominal']):
                counts=Counter();diag=Counter();qs={}
                for r in items:
                    result=r['branches'][b][layer];counts.update(result['counts']);diag.update(result['seventh_diagnosis']['counts'])
                    for q,v in result['per_quality'].items():qs.setdefault(q,Counter()).update(v)
                group[b][layer]=dict(counts=dict(counts),seventh_diagnosis=dict(diag),per_quality={q:dict(v) for q,v in qs.items()})
            if domain=='guitarset':
                c=Counter()
                for r in items:c.update(r['note_pc_counts'][b])
                p=c['tp']/max(1,c['tp']+c['fp']);rec=c['tp']/max(1,c['tp']+c['fn'])
                group[b]['note_pc']=dict(counts=dict(c),precision=p,recall=rec,f1=2*p*rec/max(p+rec,1e-12))
        summary[domain]=dict(files=len(items),branches=group)
    refs=read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json')['references'];rows=[]
    for ref in refs:
        result={}
        for mode in ['raw','cut']:
            grid,frames,meta=load_model('tutorial',mode)
            for rep in ['frames','events']:
                name=mode+'_'+rep;sal,_,_=sample_prediction(grid,frames,meta['note_events'],[ref['pts']-194],rep);scores,rank,usable=rank_saliences(sal)
                ranked=[dict(root_pc=TEMPLATES[j]['root_pc'],quality=TEMPLATES[j]['quality'],concert_symbol=TEMPLATES[j]['symbol'],score=float(scores[0,j])) for j in rank[0]] if usable[0] else []
                result[name]=dict(top3=ranked[:3],evaluation=safe_evaluate(ranked,ref))
        rows.append(dict(reference=ref,branches=result))
    tutorial=dict(rows=rows,summary={b:{k:sum(r['branches'][b]['evaluation'][k] for r in rows) for k in ['exact_top1','exact_top3','root_top1']} for b in BRANCHES})
    (OUT/'tutorial.json').write_text(json.dumps(tutorial,indent=2),encoding='utf-8')
    config=dict(training=False,frame_threshold=.3,scorer='Unmodified coverage score',pitch_range_midi=[38,88],
                sampling='Same evaluation timestamps as cut_audio_features, model sees its official2s context; baseline sees8192samples',
                clock='Input-window sample positions, overlap30/trim15, no reference-fitted offset; original0.4.0 truncated grid superseded',
                source_hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['basic_pitch_adapter.py','basic_pitch_clock.py','basic_pitch_worker.py','evaluate_basic_pitch.py']},
                limitations='GuitarSet is a Basic Pitch training corpus; results are diagnostic, not independent held-out generalization. Fixed existing dictionary excludes many tensions.')
    (OUT/'evaluation_config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(tutorial['summary'],indent=2));print('Evaluated',len(records),flush=True)

if __name__=='__main__':main()
