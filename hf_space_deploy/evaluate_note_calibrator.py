"""Evaluate the frozen correction checkpoint/validation-selected thresholds."""
import json
from collections import Counter
import numpy as np
from audio_note_calibrator import corrected_probabilities,probabilities_to_chroma
from train_audio_note_calibrator import ROOT,OUT,PRED,split_for
from benchmark_cut_audio import evaluate_arrays
from guitarset_benchmark import KNOWN_TIMING,load_reference,rank_saliences,TEMPLATES
from compare_guitar_stem_accuracy import safe_evaluate

BRANCHES=['baseline_default','baseline_calibrated','corrected_default','corrected_calibrated']

def branches(p,weights,thresholds):
    corrected=corrected_probabilities(p,weights)
    return dict(baseline_default=probabilities_to_chroma(p,.3),baseline_calibrated=probabilities_to_chroma(p,thresholds['baseline']),
                corrected_default=probabilities_to_chroma(corrected,.3),corrected_calibrated=probabilities_to_chroma(corrected,thresholds['corrected']))

def main():
    if (OUT/'evaluation_summary.json').exists():raise FileExistsError(OUT)
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));training=read(OUT/'training_result.json');thresholds=training['selected_thresholds']
    with np.load(OUT/'weights.npz') as d:weights={k:d[k] for k in d.files}
    (OUT/'evaluation').mkdir(exist_ok=True);records=[]
    base=ROOT/'dataset/integration_review/runs/cut_audio_features_20261105_v1/records'
    for file in sorted(base.glob('*.json')):
        old=read(file)
        if old['id'] in KNOWN_TIMING:continue
        with np.load(PRED/(old['id']+'_raw.npz')) as d:
            times=d['times'];idx=np.array([int(np.argmin(abs(times-t))) for t in old['times']]);p=d['note'][idx,17:68]
        arrays=branches(p,weights,thresholds)
        if old['domain']=='guitarset':layers,_=load_reference(old['annotation']);scope=split_for(old['id'])
        else:
            from pathlib import Path
            layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (l.split() for l in Path(old['annotation']).read_text().splitlines() if l.strip())]};scope='idmt_external'
        result=evaluate_arrays(arrays,np.array(old['times']),layers)
        previous=read(ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2/records'/file.name)
        for layer in layers:
            assert result['baseline_default'][layer]['counts']==previous['branches']['raw_frames'][layer]['counts']
        record=dict(id=old['id'],scope=scope,branches=result);records.append(record)
        (OUT/'evaluation'/file.name).write_text(json.dumps(record,indent=2),encoding='utf-8')
    summary={}
    for scope in ['train','validation','test','idmt_external']:
        items=[r for r in records if r['scope']==scope];group={}
        for name in BRANCHES:
            group[name]={}
            for layer in (['nominal'] if scope=='idmt_external' else ['nominal','performed']):
                c=Counter();q={};diag=Counter()
                for r in items:
                    result=r['branches'][name][layer];c.update(result['counts']);diag.update(result['seventh_diagnosis']['counts'])
                    for quality,counts in result['per_quality'].items():q.setdefault(quality,Counter()).update(counts)
                group[name][layer]=dict(counts=dict(c),per_quality={k:dict(v) for k,v in q.items()},seventh_diagnosis=dict(diag))
        summary[scope]=dict(files=len(items),branches=group)
    refs=read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json')['references'];rows=[]
    with np.load(PRED/'tutorial_raw.npz') as d:
        times=d['times'];p=d['note'][[int(np.argmin(abs(times-(r['pts']-194)))) for r in refs],17:68]
    for i,ref in enumerate(refs):
        result={}
        for name,sal in branches(p,weights,thresholds).items():
            scores,rank,usable=rank_saliences(sal[i:i+1]);top=[dict(root_pc=TEMPLATES[j]['root_pc'],quality=TEMPLATES[j]['quality'],concert_symbol=TEMPLATES[j]['symbol'],score=float(scores[0,j])) for j in rank[0]] if usable[0] else []
            result[name]=dict(top3=top[:3],evaluation=safe_evaluate(top,ref))
        rows.append(dict(reference=ref,branches=result))
    tutorial=dict(rows=rows,summary={b:{k:sum(r['branches'][b]['evaluation'][k] for r in rows) for k in ['exact_top1','exact_top3','root_top1']} for b in BRANCHES})
    (OUT/'tutorial.json').write_text(json.dumps(tutorial,indent=2),encoding='utf-8');(OUT/'evaluation_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('Thresholds',thresholds);print('Tutorial',tutorial['summary'])
    for scope in ['test','idmt_external']:
        print(scope,{b:{l:round(100*v['counts']['top1']/v['counts']['evaluated'],2) for l,v in x.items()} for b,x in summary[scope]['branches'].items()})

if __name__=='__main__':main()
