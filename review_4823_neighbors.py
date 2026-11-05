"""Inspect requested immediate neighbors with unchanged native-first selection."""
import hashlib
import json
import cv2
import numpy as np
from joint_evidence_review import ROOT,read
from fretting_hand_skeleton import FrettingHandSkeletonDetector
from global_fretting_hand import detect_global_fretting
from review_fretboard_clip import track,project,REFERENCE_CORNERS
from improve_hand_skeleton import CHAINS,COLORS


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=ROOT/'dataset/hand_analysis/runs/neighbors_4823_20261104_v1'
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    baseline=read(ROOT/'dataset/hand_analysis/runs/barre_skeleton_20261104_v1/result.json')['frames'][0]
    pts=read(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/video_frame_pts.json')['frames']
    reference=cv2.imread(str(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000120.png'))
    cap=cv2.VideoCapture(baseline['source_video']);cap.set(cv2.CAP_PROP_POS_FRAMES,4821)
    records=[];fig,axes=plt.subplots(2,5,figsize=(16,8))
    with FrettingHandSkeletonDetector(ROOT/'hand_landmarker.task',num_hands=2) as detector:
        for column,index in enumerate(range(4821,4826)):
            ok,raw=cap.read()
            if not ok:raise RuntimeError('decode failed')
            path=out/f'frame_{index}.png';cv2.imwrite(str(path),raw)
            evidence,matrix=track(reference,raw)
            corners=project(REFERENCE_CORNERS,matrix) if evidence['status']=='valid' else None
            result=detect_global_fretting(detector,raw,corners,previous=None)
            record=dict(frame_index=index,frame_pts_s=float(pts[index]['pts_time']),source_id=baseline['source_id'],
                        source_image=str(path),frame_pixel_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),
                        board_alignment=evidence,result=result)
            records.append(record)
            selected=result['selection']['selected']
            for row in range(2):
                ax=axes[row,column];ax.imshow(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB));ax.set(xlim=(830,1050),ylim=(430,165));ax.axis('off')
                ax.set_title(f"f{index} {record['frame_pts_s']:.6f}s\n"+('Original' if row==0 else result['selection']['status']),fontsize=9)
                if row and selected:
                    p=np.array(selected['hands'][0]['pixel_landmarks'])
                    for name,ids in CHAINS.items():ax.plot(p[ids,0],p[ids,1],color=COLORS[name],lw=1.4)
            print(index,record['frame_pts_s'],result['selection']['candidate_count'],result['output_stage'],
                  [(round(g['score'],3),g['selection']['candidate_count'],np.asarray(g['selection']['selected']['hands'][0]['pixel_landmarks'])[[5,9,13,17],0].mean()) for g in result['group_ranking']['groups']],flush=True)
    cap.release()
    fig.suptitle('Top: original / Bottom: selected inference | cyan=index green=middle orange=ring magenta=pinky white=thumb')
    fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(out/'comparison.png',dpi=140);plt.close(fig)
    (out/'result.json').write_text(json.dumps(dict(frames=records,previous_cue_used=False,algorithm_changed=False),indent=2),encoding='utf-8')


if __name__=='__main__':main()
