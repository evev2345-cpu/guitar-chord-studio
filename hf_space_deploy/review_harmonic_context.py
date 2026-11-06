"""Evaluate fresh harmonic priors on cached predictions, without label inputs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from chord_web_analysis import ROOT, make_timeline

OUT=ROOT/'dataset/integration_review/runs/harmonic_context_20261105_v1'


def ident(candidate):
    return (candidate['root_pc'],candidate['quality']) if candidate else None


def summarize(result):
    output={}
    for width,rows in result['branches'].items():
        output[width]=dict(frames=len(rows),statuses=dict(Counter(r['context']['status'] for r in rows)),
            changed_root_quality=sum(ident(r['display']['display_candidate'])!=ident(r['context']['display_candidates'][0] if r['context']['display_candidates'] else None) for r in rows),
            slash_frames=sum(any('/' in c['symbol'] for c in r['context']['display_candidates']) for r in rows),
            sustained_bass_frames=sum(r['context']['bass']['pc'] is not None for r in rows))
    return output


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);summary={};replacements=[]
    for directory in sorted((ROOT/'webapp/runs').iterdir()):
        if not (directory/'job.json').exists():continue
        job=json.loads((directory/'job.json').read_text(encoding='utf-8'))
        if job['status']!='complete':continue
        dest=OUT/(directory.name+'_result.json')
        if dest.exists():result=json.loads(dest.read_text(encoding='utf-8'))
        else:
            result=make_timeline(directory/'prediction/upload_raw.npz',job['duration_s'])
            dest.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        old=json.loads((directory/'result.json').read_text(encoding='utf-8'))
        for width,rows in result['branches'].items():
            assert len(rows)==len(old['branches'][width])
            for new,before in zip(rows,old['branches'][width]):
                for key in ['time_s','top3','tied_top1_count','status','display']:
                    assert new[key]==before[key],(directory.name,width,key)
        metrics=summarize(result)
        if job.get('demo'):
            row=result['branches']['0.2'][20*24]
            metrics['source_214']=dict(raw=row['top3'],context=row['context'])
        summary[directory.name]=dict(name=job['name'],metrics=metrics,key=result['harmonic_context']['key'],
            prediction_sha256=hashlib.sha256((directory/'prediction/upload_raw.npz').read_bytes()).hexdigest(),
            raw_and_legacy_display_unchanged=True,result=str(dest))
        replacements.append((directory,dest))
        print('Prepared',directory.name,flush=True)
    # Reference labels only enter this post-inference evaluation.
    evaluations=[]
    for name,pred,duration,start,refs in [
        ('tutorial',ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions/tutorial_raw.npz',32,194,ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json'),
        ('new',ROOT/'dataset/integration_review/runs/change_aware_audio_20261105_v2/new_predictions/new_tutorial_raw.npz',16,250,ROOT/'dataset/integration_review/runs/change_aware_audio_20261105_v2/new_references.json')]:
        if not pred.exists():continue
        result=make_timeline(pred,duration);points=json.loads(refs.read_text())['references'];checks={}
        for width,rows in result['branches'].items():
            records=[]
            for ref in points:
                index=round((ref['pts']-start)*24)
                if not 0<=index<len(rows):continue
                row=rows[index];target=(ref['concert_root_pc'],ref['quality']);shown=row['context']['display_candidates']
                raw_tied=[c for c in row['top3'] if abs(c['score']-row['top3'][0]['score'])<=1e-10] if row['top3'] else []
                baseline_visible=raw_tied if len(raw_tied)>1 else [row['display']['display_candidate']] if row['display']['display_candidate'] else []
                records.append(dict(pts=ref['pts'],target=ref['concert_symbol'],baseline=ident(row['display']['display_candidate'])==target,
                    baseline_visible_single=len(baseline_visible)==1 and ident(baseline_visible[0])==target,
                    baseline_visible_contains=any(ident(c)==target for c in baseline_visible),
                    context_single=len(shown)==1 and ident(shown[0])==target,context_contains=any(ident(c)==target for c in shown),
                    baseline_symbol=(row['display']['display_candidate'] or {}).get('symbol'),context_symbols=[c['symbol'] for c in shown]))
            checks[width]=dict(points=len(records),baseline_correct=sum(r['baseline'] for r in records),context_single_correct=sum(r['context_single'] for r in records),context_contains=sum(r['context_contains'] for r in records),records=records,
                baseline_visible_single_correct=sum(r['baseline_visible_single'] for r in records),
                baseline_visible_contains=sum(r['baseline_visible_contains'] for r in records),
                bass_labels_available=False,independent_validation=False)
        evaluations.append(dict(case=name,checks=checks))
    (OUT/'summary.json').write_text(json.dumps(dict(jobs=summary,reference_evaluation=evaluations,ground_truth_used_in_inference=False,
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['harmonic_context.py','chord_web_analysis.py','review_harmonic_context.py']}),ensure_ascii=False,indent=2),encoding='utf-8')
    if args.apply:
        for directory,dest in replacements:
            backup=directory/'result_before_harmony_v2.json'
            if not backup.exists():shutil.copyfile(directory/'result.json',backup)
            temporary=directory/'result_context.tmp';shutil.copyfile(dest,temporary);temporary.replace(directory/'result.json')
    print('Applied' if args.apply else 'Review only',len(replacements),'jobs',flush=True)


if __name__=='__main__':main()
