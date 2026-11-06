"""Offline evaluation of existing YOLO pose weights against all manual labels."""
import csv
import json
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
NAMES = ['nut_top','body_top','body_bottom','nut_bottom']


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', default='runs/pose/fretboard_model/pose_exp/weights/best.pt')
    parser.add_argument('--output', default='dataset/yolo_evaluation')
    args = parser.parse_args()
    out = ROOT/args.output
    out.mkdir(parents=True,exist_ok=True)
    model = YOLO(str(ROOT/args.weights))
    rows, detail, tiles = [], [], []
    for path in sorted((ROOT/'dataset/labels').glob('*.json')):
        label = json.loads(path.read_text(encoding='utf-8'))
        img = cv2.imread(str(ROOT/'sample_images'/label['image']))
        h,w = img.shape[:2]
        by_name = {p['name']:[p['x'],p['y']] for p in label['corners']}
        gt = np.array([by_name[n] for n in NAMES],np.float32)
        normalized = gt / [w,h]
        splits = []
        for split in ['train','val']:
            for txt in (ROOT/'dataset/yolo_fretboard/labels'/split).glob('*.txt'):
                values = np.array([float(x) for x in txt.read_text().split()])
                if len(values)==17 and np.allclose(values[5:].reshape(4,3)[:,:2],normalized,atol=1e-6):
                    splits.append(split)
                    break
        split = '+'.join(splits) or 'unknown'
        result = model.predict(img,conf=0.25,imgsz=640,device='cpu',verbose=False)[0]
        vis=img.copy()
        cv2.polylines(vis,[gt.astype(np.int32)],True,(0,255,0),2)
        row=dict(image=label['image'],split=split,detected=False,confidence=None,
                 mean_error_px=None,max_error_px=None,mean_error_width_pct=None,
                 polygon_iou=0,pck_20pct_width=0)
        record=dict(image=label['image'],ground_truth=gt.tolist())
        if result.boxes is not None and len(result.boxes) and result.keypoints is not None:
            best=int(result.boxes.conf.argmax())
            pred=result.keypoints.xy[best].cpu().numpy().astype(np.float32)
            if pred.shape==(4,2):
                error=np.linalg.norm(pred-gt,axis=1)
                width=(np.linalg.norm(gt[0]-gt[3])+np.linalg.norm(gt[1]-gt[2]))/2
                valid=cv2.isContourConvex(pred.astype(np.float32))
                intersection=0
                if valid: intersection,_=cv2.intersectConvexConvex(pred.astype(np.float32),gt)
                union=abs(cv2.contourArea(pred))+abs(cv2.contourArea(gt))-intersection
                row.update(detected=True,confidence=float(result.boxes.conf[best]),
                           mean_error_px=float(error.mean()),max_error_px=float(error.max()),
                           mean_error_width_pct=float(error.mean()/width*100),
                           polygon_iou=float(intersection/union) if union>0 else 0,
                           pck_20pct_width=float(np.mean(error<=width*0.2)))
                record.update(prediction=pred.tolist(),corner_errors_px=dict(zip(NAMES,error.tolist())),
                              keypoint_confidence=result.keypoints.conf[best].cpu().tolist() if result.keypoints.conf is not None else None)
                cv2.polylines(vis,[pred.astype(np.int32)],True,(255,0,255),2)
                for a,b in zip(gt,pred): cv2.line(vis,tuple(a.astype(int)),tuple(b.astype(int)),(0,200,255),1)
        record.update(row)
        rows.append(row); detail.append(record)
        cv2.imwrite(str(out/(path.stem+'_overlay.jpg')),vis)
        x0,y0=np.maximum(np.floor(gt.min(axis=0)-45),0).astype(int)
        x1,y1=np.minimum(np.ceil(gt.max(axis=0)+45),[w,h]).astype(int)
        crop=vis[y0:y1,x0:x1]
        scale=min(440/crop.shape[1],245/crop.shape[0])
        crop=cv2.resize(crop,None,fx=scale,fy=scale)
        tile=np.full((300,460,3),25,np.uint8)
        tile[48:48+crop.shape[0],10:10+crop.shape[1]]=crop
        cv2.putText(tile,label['image'],(10,18),cv2.FONT_HERSHEY_SIMPLEX,.43,(255,255,255),1)
        text=f"{split} IoU={row['polygon_iou']:.3f}"
        if row['detected']: text+=f" err={row['mean_error_px']:.1f}px"
        else: text+=' NO DETECTION'
        cv2.putText(tile,text,(10,39),cv2.FONT_HERSHEY_SIMPLEX,.43,(255,255,255),1)
        tiles.append(tile)
        print(json.dumps(row),flush=True)
    summary={}
    for split in ['all','train','val']:
        subset=[r for r in rows if split=='all' or r['split']==split]
        detected=[r for r in subset if r['detected']]
        summary[split]=dict(images=len(subset),detected=len(detected),
            mean_iou=float(np.mean([r['polygon_iou'] for r in subset])) if subset else None,
            mean_corner_error_px=float(np.mean([r['mean_error_px'] for r in detected])) if detected else None,
            mean_error_width_pct=float(np.mean([r['mean_error_width_pct'] for r in detected])) if detected else None,
            pck_20pct_width=float(np.mean([r['pck_20pct_width'] for r in subset])) if subset else None)
    (out/'results.json').write_text(json.dumps(dict(settings=dict(conf=0.25,imgsz=640,device='cpu',selection='highest box confidence'),summary=summary,images=detail),indent=2),encoding='utf-8')
    with (out/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
    sheet=np.vstack([np.hstack(tiles[i:i+3]) for i in range(0,len(tiles),3)])
    cv2.imwrite(str(out/'comparison_montage.jpg'),sheet)
    print('SUMMARY',json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
