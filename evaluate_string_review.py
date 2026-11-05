"""Offline native-vs-common-canvas evaluation on cached tutorial frames."""
import json
import hashlib
from pathlib import Path
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from string_geometry import analyze_saved_board
from string_detector import render_strings

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/string_review'


def transform(points,matrix):
    return cv2.perspectiveTransform(np.asarray(points,np.float64)[:,None],np.asarray(matrix,np.float64))[:,0]


def compare(result,reference):
    lines=result['strings'];labels=reference['lines']
    costs=np.zeros((len(labels),len(lines)))
    point_errors={}
    for i,label in enumerate(labels):
        pts=np.asarray(label['points'],float)
        flat=transform(pts,result['M'])
        for j,line in enumerate(lines):
            predicted=flat.copy();predicted[:,1]=line['m']*flat[:,0]+line['b']
            back=transform(predicted,result['M_inv'])
            original_error=np.linalg.norm(back-pts,axis=1)
            costs[i,j]=original_error.mean()
            point_errors[i,j]=dict(original_px=original_error.tolist(),common_px=np.abs(predicted[:,1]-flat[:,1]).tolist())
    pairs=[]
    if len(lines):
        ii,jj=linear_sum_assignment(costs)
        for i,j in zip(ii,jj):
            if costs[i,j]<=3:
                pairs.append(dict(reference_id=labels[i]['reference_id'],line_id=lines[j]['line_id'],**point_errors[i,j]))
    original=[e for p in pairs for e in p['original_px']]
    common=[e for p in pairs for e in p['common_px']]
    return dict(reference_lines=len(labels),matched_lines=len(pairs),missed_reference_lines=len(labels)-len(pairs),
        unmatched_candidates=len(lines)-len(pairs),matching_threshold_original_px=3,
        mean_original_error_px=float(np.mean(original)) if original else None,
        max_original_error_px=max(original) if original else None,
        mean_common_error_px=float(np.mean(common)) if common else None,pairs=pairs,
        reference_status=reference['review_status'],reference_uncertainty_px=reference['uncertainty_px'])


def main():
    OUT.mkdir(exist_ok=True)
    refs=json.loads((OUT/'manual_string_references.json').read_text(encoding='utf-8'))
    fixtures=json.loads((ROOT/'dataset/chord_video_review/cases.json').read_text(encoding='utf-8'))
    video=next((ROOT/'sample video').glob('*.mp4'))
    video_hash=hashlib.sha256(video.read_bytes()).hexdigest()
    cases=[];tiles=[]
    for name,reference in refs.items():
        file=ROOT/'dataset/chord_video_review'/(name+'_board.json')
        board=json.loads(file.read_text(encoding='utf-8'))
        image=ROOT/board['raw_image'];raw=cv2.imread(str(image))
        fixture=next(c for c in fixtures if c['case_id']==name)
        board['source_metadata']=dict(video=str(video),video_sha256=video_hash,
            frame_index=fixture['frame_index'],timestamp_seconds=fixture['timestamp_seconds'],fps=24,
            cached_geometry_file=str(file),geometry_status='preexisting manual visual approximation')
        case=dict(source_id=name,modes={})
        panels=[]
        for high in (False,True):
            mode='high' if high else '800x150'
            result,flat,detection,M,inv=analyze_saved_board(raw,board,source_id=name,high_resolution=high)
            result['image']=str(image)
            result['manual_reference_comparison']=compare(result,reference)
            (OUT/f'{name}_{mode}.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
            flat_vis,raw_vis=render_strings(flat,raw,inv,result)
            cv2.imwrite(str(OUT/f'{name}_{mode}_flat.png'),flat_vis)
            cv2.imwrite(str(OUT/f'{name}_{mode}_raw.png'),raw_vis)
            cv2.imwrite(str(OUT/f'{name}_{mode}_input.png'),detection)
            # GT only overlay: never used as detector input.
            refvis=raw.copy()
            for label in reference['lines']:
                p1,p2=np.round(label['points']).astype(int)
                cv2.line(refvis,tuple(p1),tuple(p2),(0,255,0),1,cv2.LINE_AA)
            cv2.imwrite(str(OUT/f'{name}_manual_reference.png'),refvis)
            case['modes'][mode]=dict(candidates=len(result['strings']),numbering_status=result['numbering_status'],
                resolution=dict(native_short_edge=result['native_short_edge_px'],detection_size=result['detection_canvas_size'],
                    common_downsamples_native=result['common_canvas_downsamples_native']),**result['manual_reference_comparison'])
            panel=np.full((190,820,3),25,np.uint8)
            cv2.putText(panel,f"{name} {mode} candidates={len(result['strings'])}",(8,25),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
            panel[35:185,10:810]=flat_vis
            panels.append(panel)
        tiles.append(np.vstack(panels));cases.append(case)
    # Real low-resolution/occluded photo failure case, not a fabricated mask.
    photo=ROOT/'sample_images/gpt_sol_full_test_result.json'
    board=json.loads(photo.read_text(encoding='utf-8'));raw=cv2.imread(str(ROOT/'sample_images/images (1).jpg'))
    failure,flat,_,_,inv=analyze_saved_board(raw,board,source_id='photo_images_1_low_resolution')
    fvis,rvis=render_strings(flat,raw,inv,failure)
    cv2.imwrite(str(OUT/'failure_photo_flat.png'),fvis);cv2.imwrite(str(OUT/'failure_photo_raw.png'),rvis)
    (OUT/'failure_photo.json').write_text(json.dumps(failure,indent=2),encoding='utf-8')
    rows=[]
    for case in cases:
        for mode,data in case['modes'].items():
            rows.append(dict(source_id=case['source_id'],mode=mode,**data))
    aggregates={}
    for mode in ['800x150','high']:
        data=[r for r in rows if r['mode']==mode]
        errors=[v for r in data for p in r['pairs'] for v in p['original_px']]
        aggregates[mode]=dict(reference_lines=sum(r['reference_lines'] for r in data),
            matched_lines=sum(r['matched_lines'] for r in data),
            mean_original_error_px=float(np.mean(errors)) if errors else None,
            max_original_error_px=max(errors) if errors else None)
    report=dict(api_calls=0,reference_status='agent manual visual approximation, NOT independently verified human ground truth',
        scope='string line detection only; no chord-name classification',aggregates=aggregates,cases=cases,
        failure_cases=[dict(source_id=failure['source_id'],candidates=len(failure['strings']),unresolved=failure['unresolved'],
            reason='small source board and hand occlusion; physical string identity cannot be safely assigned')])
    (OUT/'evaluation.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    cv2.imwrite(str(OUT/'resolution_comparison.jpg'),np.vstack(tiles))
    text=['# Offline string review','','API calls: **0**. Cached board geometries reused. No chord-name module implemented.','',
      '## Manual reference limitations','','Points were manually selected by the coding agent from unoverlaid original-image inspection strips. They are provisional visual references (approximately +/-1.5 original px), not independent user-verified ground truth. Four clear lines per frame were labeled; two thin/border-adjacent lines were excluded. Metrics are for these 12 labeled lines only, not six-string accuracy.','',
      '| Frame | Mode | Candidates | Matched / labeled | Mean original px | Missed references | Unmatched candidates |','|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        error='-' if r['mean_original_error_px'] is None else f"{r['mean_original_error_px']:.3f}"
        text.append(f"| {r['source_id']} | {r['mode']} | {r['candidates']} | {r['matched_lines']}/{r['reference_lines']} | {error} | {r['missed_reference_lines']} | {r['unmatched_candidates']} |")
    text+=['','## Resolution','','The tutorial source is 1280x720. Its cached board spans roughly 684 original pixels in length and 67-82 pixels across the neck. Thus 800x150 already upsamples these dimensions; it does not discard native vertical samples in these cases. The high-resolution branch warps directly from the original image and avoids chaining through 800x150; it cannot create information missing in the video. Changes in matched counts are algorithm/resampling effects, not proof of restored physical detail.','',
      '## Failure cases','','See failure_photo_raw.png and failure_photo.json. Variable candidates and unresolved physical identities are retained. Candidates can include board edges or reflections; unmatched candidates are NOT automatically false positives because only four clear reference lines were labeled.','',
      '## Coordinates and identity','','JSON contains source/video/frame identifiers, hashes, image/canvas sizes, detection-to-common scale, M/M_inv/M_detection, preserved fret numbers/sources, per-line model and visible intervals, screen rank and separate physical string_num/number_source. A partial line set is not assigned physical numbers. Six-line numbering, when plausible, is explicitly inferred from physical corner sides and is not a direct observation of identity. No missing line is synthesized to reach six.','',
      '## Artifacts','','- resolution_comparison.jpg: actual detected lines; yellow evidence-supported intervals, dashed magenta model continuation outside support intervals; no explicit reference estimates supplied in this run.','- *_high_raw.png and *_800x150_raw.png: original-frame overlays.','- manual_string_references.json: editable original-pixel manual reference points.','- *_manual_reference.png: reference-only green segments.','- evaluation.json: detailed assignment and per-point errors.']
    (OUT/'report.md').write_text('\n'.join(text),encoding='utf-8')
    print(json.dumps(dict(aggregates=aggregates,cases=[dict(source_id=c['source_id'],modes={m:{k:v for k,v in d.items() if k not in ['pairs','resolution']} for m,d in c['modes'].items()}) for c in cases]),indent=2))


if __name__=='__main__':main()
