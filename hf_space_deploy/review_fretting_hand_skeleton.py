"""Reproduce focused skeleton candidates and raw/before/after photo comparisons."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from fretting_hand_skeleton import FrettingHandSkeletonDetector
from improve_hand_skeleton import CHAINS,COLORS
from joint_evidence_review import ROOT,BOARD,HAND,read,same_frame

FOCUSED_CROP=(850,150,1110,420)  # Explicit preset for this fixed-camera tutorial only.


def plot_compare(raw,old,new,index,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(15,6))
    panels=[('Original',None),('Before: baseline ROI',old),('After: focused whole-hand candidate',new)]
    for ax,(title,points) in zip(axes,panels):
        ax.imshow(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB));ax.set(xlim=(865,1090),ylim=(390,175));ax.axis('off');ax.set_title(title)
        if points is not None:
            points=np.asarray(points)
            for finger,ids in CHAINS.items():
                p=points[ids];ax.plot(p[:,0],p[:,1],color=COLORS[finger],lw=2)
    fig.suptitle(f'Frame {index} | middle=green, ring=orange, pinky=magenta, index=cyan, thumb=white\nWhole 21-point predictions; no relabeling or point adjustment',fontsize=12)
    fig.tight_layout(rect=[0,0,1,.93]);fig.savefig(path,dpi=130);plt.close(fig)


def run(out):
    if out.exists():raise FileExistsError('Use a new output')
    out.mkdir(parents=True)
    records={r['frame_index']:r for r in (json.loads(l) for l in HAND.read_text().splitlines())}
    indices=[120,124,190,209,210,211,212,213,214,215,216]
    results=[]
    labels=read(ROOT/'dataset/hand_analysis/human_review_20261103/validated_review.json')['reviews'][0]
    with FrettingHandSkeletonDetector(ROOT/'hand_landmarker.task') as detector:
        for index in indices:
            board=read(BOARD/'frames'/f'clip003012_f{index:06d}_board.json');same_frame(records[index],board)
            raw=cv2.imread(board['image_file'])
            if hashlib.sha256(raw.tobytes()).hexdigest()!=board['frame_pixel_sha256']:raise ValueError('Pixel mismatch')
            inference=detector.detect(raw,FOCUSED_CROP)
            selected=inference['selection']['selected']
            points=None if selected is None else selected['hands'][0]['pixel_landmarks']
            old=(records[index]['roi_observations'][0]['landmarks'] if len(records[index]['roi_observations'])==1 else None)
            old_points=None if old is None else [p['pixel'] for p in old]
            if index in [120,124,190,210,212,215]:plot_compare(raw,old_points,points,index,out/f'frame{index}_before_after.png')
            row=dict(source_id=board['source_id'],frame_index=index,frame_pts_s=board['frame_pts_s'],
                     frame_pixel_sha256=board['frame_pixel_sha256'],image_file=board['image_file'],
                     crop_preset=FOCUSED_CROP,inference=inference,
                     prior_review_scope='baseline ROI only; not evidence this new skeleton is valid',
                     confirmed_anatomical_validity=False,contact='unknown')
            if index==120 and points is not None:
                errors=[]
                for label in labels['landmarks']:
                    if label['visibility']!='visible':continue
                    i=label['index'];truth=np.array(label['pixel'])
                    errors.append(dict(index=i,new_error_px=float(np.linalg.norm(np.array(points[i])-truth)),
                        old_roi_error_px=None if old_points is None else float(np.linalg.norm(np.array(old_points[i])-truth))))
                row['development_error_evaluation']=dict(points=errors,
                    new_mean_px=float(np.mean([e['new_error_px'] for e in errors])),
                    old_roi_mean_px=float(np.mean([e['old_roi_error_px'] for e in errors])),
                    scope='single development frame; crop policy explored on these labels; not heldout accuracy')
            results.append(row);print('Focused skeleton',index,'views',inference['selection']['candidate_count'],flush=True)
    output=dict(method='focused_whole_hand_rotation_medoid_v1',frames=results,
                model_sha256=hashlib.sha256((ROOT/'hand_landmarker.task').read_bytes()).hexdigest(),
                production_default_changed=False,training=False,api_calls=0,
                crop_specific_to_this_video=True)
    (out/'result.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output)
