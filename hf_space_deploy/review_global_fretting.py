"""Reproducible global-hand selection review using same-frame neck alignment."""
import json
import argparse
from pathlib import Path
import cv2
import numpy as np
from fretting_hand_skeleton import FrettingHandSkeletonDetector
from global_fretting_hand import detect_global_fretting,board_segment
from joint_evidence_review import ROOT,read
from review_fretboard_clip import track,project,REFERENCE_CORNERS
from improve_hand_skeleton import CHAINS,COLORS


def picture(raw,result,corners,old,pts,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(18,6))
    rgb=cv2.cvtColor(raw,cv2.COLOR_BGR2RGB)
    selected=result['selection']['selected']
    hand=None if selected is None else selected['hands'][0]
    for ax in axes:ax.imshow(rgb);ax.axis('off')
    axes[0].set_title('Original + board context (provisional)')
    if corners is not None:
        c=np.vstack([corners,corners[0]]);axes[0].plot(c[:,0],c[:,1],color='yellow')
        a,b,t=board_segment(corners)
        axes[0].plot([a[0],b[0]],[a[1],b[1]],color='lime',lw=30,alpha=.2)
    axes[1].set_title('Full-frame hand proposals; selected skeleton')
    for c in result['global_candidates']:
        for h in c['hands']:
            p=np.array(h['pixel_landmarks']);lo=p.min(axis=0);hi=p.max(axis=0)
            axes[1].plot([lo[0],hi[0],hi[0],lo[0],lo[0]],[lo[1],lo[1],hi[1],hi[1],lo[1]],color='gray',alpha=.4)
    for ax,h in [(axes[1],hand),(axes[2],hand)]:
        if h is not None:
            p=np.array(h['pixel_landmarks'])
            for name,ids in CHAINS.items():ax.plot(p[ids,0],p[ids,1],color=COLORS[name],lw=1.5)
    if hand is not None:
        p=np.array(hand['pixel_landmarks']);lo=p.min(axis=0)-40;hi=p.max(axis=0)+40
        axes[2].set(xlim=(max(0,lo[0]),min(raw.shape[1],hi[0])),ylim=(min(raw.shape[0],hi[1]),max(0,lo[1])))
    axes[2].set_title('Selected hand detail (anatomy unverified)')
    fig.suptitle(f'PTS {pts:.6f}s | green=middle orange=ring magenta=pinky cyan=index | previous adaptive detected: {old}')
    fig.tight_layout();fig.savefig(path,dpi=120);plt.close(fig)


def main(out):
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    baseline=read(ROOT/'dataset/hand_analysis/runs/barre_skeleton_20261104_v1/result.json')
    reference=cv2.imread(str(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000120.png'))
    rows=[];previous=None;previous_pts=None
    with FrettingHandSkeletonDetector(ROOT/'hand_landmarker.task',num_hands=2) as detector:
        for row in baseline['frames']:
            raw=cv2.imread(row['source_image']);pts=row['frame_pts_s']
            evidence,matrix=track(reference,raw)
            corners=project(REFERENCE_CORNERS,matrix) if evidence['status']=='valid' else None
            # Do not carry a hand over sparse samples, camera changes or long gaps.
            if previous_pts is None or not 0<pts-previous_pts<=.5:previous=None
            result=detect_global_fretting(detector,raw,corners,previous)
            chosen=result['selection']['selected']
            previous=None if chosen is None else chosen['hands'][0]['pixel_landmarks'];previous_pts=pts
            record={k:row[k] for k in ['source_id','frame_index','frame_pts_s','frame_pixel_sha256','source_image']}
            record.update(board_alignment=evidence,board_corners=None if corners is None else corners.tolist(),
                          board_scope='manual reference transferred by same-frame texture alignment; provisional',
                          previous_cue_used=any('continuity' in r['weights'] for v in result['rankings'] for r in v['ranked']),result=result)
            rows.append(record)
            picture(raw,result,corners,row['adaptive_focused']['selection']['selected'] is not None,pts,out/f'pts_{pts:.2f}.png')
            print(pts,'board',evidence['status'],'views',result['selection']['candidate_count'],'stage',result['output_stage'],flush=True)
    (out/'result.json').write_text(json.dumps(dict(frames=rows,score_is_probability=False,weights_status='heuristic_unvalidated',
         full_frame=True,num_hands=2,temporal_scope='Only prior samples <=0.5s; not a continuous tracking evaluation'),indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dataset/hand_analysis/runs/global_fretting_20261104_v2_direction_bonus')
    main(parser.parse_args().output)
