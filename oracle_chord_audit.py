"""Oracle-only scoring diagnostics: annotations are deliberately the input.

Never a detector benchmark. No training, model changes, or annotation edits.
"""
import json
import hashlib
from collections import Counter
from pathlib import Path
import numpy as np
from guitarset_benchmark import TEMPLATES,rank_saliences,parse_chord,load_reference,evaluate_layer,KNOWN_TIMING

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/integration_review/runs/oracle_chord_audit_20261105_v1'

def note_salience(notes,t,count_instances=False):
    pitches=[round(n['midi']) for n in notes if n['start']<=t<n['end']]
    pcs=[m%12 for m in pitches];sal=np.zeros(12)
    for pc in (pcs if count_instances else set(pcs)):sal[pc]+=1
    return sal/max(sal.sum(),1),pitches

def diagnose_frame(sal,reference,precomputed=None):
    ref=parse_chord(reference)
    scores,rank,usable=rank_saliences(np.asarray(sal)[None,:]) if precomputed is None else precomputed
    top=TEMPLATES[rank[0,0]] if usable[0] else None
    indices=[i for i,c in enumerate(TEMPLATES) if c['root_pc']==ref['root_pc'] and tuple(c['pcs'])==ref['pcs']]
    observed=set(np.where(np.asarray(sal)>0)[0].tolist());missing=sorted(set(ref['pcs'])-observed);extra=sorted(observed-set(ref['pcs']))
    ties=[TEMPLATES[i]['symbol'] for i in rank[0] if np.isclose(scores[0,i],scores[0,rank[0,0]],rtol=0,atol=1e-12)] if usable[0] else []
    target_tied=bool(indices and usable[0] and np.isclose(scores[0,indices[0]],scores[0,rank[0,0]],rtol=0,atol=1e-12))
    correct=bool(top and indices and rank[0,0]==indices[0])
    if correct:category='correct'
    elif not indices:category='dictionary_missing'
    elif not usable[0]:category='fewer_than_three_active_pcs'
    elif missing:category='reference_pcs_missing'
    elif extra:category='extra_observed_pcs'
    elif target_tied:category='exact_pcs_root_or_quality_tie'
    else:category='exact_pcs_scoring_error'
    return dict(category=category,correct_top1=correct,representable=bool(indices),missing_pcs=missing,extra_pcs=extra,
        observed_pcs=sorted(observed),reference_pcs=list(ref['pcs']),reference_root_pc=ref['root_pc'],
        target_at_top_score=target_tied,top_score_ties=ties,top1=top['symbol'] if top else None,
        same_pitch_class_templates=[c['symbol'] for c in TEMPLATES if tuple(c['pcs'])==ref['pcs']])

def main():
    if (OUT/'summary.json').exists():raise FileExistsError(OUT)
    (OUT/'records').mkdir(parents=True,exist_ok=True)
    dictionary=[]
    for c in TEMPLATES:
        s=np.zeros(12);s[c['pcs']]=1/len(c['pcs']);label=str(c['root_pc'])+':'+c['quality']
        scores,rank,usable=rank_saliences(s[None,:]);idx=next(i for i,t in enumerate(TEMPLATES) if t is c)
        tie=[TEMPLATES[i]['symbol'] for i in rank[0] if usable[0] and np.isclose(scores[0,i],scores[0,rank[0,0]],rtol=0,atol=1e-12)]
        dictionary.append(dict(symbol=c['symbol'],quality=c['quality'],pcs=c['pcs'],top1=TEMPLATES[rank[0,0]]['symbol'] if usable[0] else None,
            correct_top1=bool(usable[0] and rank[0,0]==idx),reference_at_top_score=bool(usable[0] and np.isclose(scores[0,idx],scores[0,rank[0,0]],rtol=0,atol=1e-12)),ties=tie))
    records=[]
    for path in sorted((ROOT/'dataset/integration_review/runs/cut_audio_features_20261105_v1/records').glob('*.json')):
        old=json.loads(path.read_text())
        if old['domain']!='guitarset' or old['id'] in KNOWN_TIMING:continue
        annotation=Path(old['annotation'])
        if hashlib.sha256(annotation.read_bytes()).hexdigest()!=old['annotation_sha256']:raise ValueError('Annotation changed')
        layers,notes=load_reference(annotation);times=np.array(old['times']);point=np.array([note_salience(notes,t)[0] for t in times]);instances=np.array([note_salience(notes,t,True)[0] for t in times]);branches={}
        for layer,events in layers.items():
            group={}
            # Reuse the frozen evaluator's exact stable-frame selection.
            scores,rank,usable=rank_saliences(point);selected=evaluate_layer(times,rank,scores,usable,events)['frames']
            reference_sal=np.zeros_like(point)
            for f in selected:
                i=int(np.argmin(abs(times-f['time_s'])));reference_sal[i,f['reference_pcs']]=1/len(f['reference_pcs'])
            for name,sal in [('annotated_note_pcs',point),('annotated_note_counts',instances),('reference_chord_pcs',reference_sal)]:
                scores,rank,usable=rank_saliences(sal);result=evaluate_layer(times,rank,scores,usable,events)
                categories=Counter();flags=Counter();frames=[]
                for f in result['frames']:
                    i=int(np.argmin(abs(times-f['time_s'])));d=diagnose_frame(sal[i],f['reference'],(scores[i:i+1],rank[i:i+1],usable[i:i+1]));categories[d['category']]+=1
                    flags.update(exact_pc_set=int(not d['missing_pcs'] and not d['extra_pcs']),missing_reference_pc=int(bool(d['missing_pcs'])),extra_pc=int(bool(d['extra_pcs'])),reference_at_top_score=int(d['target_at_top_score']))
                    frames.append(dict(time_s=f['time_s'],reference=f['reference'],annotated_active_midi=note_salience(notes,f['time_s'])[1],**d))
                group[name]=dict(counts=result['counts'],categories=dict(categories),flags=dict(flags),frames=frames)
            branches[layer]=group
        r=dict(id=old['id'],audio=old['audio'],annotation=str(annotation),annotation_sha256=old['annotation_sha256'],branches=branches);records.append(r)
        (OUT/'records'/path.name).write_text(json.dumps(r,indent=2),encoding='utf-8')
    summary={}
    for layer in ['nominal','performed']:
        summary[layer]={}
        for name in ['annotated_note_pcs','annotated_note_counts','reference_chord_pcs']:
            counts=Counter();cats=Counter();flags=Counter()
            for r in records:
                result=r['branches'][layer][name];counts.update(result['counts']);cats.update(result['categories']);flags.update(result['flags'])
            summary[layer][name]=dict(counts=dict(counts),categories=dict(cats),flags=dict(flags))
    result=dict(files=len(records),layers=summary,dictionary_self_test=dict(total=len(dictionary),top1=sum(r['correct_top1'] for r in dictionary),
        reference_at_top_score=sum(r['reference_at_top_score'] for r in dictionary),insufficient=sum(not r['ties'] for r in dictionary)),
        scope='Oracle diagnostic only: reference input, no acoustic/model accuracy claim')
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');(OUT/'dictionary_self_test.json').write_text(json.dumps(dictionary,indent=2),encoding='utf-8')
    (OUT/'config.json').write_text(json.dumps(dict(branches=['notePCuniform','noteInstanceCounts','labelPCuniform'],scorer='Frozen existing rank_saliences',
        time_grid='Frozen1sgrid, same stable selection as previous4,886frames',training=False,model_inference=False,
        limitations=['note_midi annotations are estimates, not infallible sounding truth','Chord labels describe a segment; instantaneous notes may differ','Chord-label oracle deliberately leaks reference input; diagnostic only'],
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['oracle_chord_audit.py','guitarset_benchmark.py']}),indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
