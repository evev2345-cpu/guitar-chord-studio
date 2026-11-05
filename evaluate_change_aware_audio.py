"""Frozen audio-only boundary detector vs fixed short pooling; no training."""
import json
import hashlib
from collections import Counter
from pathlib import Path
import numpy as np
from audio_change_pool import detect_changes,clipped_pool,CONTEXT,HEIGHT,PROMINENCE,MIN_DISTANCE
from temporal_audio_pool import pooled_chroma
from guitarset_benchmark import load_reference,parse_chord,TEMPLATES,rank_saliences
from benchmark_cut_audio import evaluate_arrays
from compare_guitar_stem_accuracy import safe_evaluate

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/integration_review/runs/change_aware_audio_20261105_v1'
PRED=ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions'
METHODS=['instant','fixed02','fixed04','clipped02','clipped04']

def make_inputs(times,frames,query):
    boundaries,scores,indices=detect_changes(times,frames)
    arrays=dict(instant=pooled_chroma(times,frames,query),fixed02=pooled_chroma(times,frames,query,.2),fixed04=pooled_chroma(times,frames,query,.4));supports={}
    for width,name in [(.2,'clipped02'),(.4,'clipped04')]:arrays[name],supports[name]=clipped_pool(times,frames,query,width,boundaries)
    return arrays,boundaries,scores,supports

def match_changes(predicted,events,start,end,tolerance=.2):
    refs=[]
    for a,b in zip(events,events[1:]):
        x=parse_chord(a['value']);y=parse_chord(b['value'])
        if x and y and (x['root_pc'],x['pcs'])!=(y['root_pc'],y['pcs']) and start<=b['time']<=end:refs.append(float(b['time']))
    predicted=[float(t) for t in predicted if start<=t<=end];pairs=sorted((abs(p-r),i,j) for i,p in enumerate(predicted) for j,r in enumerate(refs) if abs(p-r)<=tolerance)
    used_p=set();used_r=set();errors=[]
    for _,i,j in pairs:
        if i in used_p or j in used_r:continue
        used_p.add(i);used_r.add(j);errors.append(predicted[i]-refs[j])
    return dict(tp=len(errors),fp=len(predicted)-len(errors),fn=len(refs)-len(errors),signed_errors_s=errors,reference_times_s=refs)

def decorate(result):
    for f in result['frames']:
        ref=parse_chord(f['reference']);reference=next((c for c in TEMPLATES if c['root_pc']==ref['root_pc'] and tuple(c['pcs'])==ref['pcs']),None);f['false_added_extension']=False
        if reference and reference['quality'] in ['major','minor'] and f['top3']:
            top=f['top3'][0];template=next(c for c in TEMPLATES if c['root_pc']==top['root_pc'] and c['quality']==top['quality'])
            f['false_added_extension']=bool(top['root_pc']==ref['root_pc'] and top['quality'] in ['7','maj7','m7','m7b5','dim7','add9','6','m6'] and set(template['pcs'])-set(ref['pcs']))

def main():
    if (OUT/'summary.json').exists():raise FileExistsError(OUT)
    (OUT/'records').mkdir(exist_ok=True)
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));freeze=read(OUT/'reference_freeze_sha256.json')
    assert hashlib.sha256((OUT/'new_references.json').read_bytes()).hexdigest()==freeze['sha256']
    config=dict(training=False,methods=METHODS,note_threshold=.3,scorer='Existing coverage unchanged',
        detection=dict(left_right_context_s=CONTEXT,height=HEIGHT,prominence=PROMINENCE,min_distance_s=MIN_DISTANCE,energy_gate=.3),
        pooling='Centered fixed0.2/0.4s; clipped to nearest detected changes, no forced abstention; no annotation passed into detection',
        transition_evaluation='One-to-one nearest matching within0.2s of root/PC-set reference changes, not display inversion changes',
        reference_freeze_sha256=freeze['sha256'],source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['audio_change_pool.py','evaluate_change_aware_audio.py']})
    (OUT/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8');records=[]
    base=ROOT/'dataset/integration_review/runs/temporal_audio_20261105_v1/records'
    for path in sorted(base.glob('*.json')):
        old=read(path);source=read(ROOT/'dataset/integration_review/runs/cut_audio_features_20261105_v1/records'/path.name)
        with np.load(PRED/(old['id']+'_raw.npz')) as d:grid=d['times'];frames=d['note']
        query=np.array(old['times']);arrays,boundaries,scores,supports=make_inputs(grid,frames,query)
        if old['domain']=='guitarset':layers,_=load_reference(source['annotation'])
        else:layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (l.split() for l in Path(source['annotation']).read_text().splitlines() if l.strip())]}
        result=evaluate_arrays(arrays,query,layers);transition={}
        for layer,events in layers.items():
            transition[layer]=match_changes(boundaries,events,float(grid[0]+CONTEXT),float(grid[-1]-CONTEXT))
            for name in METHODS:decorate(result[name][layer])
            for new,previous in [('instant','instant'),('fixed02','max_0.2s'),('fixed04','max_0.4s')]:assert result[new][layer]['counts']==old['branches'][previous][layer]['counts']
        record=dict(id=old['id'],domain=old['domain'],boundaries_s=boundaries.tolist(),transition=transition,supports=supports,branches=result)
        records.append(record);(OUT/'records'/path.name).write_text(json.dumps(record,indent=2),encoding='utf-8')
    summary={}
    for domain in ['guitarset','idmt']:
        items=[r for r in records if r['domain']==domain];group={}
        for method in METHODS:
            group[method]={}
            for layer in (['nominal','performed'] if domain=='guitarset' else ['nominal']):
                c=Counter();diag=Counter();qs={}
                for r in items:
                    result=r['branches'][method][layer];c.update(result['counts']);c['false_added_extension']+=sum(f['false_added_extension'] for f in result['frames']);diag.update(result['seventh_diagnosis']['counts'])
                    for q,v in result['per_quality'].items():qs.setdefault(q,Counter()).update(v)
                group[method][layer]=dict(counts=dict(c),seventh_diagnosis=dict(diag),per_quality={q:dict(v) for q,v in qs.items()})
        transitions={}
        for layer in (['nominal','performed'] if domain=='guitarset' else ['nominal']):
            c=Counter();errors=[]
            for r in items:
                for k in ['tp','fp','fn']:c[k]+=r['transition'][layer][k]
                errors.extend(r['transition'][layer]['signed_errors_s'])
            transitions[layer]=dict(counts=dict(c),precision=c['tp']/max(1,c['tp']+c['fp']),recall=c['tp']/max(1,c['tp']+c['fn']),median_abs_error_s=float(np.median(np.abs(errors))) if errors else None)
        summary[domain]=dict(files=len(items),branches=group,transition=transitions)
    reviews=[('old',PRED/'tutorial_raw.npz',194.,read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json')['references']),
             ('new',OUT/'new_predictions/new_tutorial_raw.npz',250.,read(OUT/'new_references.json')['references'])]
    for scope,path,offset,refs in reviews:
        with np.load(path) as d:grid=d['times'];frames=d['note']
        arrays,boundaries,scores,supports=make_inputs(grid,frames,[r['pts']-offset for r in refs]);rows=[]
        for i,ref in enumerate(refs):
            result={}
            for name,sal in arrays.items():
                sc,rk,ok=rank_saliences(sal[i:i+1]);top=[dict(root_pc=TEMPLATES[j]['root_pc'],quality=TEMPLATES[j]['quality'],concert_symbol=TEMPLATES[j]['symbol'],score=float(sc[0,j])) for j in rk[0]] if ok[0] else []
                result[name]=dict(top3=top[:3],evaluation=safe_evaluate(top,ref))
            rows.append(dict(reference=ref,branches=result))
        review=dict(rows=rows,boundaries_source_s=(boundaries+offset).tolist(),supports={n:[{k:(v+offset if k.endswith('_s') else v) for k,v in s.items()} for s in ss] for n,ss in supports.items()},
            summary={n:{k:sum(r['branches'][n]['evaluation'][k] for r in rows) for k in ['exact_top1','exact_top3','root_top1']} for n in METHODS})
        (OUT/(scope+'_tutorial.json')).write_text(json.dumps(review,indent=2),encoding='utf-8');print(scope,review['summary'])
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print('Complete',len(records),flush=True)

if __name__=='__main__':main()
