"""Aggregate frozen evaluation artifacts; never rerun or alter a predictor."""
import csv
from collections import Counter,defaultdict
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()
sys.path.insert(0,str(ROOT/'engine'))
from labels import load_reference
from metrics import collect


def rates(c):
    n=c.get('n',0)
    return dict(c,**{k+'_accuracy':c.get(k,0)/n if n else None for k in ['exact','root','quality']})


def main():
    manifest=json.loads((RUN/'manifest.json').read_text(encoding='utf-8'))
    summary=dict(git_commit=manifest['git_remote_commit'],groups={},errors=[],pending=[],comparison={},excluded_known_timing=[])
    quality_rows=[];confusions=[];transition_rows=[];file_rows=[];paired=defaultdict(Counter)
    for mode in ['github','patched']:
        groups={};records={}
        for r in manifest['records']:
            p=RUN/mode/'records'/(r['id']+'.json')
            if not p.exists():summary['pending'].append(dict(mode=mode,id=r['id']));continue
            d=json.loads(p.read_text(encoding='utf-8'));records[r['id']]=d
            if d['status']!='complete':
                summary['errors'].append(dict(mode=mode,id=r['id'],error=d.get('error'),traceback=d.get('traceback')))
            file_rows.append(dict(mode=mode,id=r['id'],dataset=r['dataset'],status=d['status'],duration_s=d.get('duration_s'),timing=d.get('timing'),separation_status=d.get('separation_status')))
            if r['known_timing_issue']:
                summary['excluded_known_timing'].append(dict(mode=mode,id=r['id']));continue
            if not d.get('branches'):
                if r['dataset']=='guitarset':layers,_=load_reference(r['annotation'])
                else:layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (l.split() for l in Path(r['annotation']).read_text().splitlines() if l.strip())]}
                d['branches']={w:{layer:collect([],r['times'],events,r['dataset'])[0] for layer,events in layers.items()} for w in ['0.2','0.4']}
            for width,layers in d['branches'].items():
                for layer,stats in layers.items():
                    key=r['dataset']+'_'+layer+'_'+width
                    g=groups.setdefault(key,dict(files=0,failed_files=0,duration_s=0.,B_analyze_wall_s=0.,B_backend_and_result_write_s=0.,A_native_raw_postprocess_both_widths_s=0.,separation_status=Counter(),views={v:Counter() for v in ['A','B','U_context','B_frame']},per_quality={v:defaultdict(Counter) for v in ['A','B','U_context','B_frame']},confusion={v:Counter() for v in ['A','B','U_context','B_frame']},excluded=Counter(),temporal={v:Counter() for v in ['A','B','U_context','B_frame']},transitions=Counter()))
                    g['files']+=1;g['failed_files']+=int(d['status']!='complete');g['duration_s']+=d.get('duration_s',0)
                    g['separation_status'][d.get('separation_status',d.get('job',{}).get('separation_status','failed'))]+=1
                    for name in ['B_analyze_wall_s','B_backend_and_result_write_s','A_native_raw_postprocess_both_widths_s']:g[name]+=d.get('timing',{}).get(name,0.)
                    for view in g['views']:
                        g['views'][view].update(stats['counts'][view]);g['confusion'][view].update(stats['confusion'][view])
                        for q,c in stats['per_quality'][view].items():g['per_quality'][view][q].update(c)
                    g['excluded'].update(stats['excluded'])
                    temporal=d.get('temporal',{}).get(width,{}).get(layer,{})
                    for view,c in temporal.get('runs',{}).items():g['temporal'][view].update(c)
                    for t in temporal.get('transitions',[]):
                        g['transitions']['all_labelled']+=1
                        for view,detected in t['detected'].items():g['transitions']['detected_'+view]+=int(detected)
                        for reason in ['B_lost_A','lookahead_loss','grid_loss']:g['transitions'][reason]+=int(t[reason])
                        if t['stable_intervals']:
                            g['transitions']['stable_labelled']+=1
                            for view,detected in t['detected'].items():g['transitions']['stable_detected_'+view]+=int(detected)
                            for reason in ['B_lost_A','lookahead_loss','grid_loss']:g['transitions']['stable_'+reason]+=int(t[reason])
                        if width=='0.2':transition_rows.append(dict(mode=mode,id=r['id'],dataset=r['dataset'],layer=layer,**t))
            detail=RUN/mode/'details'/(r['id']+'.csv')
            if detail.exists():
                by_point=defaultdict(dict)
                with detail.open(encoding='utf-8-sig',newline='') as f:
                    for row in csv.DictReader(f):
                        if row['width']=='0.2':by_point[(row['layer'],row['time_s'])][row['view']]=int(row['exact'])
                for (layer,t),values in by_point.items():
                    c=paired[mode+'_'+r['dataset']+'_'+layer];a=values.get('A',0);b=values.get('B',0);c['both_correct' if a and b else 'A_only_correct' if a else 'B_only_correct' if b else 'both_wrong']+=1
        for key,g in groups.items():
            g['views']={v:rates(c) for v,c in g['views'].items()}
            g['per_quality']={v:{q:rates(c) for q,c in qs.items()} for v,qs in g['per_quality'].items()}
            for v,qs in g['per_quality'].items():
                for q,c in qs.items():quality_rows.append(dict(mode=mode,group=key,view=v,reference_quality=q,**c))
            for v,c in g['confusion'].items():
                for name,n in c.most_common():confusions.append(dict(mode=mode,group=key,view=v,confusion=name,n=n))
            g['confusion']={v:c.most_common(30) for v,c in g['confusion'].items()}
            g['real_time_factor_B']=g['B_analyze_wall_s']/g['duration_s'] if g['duration_s'] else None
        summary['groups'][mode]=groups
    summary['paired_A_B']={k:dict(v) for k,v in paired.items()}
    summary['complete']=not summary['pending']
    (RUN/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (RUN/'transitions.json').write_text(json.dumps(transition_rows,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,rows in [('per_quality',quality_rows),('confusions',confusions),('per_file',file_rows)]:
        if not rows:continue
        with (RUN/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
            for row in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    print('Completed files:',len(file_rows),'pending:',len(summary['pending']),'failures:',len(summary['errors']))
    for mode,groups in summary['groups'].items():
        for key,g in groups.items():
            if key.endswith('0.2'):print(mode,key,'files',g['files'],'n',g['views']['A'].get('n'), 'A',g['views']['A']['exact_accuracy'],'B',g['views']['B']['exact_accuracy'])


if __name__=='__main__':main()
