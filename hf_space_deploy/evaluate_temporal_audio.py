"""Same scorer, fixed pretrained activations, short time-window ablation."""
import json
import hashlib
from collections import Counter
from pathlib import Path
import numpy as np
from temporal_audio_pool import all_variants,VARIANTS
from guitarset_benchmark import load_reference,KNOWN_TIMING,TEMPLATES,rank_saliences
from benchmark_cut_audio import evaluate_arrays
from compare_guitar_stem_accuracy import safe_evaluate

ROOT=Path(__file__).resolve().parent
PRED=ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions'
OUT=ROOT/'dataset/integration_review/runs/temporal_audio_20261105_v1'

def crossing(events,t,radius):
    event=next((e for e in events if e['time']<=t<e['time']+e['duration']),None)
    return event is None or t-radius<event['time'] or t+radius>event['time']+event['duration']

def main():
    if OUT.exists():raise FileExistsError(OUT)
    (OUT/'records').mkdir(parents=True);read=lambda p:json.loads(p.read_text(encoding='utf-8'));records=[]
    config=dict(training=False,threshold=.3,pitch_range_midi=[38,88],input='Frozen raw-input BasicPitch model; no added note correction, no waveform frequency cut',
        widths_s=[.1,.2,.4,.8],pooling=['max','mean'],scorer='Unchanged existing coverage',
        support='Common audio support for0.8swindow across all branches; no clipping/padding',
        reference_usage='Evaluation strata only: never used to stop, clip or choose pooling windows',
        limitations='Pooling output evidence only; BasicPitch2s inference context remains unchanged. Centered offline windows need future audio. All datasets previously inspected.',
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['temporal_audio_pool.py','evaluate_temporal_audio.py']})
    (OUT/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    for file in sorted((ROOT/'dataset/integration_review/runs/cut_audio_features_20261105_v1/records').glob('*.json')):
        old=read(file)
        if old['id'] in KNOWN_TIMING:continue
        with np.load(PRED/(old['id']+'_raw.npz')) as d:grid=d['times'];frames=d['note']
        original=np.array(old['times']);times=original[(original-.4>=grid[0])&(original+.4<=grid[-1])]
        arrays=all_variants(grid,frames,times)
        if old['domain']=='guitarset':layers,_=load_reference(old['annotation'])
        else:layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (l.split() for l in Path(old['annotation']).read_text().splitlines() if l.strip())]}
        branches=evaluate_arrays(arrays,times,layers)
        previous=read(ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2/records'/file.name)
        for layer,events in layers.items():
            expected=[f for f in previous['branches']['raw_frames'][layer]['frames'] if f['time_s'] in set(times)]
            actual=branches['instant'][layer]['frames'];assert [(f['time_s'],f['correct_top1'],f['correct_top3']) for f in actual]==[(f['time_s'],f['correct_top1'],f['correct_top3']) for f in expected]
            for name in VARIANTS:
                for f in branches[name][layer]['frames']:
                    f['common_clean_0_8s']=not crossing(events,f['time_s'],.4)
                    f['window_crosses_reference_boundary']=crossing(events,f['time_s'],0. if name=='instant' else float(name.split('_')[1][:-1])/2)
        record=dict(id=old['id'],domain=old['domain'],times=times.tolist(),excluded_audio_edge_centers=len(original)-len(times),branches=branches)
        records.append(record);(OUT/'records'/file.name).write_text(json.dumps(record,indent=2),encoding='utf-8')
    summary={}
    for domain in ['guitarset','idmt']:
        items=[r for r in records if r['domain']==domain];result={}
        for name in VARIANTS:
            result[name]={}
            for layer in (['nominal','performed'] if domain=='guitarset' else ['nominal']):
                result[name][layer]={}
                for scope in ['all','common_clean','crossing']:
                    c=Counter()
                    for r in items:
                        for f in r['branches'][name][layer]['frames']:
                            if scope=='common_clean' and not f['common_clean_0_8s']:continue
                            if scope=='crossing' and not f['window_crosses_reference_boundary']:continue
                            c.update(evaluated=1,top1=int(f['correct_top1']),top3=int(f['correct_top3']),abstain=int(not f['top3']))
                    result[name][layer][scope]=dict(c)
        summary[domain]=dict(files=len(items),branches=result)
    refs=read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json')['references'];rows=[]
    with np.load(PRED/'tutorial_raw.npz') as d:arrays=all_variants(d['times'],d['note'],[r['pts']-194 for r in refs])
    for i,ref in enumerate(refs):
        result={}
        for name,sal in arrays.items():
            scores,rank,usable=rank_saliences(sal[i:i+1]);top=[dict(root_pc=TEMPLATES[j]['root_pc'],quality=TEMPLATES[j]['quality'],concert_symbol=TEMPLATES[j]['symbol'],score=float(scores[0,j])) for j in rank[0]] if usable[0] else []
            result[name]=dict(top3=top[:3],evaluation=safe_evaluate(top,ref))
        rows.append(dict(reference=ref,branches=result))
    (OUT/'tutorial.json').write_text(json.dumps(dict(rows=rows,summary={n:{k:sum(r['branches'][n]['evaluation'][k] for r in rows) for k in ['exact_top1','exact_top3','root_top1']} for n in VARIANTS}),indent=2),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print('Completed',len(records),flush=True)

if __name__=='__main__':main()
