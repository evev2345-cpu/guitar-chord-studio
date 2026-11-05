"""Render and account for the completed comparison; no API calls."""
import csv
import json
from pathlib import Path
import cv2
import numpy as np
from compare_baze_models import MODELS, summarize, ROOT
from two_stage_fret_pipeline import CORNER_NAMES


def main():
    out=ROOT/'dataset/baze_comparison'
    records=[json.loads(p.read_text(encoding='utf-8')) for model in MODELS for p in sorted((out/model).glob('*.json'))]
    if len(records)!=36 or any(r['status']=='running' for r in records):
        raise SystemExit('Comparison is still incomplete')
    summary=summarize(records,MODELS)
    diagnostic_path=out/'claude_response_diagnostic.json'
    diagnostic=json.loads(diagnostic_path.read_text(encoding='utf-8')) if diagnostic_path.exists() else {}
    du=diagnostic.get('usage',{})
    accounting=dict(comparison_calls=sum(s['calls'] for s in summary.values()),
                    diagnostic_calls=1 if diagnostic else 0,
                    diagnostic_usage=du,
                    reported_input_tokens=sum(s['reported_input_tokens'] for s in summary.values())+du.get('prompt_tokens',0),
                    reported_output_tokens=sum(s['reported_output_tokens'] for s in summary.values())+du.get('completion_tokens',0),
                    reported_total_tokens=sum(s['reported_total_tokens'] for s in summary.values())+du.get('total_tokens',0),
                    calls_without_token_counts=sum(s['calls_without_token_counts'] for s in summary.values()))
    accounting['unattributed_total_token_difference'] = accounting['reported_total_tokens'] - accounting['reported_input_tokens'] - accounting['reported_output_tokens']
    report=dict(summary=summary,accounting=accounting,images=records,
                caveats=['Single trial per image, except Claude format-failure retries; this is not a controlled repeated-trial benchmark.',
                         'Claude retry history and diagnostic usage are retained and included in accounting.',
                         'Manual labels score outputs only; they are not sent as prompts.',
                         'Token figures are reported by BAZE; provider image/reasoning accounting differs. No monetary cost inferred.',
                         'Gemini total_tokens exceeds prompt_tokens + completion_tokens by 35,737 tokens. The gateway did not provide a detailed breakdown; these tokens are retained in total usage, not assigned definitively to reasoning.',
                         'Convex valid output does not imply perfect accuracy. Failed geometry receives zero IoU.'])
    (out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    rows=[]
    lookup={(r['model'],r['image']):r for r in records}
    for r in records:
        rows.append(dict(model=r['model'],image=r['image'],status=r['status'],
                         mean_error_px=r.get('metrics',{}).get('mean_error_px'),
                         mean_error_width_pct=r.get('metrics',{}).get('mean_error_width_pct'),
                         polygon_iou=r.get('metrics',{}).get('polygon_iou',0),
                         calls=sum(len(a['calls']) for a in r.get('previous_attempts',[])+[r])))
    with (out/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# BAZE 12-image comparison','','Scope: two-stage fretboard extraction, identical prompts/preprocessing. Ground truth not supplied to models.','',
           '| Model | Valid outputs | Mean IoU (failures=0) | Corner error px (successes) | Error / board width | Calls incl. retries | Input tokens | Output tokens | Total tokens |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for model,s in summary.items():
        lines.append(f"| {model} | {s['successful']}/12 | {s['mean_iou_including_failures']:.4f} | {s['mean_corner_error_px_successes']:.3f} | {s['mean_error_width_pct_successes']:.2f}% | {s['calls']} | {s['reported_input_tokens']:,} | {s['reported_output_tokens']:,} | {s['reported_total_tokens']:,} |")
    lines+=['',f"Additional Claude diagnostic: {du.get('total_tokens',0):,} tokens ({du.get('prompt_tokens',0)} input, {du.get('completion_tokens',0)} output).",f"Grand total: {accounting['reported_total_tokens']:,} reported tokens; {accounting['comparison_calls']+accounting['diagnostic_calls']} requests.",'',*report['caveats'],'','## Per-image metrics','','| Image | Gemini IoU / px | GPT IoU / px | Claude IoU / px |','|---|---:|---:|---:|']
    tiles=[]
    for p in sorted((ROOT/'dataset/labels').glob('*.json')):
        label=json.loads(p.read_text(encoding='utf-8'))
        image=cv2.imread(str(ROOT/'sample_images'/label['image']))
        by_name={v['name']:[v['x'],v['y']] for v in label['corners']}
        gt=np.asarray([by_name[n] for n in CORNER_NAMES],np.float32)
        h,w=image.shape[:2]
        x0,y0=np.maximum(np.floor(gt.min(axis=0)-.08*max(h,w)),0).astype(int)
        x1,y1=np.minimum(np.ceil(gt.max(axis=0)+.08*max(h,w)),[w,h]).astype(int)
        row=[];scores=[]
        for model in MODELS:
            r=lookup[model,label['image']]
            vis=image.copy()
            cv2.polylines(vis,[gt.astype(np.int32)],True,(0,255,0),max(1,round(max(h,w)/700)))
            if 'corners' in r:
                cv2.polylines(vis,[np.asarray(r['corners'],np.int32)],True,(255,0,255),max(1,round(max(h,w)/700)))
            crop=vis[y0:y1,x0:x1]
            scale=min(440/crop.shape[1],240/crop.shape[0])
            crop=cv2.resize(crop,None,fx=scale,fy=scale)
            tile=np.full((300,460,3),25,np.uint8)
            tile[50:50+crop.shape[0],10:10+crop.shape[1]]=crop
            cv2.putText(tile,model+' '+label['image'],(7,17),cv2.FONT_HERSHEY_SIMPLEX,.36,(255,255,255),1)
            m=r.get('metrics',{})
            status=f"IoU {m.get('polygon_iou',0):.3f} error {m.get('mean_error_px',0):.2f}px" if m else 'FAILED: '+r.get('error','')[:48]
            cv2.putText(tile,status,(7,38),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1)
            row.append(tile)
            scores.append(f"{m['polygon_iou']:.3f} / {m['mean_error_px']:.2f}" if m else 'failed')
        tiles.append(np.hstack(row))
        lines.append('| '+label['image']+' | '+' | '.join(scores)+' |')
    (out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    # Three pages for legible visual inspection.
    for page in range(3):
        cv2.imwrite(str(out/f'comparison_{page+1}.jpg'),np.vstack(tiles[page*4:page*4+4]))
    print(json.dumps(dict(summary=summary,accounting=accounting),indent=2))


if __name__=='__main__':main()
