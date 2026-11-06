"""Chronological display evaluation on existing actual-video timelines."""
import json
import hashlib
from pathlib import Path
from collections import Counter
import numpy as np
from chord_display_stabilizer import stabilize,identity,CONFIG

ROOT=Path(__file__).resolve().parent
BASE=ROOT/'dataset/integration_review/runs/actual_video_review_20261105_v1'
OUT=ROOT/'dataset/integration_review/runs/stable_video_review_20261105_v1'

def metrics(times,labels):
    values=[identity(c) for c in labels];runs=[];start=0
    for i in range(1,len(values)+1):
        if i==len(values) or values[i]!=values[start]:
            if values[start] is not None:runs.append((i-start)/24)
            start=i
    return dict(frames=len(values),abstain_frames=sum(v is None for v in values),
        all_state_changes=sum(a!=b for a,b in zip(values,values[1:])),
        direct_chord_changes=sum(a is not None and b is not None and a!=b for a,b in zip(values,values[1:])),
        short_candidate_runs_le_0_125s=sum(t<=.125+1e-9 for t in runs))

def main():
    if (OUT/'evaluation.json').exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True,exist_ok=True);manifest=json.loads((BASE/'manifest.json').read_text());result={}
    for case in manifest['cases']:
        raw=json.loads((BASE/(case['id']+'_timeline.json')).read_text());times=np.array([r['video_pts_s'] for r in raw]);refs={r['review_reference']['pts']:r['review_reference'] for r in raw if r['review_reference']};branches={}
        displays={key:stabilize(times,[r['predictions'][key] for r in raw]) for key in ['0.2','0.4']}
        for key,display in displays.items():
            before=[r['predictions'][key]['top3'][0] if r['predictions'][key]['top3'] else None for r in raw];after=[r['display_candidate'] for r in display];checks=[]
            for t,ref in sorted(refs.items()):
                i=int(np.argmin(abs(times-t)));target=(ref['concert_root_pc'],ref['quality'])
                checks.append(dict(pts=t,reference=ref['concert_symbol'],before=identity(before[i])==target,after=identity(after[i])==target,before_candidate=before[i],after_candidate=after[i],status=display[i]['status']))
            delays=[r['confirmation_delay_s'] for r in display if r['confirmation_delay_s'] is not None]
            branches[key]=dict(before=metrics(times,before),after=metrics(times,after),reference_checks=checks,
                before_correct=sum(r['before'] for r in checks),after_correct=sum(r['after'] for r in checks),
                status_counts=dict(Counter(r['status'] for r in display)),max_confirmation_delay_s=max(delays) if delays else None)
        output=[dict(r,stable_predictions={key:displays[key][i] for key in displays}) for i,r in enumerate(raw)]
        (OUT/(case['id']+'_timeline.json')).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');result[case['id']]=branches
    (OUT/'config.json').write_text(json.dumps(dict(stabilizer=CONFIG,training=False,reference_fed_to_stabilizer=False,
        input_timeline_sha256={c['id']:hashlib.sha256((BASE/(c['id']+'_timeline.json')).read_bytes()).hexdigest() for c in manifest['cases']},
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['chord_display_stabilizer.py','evaluate_chord_display.py']}),indent=2),encoding='utf-8')
    (OUT/'evaluation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({c:{k:{'before':v['before'],'after':v['after'],'refs':[v['before_correct'],v['after_correct']]} for k,v in bs.items()} for c,bs in result.items()},indent=2))

if __name__=='__main__':main()
