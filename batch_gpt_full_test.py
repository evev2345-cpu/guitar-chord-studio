"""Run the remaining 11 labeled images end-to-end; preserve usage on failures."""
import concurrent.futures
import csv
import json
import time
from pathlib import Path
import cv2
import numpy as np
from baze_client import call_baze_json,request_json
from compare_baze_models import metrics
from two_stage_fret_pipeline import TwoStageFretPipeline,CORNER_NAMES

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/gpt_full_evaluation'
MODEL='gpt-6.1-sol'


def run_one(label_path):
    label=json.loads(label_path.read_text(encoding='utf-8'))
    folder=OUT/label_path.stem
    folder.mkdir(parents=True,exist_ok=True)
    checkpoint=folder/'evaluation.json'
    if checkpoint.exists():
        return json.loads(checkpoint.read_text(encoding='utf-8'))
    record=dict(image=label['image'],model=MODEL,status='running',calls=[])
    def save():
        temporary=checkpoint.with_suffix('.tmp')
        temporary.write_text(json.dumps(record,indent=2),encoding='utf-8')
        temporary.replace(checkpoint)
    save()
    def invoke(contents,timeout,model):
        start=time.monotonic()
        call=dict(stage=len(record['calls'])+1)
        record['calls'].append(call)
        save()
        try:
            response,usage=call_baze_json(contents,timeout=timeout,model=model)
            call.update(response=response,usage=usage)
            return response,usage
        except Exception as error:
            call.update(error=str(error),usage=getattr(error,'usage',{}))
            raise
        finally:
            call['seconds']=time.monotonic()-start
            save()
    pipeline=TwoStageFretPipeline(str(ROOT/'sample_images'/label['image']),model=MODEL,api_call=invoke)
    try:
        pipeline.stage1_detect_corners()
        by={v['name']:[v['x'],v['y']] for v in label['corners']}
        record.update(corners=pipeline.corners,corner_metrics=metrics(pipeline.corners,[by[n] for n in CORNER_NAMES]))
        pipeline.stage2_unwarp_and_enhance()
        cv2.imwrite(str(folder/'flat_input.png'),pipeline.flat)
        pipeline.stage3_detect_frets_two_points()
        pipeline.render_and_save(str(folder/'result'))
        frets=pipeline.fret_records
        record.update(status='ok',frets=frets,
            wire_count=len(frets),estimated=[f['fret_num'] for f in frets if f.get('estimated')],
            adjusted=[f['fret_num'] for f in frets if f.get('geometry_adjustment')],observed=[f['fret_num'] for f in frets if f['source']=='observed'],
            interpolated=[f['fret_num'] for f in frets if f.get('interpolated')],
            unresolved=[f['fret_num'] for f in frets if 'xt' not in f],
            out_of_bounds=[f['fret_num'] for f in frets if 'xt' in f and not (0<=f['xt']<=800 and 0<=f['xb']<=800)])
    except Exception as error:
        record.update(status='failed',error=str(error))
    save()
    print(label['image'],record['status'],sum(c.get('usage',{}).get('totalTokenCount') or 0 for c in record['calls']),flush=True)
    return record


def summarize():
    records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(OUT.glob('*/evaluation.json'))]
    completed=[r for r in records if r['status']!='running']
    ok=[r for r in completed if r['status']=='ok']
    calls=[c for r in completed for c in r['calls']]
    summary=dict(images=len(completed),successful=len(ok),failed=len(completed)-len(ok),
        mean_corner_error_px=float(np.mean([r['corner_metrics']['mean_error_px'] for r in completed if 'corner_metrics' in r])) if completed else None,
        mean_iou_including_failures=float(np.mean([r.get('corner_metrics',{}).get('polygon_iou',0) for r in completed])) if completed else None,
        calls=len(calls),input_tokens=sum(c.get('usage',{}).get('promptTokenCount') or 0 for c in calls),
        output_tokens=sum(c.get('usage',{}).get('candidatesTokenCount') or 0 for c in calls),
        total_tokens=sum(c.get('usage',{}).get('totalTokenCount') or 0 for c in calls),
        calls_without_usage=sum(c.get('usage',{}).get('totalTokenCount') is None for c in calls))
    (OUT/'summary.json').write_text(json.dumps(dict(summary=summary,images=records),indent=2),encoding='utf-8')
    rows=[]
    for r in completed:
        rows.append(dict(image=r['image'],status=r['status'],
            corner_error_px=r.get('corner_metrics',{}).get('mean_error_px'),iou=r.get('corner_metrics',{}).get('polygon_iou'),
            wire_count=r.get('wire_count'),interpolated=','.join(map(str,r.get('interpolated',[]))),
            unresolved=','.join(map(str,r.get('unresolved',[]))),
            tokens=sum(c.get('usage',{}).get('totalTokenCount') or 0 for c in r['calls']),error=r.get('error','')))
    if rows:
        with (OUT/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    tiles=[]
    for r in completed:
        folder=OUT/Path(r['image']).stem
        path=folder/'result_flat_boxes.png'
        tile=np.full((210,820,3),25,np.uint8)
        cv2.putText(tile,r['image']+' '+r['status'],(10,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1)
        if path.exists():tile[45:195,10:810]=cv2.imread(str(path))
        else:cv2.putText(tile,r.get('error','')[:90],(10,75),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,150,255),1)
        tiles.append(tile)
    for page,start in enumerate(range(0,len(tiles),4),1):
        cv2.imwrite(str(OUT/f'flat_comparison_{page}.jpg'),np.vstack(tiles[start:start+4]))
    lines=['# GPT-6.1 Sol: remaining 11 images end-to-end','','All calls explicitly approved. Same live candidate/corner/fret pipeline; no manual target coordinates supplied to the model.','',json.dumps(summary,indent=2),'',
           '| Image | Status | Corner px | IoU | Wires | Interpolated | Tokens |','|---|---|---:|---:|---:|---|---:|']
    for row in rows:
        error='-' if row['corner_error_px'] is None else f"{row['corner_error_px']:.2f}"
        iou='-' if row['iou'] is None else f"{row['iou']:.3f}"
        lines.append(f"| {row['image']} | {row['status']} | {error} | {iou} | {row['wire_count']} | {row['interpolated'] or '-'} | {row['tokens']:,} |")
    lines+=['','Corner accuracy is measured against the 4-point labels. No per-image fret-wire ground truth exists; wire counts and source classifications are model outputs, not certified fret accuracy.','Out-of-bounds wire endpoints and unresolved wires are retained in each evaluation JSON for review. No automatic paid retries.','The previously tested images (1).jpg is excluded; its earlier usage was 6,019 tokens.']
    (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)
    return summary


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--summarize-only',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True,parents=True)
    if args.summarize_only:return summarize()
    ids={m['id'] for m in request_json('GET','/models/?type=llm').get('data',[])}
    if MODEL not in ids:raise SystemExit('GPT model unavailable')
    labels=[p for p in sorted((ROOT/'dataset/labels').glob('*.json')) if p.stem!='images (1)']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run_one,p) for p in labels]):
            future.result()
            summarize()


if __name__=='__main__':main()
