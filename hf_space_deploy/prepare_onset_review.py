"""Add optional onset A/B records to existing web jobs without new inference."""
import argparse
import copy
import json
import shutil
from pathlib import Path
import numpy as np
from chord_web_analysis import ROOT
from onset_transition import add_layer

OUT=ROOT/'dataset/integration_review/runs/onset_transition_20261105_v1'


def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True);summary={}
    for directory in sorted((ROOT/'webapp/runs').iterdir()):
        if not (directory/'job.json').exists():continue
        job=json.loads((directory/'job.json').read_text(encoding='utf-8'))
        if job['status']!='complete':continue
        old=json.loads((directory/'result.json').read_text(encoding='utf-8'))
        if not all(rows and 'presentation' in rows[0] for rows in old['branches'].values()):continue
        result=copy.deepcopy(old)
        with np.load(directory/'prediction/upload_raw.npz') as data:
            add_layer(result,data['times'],data['note'],data['onset'] if 'onset' in data else None)
        for width,rows in result['branches'].items():
            for before,after in zip(old['branches'][width],rows):
                for key in ['time_s','top3','display','context','presentation']:assert before[key]==after[key]
                assert 'onset_context' in after and 'onset_presentation' in after
        dest=OUT/(directory.name+'_result.json');dest.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        if args.apply:
            backup=directory/'result_before_onset_v4.json'
            if not backup.exists():shutil.copyfile(directory/'result.json',backup)
            temp=directory/'onset_result.tmp';shutil.copyfile(dest,temp);temp.replace(directory/'result.json')
        summary[directory.name]=dict(name=job['name'],rows={w:len(rows) for w,rows in result['branches'].items()},baseline_records_unchanged=True,manual_accuracy_review=False)
        print('Prepared',directory.name,flush=True)
    (OUT/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
