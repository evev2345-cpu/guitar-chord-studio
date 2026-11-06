"""Evaluate unchanged focused hand inference and adaptive crops after 3:15, with photo evidence."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from fretting_hand_skeleton import FrettingHandSkeletonDetector
from improve_hand_skeleton import CHAINS,COLORS
from joint_evidence_review import ROOT,read

TIMES=[195.,195.5,196.,198.,200.,202.,206.,210.,214.,217.25,220.,225.]


def points(result):
    s=result['selection']['selected']
    return None if s is None else s['hands'][0]['pixel_landmarks']


def picture(raw,before,fixed,adaptive,pts,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    after=points(adaptive)
    source_points=np.array(after) if after is not None else np.array([[820,180],[1050,420]])
    x0=max(600,float(source_points[:,0].min())-50);x1=min(1180,float(source_points[:,0].max())+50)
    y0=max(80,float(source_points[:,1].min())-35);y1=min(460,float(source_points[:,1].max())+35)
    fig,axes=plt.subplots(1,4,figsize=(17,5))
    for ax,(title,hand) in zip(axes,[('Original',None),('Legacy crop candidate',points(before)),
                                   ('Earlier fixed focused crop',points(fixed)),('Adaptive focused candidate',after)]):
        ax.imshow(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB));ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off');ax.set_title(title,fontsize=10)
        if hand is not None:
            p=np.array(hand)
            for finger,ids in CHAINS.items():ax.plot(p[ids,0],p[ids,1],lw=1.5,color=COLORS[finger])
    fig.suptitle(f'PTS {pts:.6f}s | middle=green, ring=orange, pinky=magenta, index=cyan | candidates, not contact truth')
    fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(path,dpi=125);plt.close(fig)


def main(out):
    if out.exists():raise FileExistsError('Use new output')
    out.mkdir(parents=True)
    cases=read(ROOT/'dataset/chord_video_review/cases.json');video=ROOT/cases[0]['video']
    frame_probe=read(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/video_frame_pts.json')['frames']
    frames=[(i,float(f.get('pts_time',f['best_effort_timestamp_time']))) for i,f in enumerate(frame_probe)]
    cap=cv2.VideoCapture(str(video));rows=[]
    with FrettingHandSkeletonDetector(ROOT/'hand_landmarker.task') as detector:
        for requested in TIMES:
            index,pts=min(frames,key=lambda v:abs(v[1]-requested))
            cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,raw=cap.read()
            if not ok:raise RuntimeError('Frame decode failed')
            cv2.imwrite(str(out/f'frame_{index}_source.png'),raw)
            legacy=detector.detect(raw,(740,155,1135,420))
            fixed=detector.detect(raw,(850,150,1110,420))
            adaptive=detector.detect_adaptive(raw,(650,100,1180,460))
            row=dict(requested_s=requested,frame_index=index,frame_pts_s=pts,
                     source_id=cases[0].get('source_id'),source_video=str(video),
                     frame_pixel_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),
                     source_image=str(out/f'frame_{index}_source.png'),
                     legacy=legacy,fixed_focused=fixed,adaptive_focused=adaptive,
                     scene_cut_assumption='user_reports_no_scene_cuts_not_exhaustively_verified',
                     visual_anatomical_status='unreviewed',contact='unknown',
                     video_position_used_as_ground_truth=False)
            rows.append(row)
            picture(raw,legacy,fixed,adaptive,pts,out/f'pts_{requested:.2f}_comparison.png')
            print('barre sample',pts,'fixed views',fixed['selection']['candidate_count'],
                  'adaptive views',adaptive['selection']['candidate_count'],flush=True)
    cap.release()
    digest=hashlib.sha256()
    with video.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    for row in rows:row['source_id']=digest.hexdigest()
    (out/'result.json').write_text(json.dumps(dict(source_id=digest.hexdigest(),frames=rows,
         inference='independent IMAGE mode; no temporal coordinate imputation',
         physical_fret_or_string_detection=False),indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    main(p.parse_args().output)
