"""Separate delayed/old-side failures from genuinely absent new chord labels."""
from collections import Counter,defaultdict
import gzip
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()
sys.path.insert(0,str(ROOT/'engine'))
from labels import load_reference
from metrics import reference,identity


def main():
    manifest=json.loads((RUN/'manifest.json').read_text());output=[];groups=defaultdict(Counter)
    for mode in ['github','patched']:
        for r in manifest['records']:
            if r['known_timing_issue']:continue
            path=RUN/mode/'records'/(r['id']+'.json');dense=RUN/mode/'dense'/(r['id']+'_0.2.jsonl.gz')
            if not path.exists() or not dense.exists():continue
            d=json.loads(path.read_text(encoding='utf-8'))
            if d['status']!='complete':continue
            if r['dataset']=='guitarset':layers,_=load_reference(r['annotation'])
            else:layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (l.split() for l in Path(r['annotation']).read_text().splitlines() if l.strip())]}
            targets=[]
            for layer,block in d['temporal']['0.2'].items():
                for t in block['transitions']:
                    if not t['stable_intervals'] or not t['representable']:continue
                    event=next(e for e in layers[layer] if abs(e['time']-t['time_s'])<1e-7)
                    ref=reference(event['value']);target=(ref['root_pc'],tuple(ref['pcs']))
                    targets.append(dict(mode=mode,id=r['id'],dataset=r['dataset'],layer=layer,**t,end_s=event['time']+event['duration'],
                                        target=target,new_present={v:False for v in ['A','B','U_context','B_frame']},early_B=False))
            targets.sort(key=lambda t:t['time_s']);active=[];next_idx=0
            with gzip.open(dense,'rt',encoding='utf-8') as f:
                for line in f:
                    row=json.loads(line);clock=row['time_s']
                    while next_idx<len(targets) and targets[next_idx]['time_s']<=clock+1e-9:
                        active.append(targets[next_idx]);next_idx+=1
                    active=[t for t in active if clock<t['end_s']-1e-9]
                    for target in active:
                        for v in target['new_present']:
                            c=row[v]
                            if len(c)==1 and identity(c[0])==target['target']:
                                target['new_present'][v]=True
                                if v=='B' and clock<target['time_s']+.5:target['early_B']=True
            for t in targets:
                p=t['new_present'];t['confirmed_lookahead_interval_omission']=p['U_context'] and not p['B_frame']
                t['confirmed_grid_interval_omission']=p['B_frame'] and not p['B']
                t['B_absent_entire_interval']=not p['B']
                t['B_delayed_only']=p['B'] and not t['early_B']
                if t['B_lost_A']:
                    t['A_B_failure_kind']='new_label_absent_entire_interval' if not p['B'] else 'new_label_delayed_beyond_half_second' if not t['early_B'] else 'old_side_not_reproduced'
                key=mode+'_'+r['dataset']+'_'+t['layer'];g=groups[key];g['stable_representable_transitions']+=1
                for reason in ['confirmed_lookahead_interval_omission','confirmed_grid_interval_omission','B_absent_entire_interval','B_delayed_only']:g[reason]+=int(t[reason])
                if t.get('confirmed_lookahead_interval_omission') or t.get('confirmed_grid_interval_omission') or t.get('B_lost_A'):output.append(t)
    (RUN/'transition_diagnosis.json').write_text(json.dumps(dict(groups=groups,cases=output),ensure_ascii=False,indent=2),encoding='utf-8')
    print({k:dict(v) for k,v in groups.items()})


if __name__=='__main__':main()
