"""Reference-only contact sheets; no classifier scores used for sampling."""
import cv2
import numpy as np
from joint_evidence_review import ROOT,read


def main():
    folder=ROOT/'dataset/integration_review/runs/tutorial_reference_20261105_v1'
    rows=read(folder/'frames.json');video=ROOT/read(ROOT/'dataset/chord_video_review/cases.json')[0]['video']
    cap=cv2.VideoCapture(str(video));panels=[]
    for r in rows:
        cells=[]
        for delta in [-.2,0,.2]:
            index=r['frame_index']+round(delta*24);cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,im=cap.read()
            if not ok:raise RuntimeError('decode failed')
            cv2.imwrite(str(folder/f'neighbor_{index}.png'),im)
            a=cv2.resize(im[170:420,760:1120],(360,250));b=cv2.resize(im[460:700,870:1280],(360,210))
            cell=np.vstack([a,b]);cv2.putText(cell,f"{r['time']+delta:.2f}s f{index}",(5,22),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
            cells.append(cell)
        panels.append(np.hstack(cells))
    for k in range(4):cv2.imwrite(str(folder/f'stability_{k}.png'),np.vstack(panels[k*4:k*4+4]))
    cap.release()


if __name__=='__main__':main()
