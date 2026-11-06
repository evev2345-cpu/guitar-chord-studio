"""Before/after boundary review; no API requests."""
import json
from pathlib import Path
import cv2
import numpy as np
from fret_geometry import resolve_frets

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/gpt_boundary_retest'


def main():
    pairs=[];tiles=[]
    for path in sorted(OUT.glob('*/evaluation.json')):
        new=json.loads(path.read_text(encoding='utf-8'))
        old=json.loads((ROOT/'dataset/gpt_full_evaluation'/path.parent.name/'evaluation.json').read_text(encoding='utf-8'))
        replay=resolve_frets(old['calls'][-1]['response'],board_boundaries=True)
        pairs.append(dict(image=new['image'],old_unresolved=old['unresolved'],old_outside=old['out_of_bounds'],
            new_unresolved=new.get('unresolved'),new_outside=new.get('out_of_bounds'),
            estimated=new.get('estimated'),adjusted=new.get('adjusted'),interpolated=new.get('interpolated'),
            old_last=max(f['fret_num'] for f in old['frets']),new_last=max(f['fret_num'] for f in new['frets']),
            old_corner_metrics=old['corner_metrics'],new_corner_metrics=new['corner_metrics'],
            cached_response_replay_unresolved=[f['fret_num'] for f in replay if 'xt' not in f]))
        tile=np.full((375,820,3),25,np.uint8)
        cv2.putText(tile,new['image']+' BEFORE / AFTER',(10,23),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
        tile[40:190,10:810]=cv2.imread(str(ROOT/'dataset/gpt_full_evaluation'/path.parent.name/'result_flat_boxes.png'))
        tile[210:360,10:810]=cv2.imread(str(path.parent/'result_flat_boxes.png'))
        tiles.append(tile)
    summary=dict(images=len(pairs),old_unresolved=sum(len(p['old_unresolved']) for p in pairs),
        new_unresolved=sum(len(p['new_unresolved']) for p in pairs),
        old_outside=sum(len(p['old_outside']) for p in pairs),new_outside=sum(len(p['new_outside']) for p in pairs),
        boundary_estimated=sum(len(p['estimated']) for p in pairs),
        adjusted=sum(len(p['adjusted']) for p in pairs),
        old_mean_iou=float(np.mean([p['old_corner_metrics']['polygon_iou'] for p in pairs])),
        new_mean_iou=float(np.mean([p['new_corner_metrics']['polygon_iou'] for p in pairs])),
        old_corner_error_px=float(np.mean([p['old_corner_metrics']['mean_error_px'] for p in pairs])),
        new_corner_error_px=float(np.mean([p['new_corner_metrics']['mean_error_px'] for p in pairs])))
    usage=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))['summary']
    (OUT/'boundary_comparison.json').write_text(json.dumps(dict(summary=summary,usage=usage,images=pairs),indent=2),encoding='utf-8')
    lines=['# Boundary handling: same five images retest','','## Results','','```json',json.dumps(dict(summary=summary,usage=usage),indent=2),'```','',
        '| Image | Previous unresolved | Previous outside | Boundary estimates | Small clips | New unresolved/outside | Old last / new last |','|---|---|---|---|---|---|---|']
    for p in pairs:
        lines.append(f"| {p['image']} | {p['old_unresolved']} | {p['old_outside']} | {p['estimated']} | {p['adjusted']} | {p['new_unresolved']} / {p['new_outside']} | {p['old_last']} / {p['new_last']} |")
    lines+=['','## Interpretation','',
        'Magenta lines are boundary estimates, cyan lines are internal interpolation, green lines are observed wires. Small clipped observations retain original_endpoints and geometry_adjustment metadata.',
        'Nut recovery uses the semantic stage-1 nut corners. Terminal-number recovery requires at least six observed wires, a projective fit of 12-TET positions, low residual, monotonic positions, agreement at both edges and agreement with last_fret_num when supplied. Inconclusive cases remain unresolved.',
        'Small out-of-board extrapolations <=0.5% of board width are clipped with original endpoints retained. Larger excursions are rejected from geometry and may only be filled with explicit estimates between valid anchors.',
        'Old cached responses also resolve all old unresolved records after the geometry change; these were replayed without API charges.',
        'Fresh endpoint counts changed in some images. No fret-wire ground truth exists, so these are model/geometry estimates, not certified physical numbering. Endpoint crop quality affects every boundary estimate.',
        'Fresh corner IoU slightly declined compared with the same five old runs; the corner detector itself was not improved by this boundary change. This is not a claim of improved corner accuracy.',
        '15 fresh requests, no automatic retries. Original results retained under dataset/gpt_full_evaluation.']
    (OUT/'boundary_report.md').write_text('\n'.join(lines),encoding='utf-8')
    for page,start in enumerate(range(0,len(tiles),3),1):
        cv2.imwrite(str(OUT/f'before_after_{page}.jpg'),np.vstack(tiles[start:start+3]))
    print(json.dumps(dict(summary=summary,usage=usage,images=[{k:v for k,v in p.items() if 'metrics' not in k} for p in pairs]),indent=2))


if __name__=='__main__':main()
