"""Compare display v2/v3 on identical saved model/context observations."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
from chord_web_analysis import ROOT
from chord_presentation import prepare, CONFIG

OUT=ROOT/'dataset/integration_review/runs/chord_presentation_20261105_v1'


def candidates(row,after):
    return row['presentation']['display_candidates'] if after else row['context']['display_candidates']


def metrics(rows,after):
    labels=[];bases=[];slash=0;durations=[];start=0
    for row in rows:
        cs=candidates(row,after);labels.append(tuple(sorted((c['root_pc'],c['quality'],c.get('bass_pc') if c.get('bass_pc') is not None else c['root_pc']) for c in cs)))
        bases.append(tuple(sorted((c['root_pc'],c['quality']) for c in cs)));slash+=any('/' in c['symbol'] for c in cs)
    for i in range(1,len(labels)+1):
        if i==len(labels) or labels[i]!=labels[start]:durations.append((i-start)/24);start=i
    return dict(frames=len(rows),display_changes=sum(a!=b for a,b in zip(labels,labels[1:])),base_changes=sum(a!=b for a,b in zip(bases,bases[1:])),
                slash_frames=slash,short_display_runs_under_0_2s=sum(t<.2 for t in durations))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True);summary={}
    for directory in sorted((ROOT/'webapp/runs').iterdir()):
        if not (directory/'job.json').exists():continue
        job=json.loads((directory/'job.json').read_text(encoding='utf-8'))
        if job['status']!='complete':continue
        old=json.loads((directory/'result.json').read_text(encoding='utf-8'))
        if not all('context' in rows[0] for rows in old['branches'].values()):continue
        result=copy.deepcopy(old);result['schema_version']='chord_web.v3';result['presentation_config']=CONFIG;branches={}
        for width,rows in result['branches'].items():
            fresh=prepare([r['time_s'] for r in rows],rows)
            for row,presentation in zip(rows,fresh):row['presentation']=presentation
            for before,after in zip(old['branches'][width],rows):
                for key in ['top3','status','display','context']:assert before[key]==after[key]
            branches[width]=dict(before=metrics(rows,False),after=metrics(rows,True),display_statuses=dict(Counter(r['presentation']['status'] for r in rows)))
        dest=OUT/(directory.name+'_result.json');dest.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        summary[directory.name]=dict(name=job['name'],branches=branches,result=str(dest),underlying_observations_unchanged=True)
        if args.apply:
            backup=directory/'result_before_presentation_v3.json'
            if not backup.exists():shutil.copyfile(directory/'result.json',backup)
            temp=directory/'presentation_result.tmp';shutil.copyfile(dest,temp);temp.replace(directory/'result.json')
        print(directory.name,branches['0.2'],flush=True)
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
