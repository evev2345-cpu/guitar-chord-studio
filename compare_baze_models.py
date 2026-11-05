"""Compare three BAZE providers on labeled images. Default is an offline estimate."""
import argparse
import csv
import hashlib
import json
import time
from pathlib import Path
import cv2
import numpy as np
from baze_client import call_baze_json, request_json
from fretboard_prompts import CANDIDATE_PROMPT, CORNER_PROMPT
from two_stage_fret_pipeline import TwoStageFretPipeline, CORNER_NAMES

ROOT = Path(__file__).resolve().parent
MODELS = ['gemini-3.5-flash','gpt-6.1-sol','claude-sonnet-5-5']


def metrics(pred, gt):
    pred,gt = np.asarray(pred,np.float32),np.asarray(gt,np.float32)
    error=np.linalg.norm(pred-gt,axis=1)
    intersection,_=cv2.intersectConvexConvex(pred,gt)
    union=abs(cv2.contourArea(pred))+abs(cv2.contourArea(gt))-intersection
    width=(np.linalg.norm(gt[0]-gt[3])+np.linalg.norm(gt[1]-gt[2]))/2
    return dict(mean_error_px=float(error.mean()),max_error_px=float(error.max()),
                mean_error_width_pct=float(error.mean()/width*100),
                polygon_iou=float(intersection/union) if union else 0,
                corner_errors_px=error.tolist())


def summarize(records, models):
    summary={}
    for model in models:
        group=[r for r in records if r['model']==model]
        ok=[r for r in group if r['status']=='ok']
        attempts=[a for r in group for a in r.get('previous_attempts',[])+[r]]
        usages=[c.get('usage',{}) for r in attempts for c in r['calls']]
        summary[model]=dict(images=len(group),successful=len(ok),failed=len(group)-len(ok),
            mean_iou_including_failures=float(np.mean([r.get('metrics',{}).get('polygon_iou',0) for r in group])) if group else None,
            mean_corner_error_px_successes=float(np.mean([r['metrics']['mean_error_px'] for r in ok])) if ok else None,
            mean_error_width_pct_successes=float(np.mean([r['metrics']['mean_error_width_pct'] for r in ok])) if ok else None,
            attempts=len(attempts),calls=len(usages),
            reported_input_tokens=sum(u.get('promptTokenCount') or 0 for u in usages),
            reported_output_tokens=sum(u.get('candidatesTokenCount') or 0 for u in usages),
            reported_total_tokens=sum(u.get('totalTokenCount') or 0 for u in usages),
            calls_without_token_counts=sum(u.get('totalTokenCount') is None for u in usages))
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--retry-failed',action='store_true',help='Explicitly retry failed records, preserving prior attempts and usage')
    parser.add_argument('--run',action='store_true',help='Send images to BAZE and incur API usage')
    parser.add_argument('--models',nargs='+',default=MODELS)
    parser.add_argument('--output',default='dataset/baze_comparison')
    parser.add_argument('--only-model', choices=MODELS, help='Process only one model within the same experiment manifest')
    args=parser.parse_args()
    labels=sorted((ROOT/'dataset/labels').glob('*.json'))
    count=len(labels)*len(args.models)*2
    estimate=dict(images=len(labels),models=args.models,calls=count,
        scope='Two-stage fretboard extraction only; no fret-wire detection',
        input_tokens_rough_range=[count*1000,count*4000],
        output_including_reasoning_rough_range=[count*200,count*2000],
        combined_rough_range=[count*1200,count*6000],
        configured_output_ceiling=count*16000,
        caveat='Planning estimate, not provider tokenization or a price quote. Reasoning can exceed the rough range; failed calls can still be billed.')
    print(json.dumps(estimate,indent=2),flush=True)
    if not args.run:
        return
    available={m['id'] for m in request_json('GET','/models/?type=llm').get('data',[])}
    missing=set(args.models)-available
    if missing: raise SystemExit('Models not available: '+', '.join(sorted(missing)))
    out=ROOT/args.output
    out.mkdir(parents=True,exist_ok=True)
    manifest=dict(models=args.models,images=[p.name for p in labels],
                  prompts=dict(candidate=CANDIDATE_PROMPT,corners=CORNER_PROMPT),
                  preprocessing=dict(max_full_side=1400,crop_margin=0.15,crop_long_side=1400,jpeg_quality=90),
                  max_tokens=16000,automatic_retries=0)
    fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode())
    for p in labels:
        fingerprint.update(p.read_bytes())
        label=json.loads(p.read_text(encoding='utf-8'))
        fingerprint.update((ROOT/'sample_images'/label['image']).read_bytes())
    manifest['fingerprint']=fingerprint.hexdigest()
    manifest_path=out/'manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding='utf-8'))!=manifest:
        raise SystemExit('Existing output uses different settings/data. Choose another --output directory.')
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    records=[]
    for model in args.models:
        if args.only_model and model != args.only_model:
            continue
        folder=out/model
        folder.mkdir(exist_ok=True)
        for label_path in labels:
            label=json.loads(label_path.read_text(encoding='utf-8'))
            path=folder/(label_path.stem+'.json')
            # Completed failures are also retained; reruns never silently rebill them.
            history=[]
            if path.exists():
                previous=json.loads(path.read_text(encoding='utf-8'))
                if not args.retry_failed or previous['status'] != 'failed':
                    records.append(previous)
                    continue
                history=previous.get('previous_attempts',[])+[
                    {k:v for k,v in previous.items() if k != 'previous_attempts'}]
            record=dict(model=model,image=label['image'],status='running',calls=[],previous_attempts=history)
            def save():
                path.write_text(json.dumps(record,indent=2),encoding='utf-8')
            def invoke(contents,timeout,model):
                start=time.monotonic()
                entry=dict(stage=len(record['calls'])+1)
                record['calls'].append(entry)
                save()
                try:
                    result,usage=call_baze_json(contents,timeout=timeout,model=model)
                    entry.update(usage=usage,response=result)
                    return result,usage
                except Exception as e:
                    entry.update(error=str(e),usage=getattr(e,'usage',{}))
                    raise
                finally:
                    entry['elapsed_seconds']=time.monotonic()-start
                    save()
            pipeline=TwoStageFretPipeline(str(ROOT/'sample_images'/label['image']),model=model,api_call=invoke)
            try:
                pipeline.stage1_detect_corners()
                by_name={v['name']:[v['x'],v['y']] for v in label['corners']}
                gt=[by_name[n] for n in CORNER_NAMES]
                record.update(status='ok',corners=pipeline.corners,
                              metrics=metrics(pipeline.corners,gt),detection=pipeline.corner_detection)
                vis=pipeline.raw.copy()
                cv2.polylines(vis,[np.asarray(gt,np.int32)],True,(0,255,0),2)
                cv2.polylines(vis,[np.asarray(pipeline.corners,np.int32)],True,(255,0,255),2)
                cv2.imwrite(str(folder/(label_path.stem+'_overlay.jpg')),vis)
            except Exception as e:
                record.update(status='failed',error=str(e))
            save()
            records.append(record)
            print(model,label['image'],record['status'],flush=True)
            report=dict(summary=summarize(records,args.models),images=records)
            (out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    records=[json.loads(p.read_text(encoding='utf-8')) for model in args.models for p in sorted((out/model).glob('*.json'))]
    report=dict(summary=summarize(records,args.models),images=records)
    (out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    rows=[dict(model=r['model'],image=r['image'],status=r['status'],
               mean_error_px=r.get('metrics',{}).get('mean_error_px'),
               polygon_iou=r.get('metrics',{}).get('polygon_iou',0)) for r in records]
    with (out/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(report['summary'],indent=2))


if __name__=='__main__':main()
