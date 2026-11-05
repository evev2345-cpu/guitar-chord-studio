"""Inspect every frame around 200s without smoothing or changing the hand detector."""
import hashlib
import argparse
from pathlib import Path
import json
import cv2
import numpy as np
from joint_evidence_review import ROOT,read
from fretting_hand_skeleton import FrettingHandSkeletonDetector
from global_fretting_hand import detect_global_fretting
from review_fretboard_clip import track,project,REFERENCE_CORNERS
from improve_hand_skeleton import CHAINS,COLORS


def montage(records,indices,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,6,figsize=(18,14))
    for n,i in enumerate(indices):
        r=records[i];raw=cv2.imread(r['source_image']);s=r['result']['selection']['selected']
        for col in range(2):
            ax=axes[n//3,(n%3)*2+col];ax.imshow(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB))
            ax.set(xlim=(830,1050),ylim=(430,165));ax.axis('off')
            ax.set_title(f"{r['frame_pts_s']:.6f}s f{r['frame_index']} "+('original' if col==0 else 'inference'),fontsize=9)
            if col and s:
                p=np.array(s['hands'][0]['pixel_landmarks'])
                for finger,ids in CHAINS.items():ax.plot(p[ids,0],p[ids,1],color=COLORS[finger],lw=1.4)
    fig.suptitle('Original / inference pairs; exact source PTS shown | middle=green ring=orange pinky=magenta index=cyan')
    fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(path,dpi=130);plt.close(fig)


def main(out):
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    baseline=read(ROOT/'dataset/hand_analysis/runs/barre_skeleton_20261104_v1/result.json')
    source=baseline['frames'][0]['source_id'];video=baseline['frames'][0]['source_video']
    probe=read(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/video_frame_pts.json')['frames']
    center=min(range(len(probe)),key=lambda i:abs(float(probe[i]['pts_time'])-200))
    reference=cv2.imread(str(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000120.png'))
    cap=cv2.VideoCapture(video);cap.set(cv2.CAP_PROP_POS_FRAMES,center-24);records=[]
    with FrettingHandSkeletonDetector(ROOT/'hand_landmarker.task',num_hands=2) as detector:
        for index in range(center-24,center+25):
            ok,raw=cap.read()
            if not ok:raise RuntimeError('decode failed')
            pts=float(probe[index]['pts_time']);path=out/f'frame_{index}.png';cv2.imwrite(str(path),raw)
            evidence,matrix=track(reference,raw)
            corners=project(REFERENCE_CORNERS,matrix) if evidence['status']=='valid' else None
            result=detect_global_fretting(detector,raw,corners,previous=None)
            record=dict(frame_index=index,frame_pts_s=pts,source_id=source,source_image=str(path),
                frame_pixel_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),board_alignment=evidence,result=result)
            s=result['selection']['selected']
            if s:
                p=np.array(s['hands'][0]['pixel_landmarks'])
                record['middle_joints']=p[9:13].tolist()
                record['middle_tip_to_index_tip_px']=float(np.linalg.norm(p[12]-p[8]))
                if records and 'middle_joints' in records[-1]:
                    record['middle_joint_displacements_px']=np.linalg.norm(p[9:13]-np.array(records[-1]['middle_joints']),axis=1).tolist()
            records.append(record)
            print(index,pts,result['selection']['candidate_count'],flush=True)
    cap.release()
    (out/'result.json').write_text(json.dumps(dict(frames=records,diagnostic='independent IMAGE inference; no previous-position score or smoothing; not VIDEO tracking'),indent=2),encoding='utf-8')
    montage(records,list(range(0,49,6)),out/'comparison.png')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
