"""Detect strings using saved fretboard geometry. This script never calls APIs."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from string_detector import detect_strings,render_strings

ROOT=Path(__file__).resolve().parent


def process(result_path,out):
    data=json.loads(result_path.read_text(encoding='utf-8'))
    path=Path(data['raw_image'])
    if not path.is_absolute():path=ROOT/path
    raw=cv2.imread(str(path))
    if raw is None:raise FileNotFoundError(path)
    from string_geometry import analyze_saved_board
    result,flat,detector_image,matrix,inverse=analyze_saved_board(raw,data,source_id=path.name)
    result.update(image=path.name,input_geometry=str(result_path))
    out.mkdir(parents=True,exist_ok=True)
    flat_vis,raw_vis=render_strings(flat,raw,inverse,result)
    cv2.imwrite(str(out/(path.stem+'_flat.png')),flat_vis)
    cv2.imwrite(str(out/(path.stem+'_detection_input.png')),detector_image)
    cv2.imwrite(str(out/(path.stem+'_raw.png')),raw_vis)
    (out/(path.stem+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result,flat_vis


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--result',type=Path,help='One existing pipeline result JSON')
    parser.add_argument('--output',type=Path,default=ROOT/'dataset/string_detection')
    args=parser.parse_args()
    paths=[]
    if args.result:paths=[args.result]
    else:
        for label in sorted((ROOT/'dataset/labels').glob('*.json')):
            name=label.stem
            options=[ROOT/'dataset/gpt_boundary_retest'/name/'result_result.json',
                     ROOT/'dataset/gpt_full_evaluation'/name/'result_result.json']
            if name=='images (1)':options=[ROOT/'sample_images/gpt_sol_full_test_result.json']
            match=next((p for p in options if p.exists()),None)
            if match:paths.append(match)
    results=[];tiles=[]
    for path in paths:
        r,flat=process(path,args.output)
        print(r['image'],r['status'],r.get('observed_count',0),flush=True)
        results.append(r)
        tile=np.full((195,820,3),25,np.uint8)
        cv2.putText(tile,f"{r['image']} {r['status']} evidence {r.get('observed_count',0)}/6",(8,23),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),1)
        tile[35:185,10:810]=flat
        tiles.append(tile)
    if tiles:
        for page,start in enumerate(range(0,len(tiles),4),1):
            cv2.imwrite(str(args.output/f'comparison_{page}.jpg'),np.vstack(tiles[start:start+4]))
    (args.output/'summary.json').write_text(json.dumps(dict(images=len(results),api_calls=0,results=results),indent=2),encoding='utf-8')


if __name__=='__main__':main()
