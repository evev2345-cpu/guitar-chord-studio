"""Whole-hand inference experiments with invertible crops, rotations and video tracking."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from joint_evidence_review import ROOT, BOARD, HAND, read

CROPS = {'baseline':(740,155,1135,420), 'square':(820,120,1170,470),
         'tight':(850,150,1110,420), 'context':(740,100,1190,500)}
CHAINS = {'thumb':[0,1,2,3,4], 'index':[0,5,6,7,8], 'middle':[0,9,10,11,12],
          'ring':[0,13,14,15,16], 'pinky':[0,17,18,19,20]}
COLORS = {'thumb':'white','index':'cyan','middle':'lime','ring':'orange','pinky':'magenta'}


def prepare_image(raw, crop, quarter_turns=0, mirror=False):
    """Integer right-angle transforms, exactly invertible in pixel coordinates."""
    x0,y0,x1,y1=crop
    if not (0<=x0<x1<=raw.shape[1] and 0<=y0<y1<=raw.shape[0]):
        raise ValueError('Invalid crop')
    image=raw[y0:y1,x0:x1].copy()
    height,width=image.shape[:2]
    transform=np.array([[1.,0.,-x0],[0.,1.,-y0],[0.,0.,1.]])
    for _ in range(quarter_turns%4):
        image=cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE)
        transform=np.array([[0.,-1.,height-1],[1.,0.,0.],[0.,0.,1.]])@transform
        width,height=height,width
    if mirror:
        image=cv2.flip(image,1)
        transform=np.array([[-1.,0.,width-1],[0.,1.,0.],[0.,0.,1.]])@transform
    return image,transform


def restore_hand(hand, image_shape, transform):
    h,w=image_shape[:2]
    points=np.array([[p.x*w,p.y*h] for p in hand],float)
    restored=cv2.perspectiveTransform(points[:,None,:],np.linalg.inv(transform))[:,0]
    return restored.tolist()


def serialize(result, image_shape, transform):
    return [dict(pixel_landmarks=restore_hand(hand,image_shape,transform),
                 handedness_raw=result.handedness[i][0].category_name,
                 handedness_score=float(result.handedness[i][0].score),
                 points_from_one_inference=True,per_finger_mixing=False)
            for i,hand in enumerate(result.hand_landmarks)]


def draw_panels(raw,candidates,path,title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    n=len(candidates)+1;cols=min(4,n);rows=(n+cols-1)//cols
    fig,axes=plt.subplots(rows,cols,figsize=(4*cols,4.5*rows),squeeze=False)
    for ax in axes.ravel():ax.axis('off')
    panels=[('Original (no labels)',None)]+[(c['candidate_id'], c.get('hands',[None])[0] if c.get('hands') else None) for c in candidates]
    for ax,(name,hand) in zip(axes.ravel(),panels):
        ax.imshow(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB));ax.set(xlim=(865,1090),ylim=(400,170));ax.axis('on')
        if hand:
            points=np.array(hand['pixel_landmarks'])
            for finger,indices in CHAINS.items():
                p=points[indices];ax.plot(p[:,0],p[:,1],color=COLORS[finger],lw=1.5)
        ax.set_title(name,fontsize=9)
    fig.suptitle(title+' | index=cyan middle=green ring=orange pinky=magenta',fontsize=11)
    fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(path,dpi=130);plt.close(fig)


def image_experiments(out,frames):
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    options=vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(ROOT/'hand_landmarker.task')),
        running_mode=vision.RunningMode.IMAGE,num_hands=1)
    outputs=[]
    with vision.HandLandmarker.create_from_options(options) as detector:
        for idx in frames:
            board=read(BOARD/'frames'/f'clip003012_f{idx:06d}_board.json')
            raw=cv2.imread(board['image_file'])
            if hashlib.sha256(raw.tobytes()).hexdigest()!=board['frame_pixel_sha256']:raise ValueError('Source pixels changed')
            candidates=[]
            for name,crop in CROPS.items():
                for turns in range(4):
                    for mirror in [False,True]:
                        image,transform=prepare_image(raw,crop,turns,mirror)
                        result=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)))
                        candidates.append(dict(candidate_id=f'{name}_r{turns*90}_'+('mirror' if mirror else 'native'),
                           crop=crop,quarter_turns=turns,mirror=mirror,source_transform=transform.tolist(),
                           hands=serialize(result,image.shape,transform),anatomical_validity='unreviewed'))
            for name in CROPS:
                draw_panels(raw,[c for c in candidates if c['candidate_id'].startswith(name+'_')],
                            out/f'frame{idx}_{name}_comparison.png',f'Frame {idx}: whole-hand inference')
            outputs.append(dict(frame_index=idx,frame_pts_s=board['frame_pts_s'],source_id=board['source_id'],
                frame_pixel_sha256=board['frame_pixel_sha256'],image_file=board['image_file'],candidates=candidates))
            print('Image experiments complete',idx,flush=True)
    (out/'image_results.json').write_text(json.dumps(outputs,indent=2),encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--frames',type=int,nargs='+',default=[120,210]);args=p.parse_args()
    if args.output.exists():raise FileExistsError('Use new output')
    args.output.mkdir(parents=True)
    image_experiments(args.output,args.frames)


if __name__=='__main__':main()
