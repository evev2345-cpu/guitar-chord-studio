"""Focused whole-hand candidates. No finger relabeling, point mixing, or contact inference."""
import hashlib

import cv2
import numpy as np

from improve_hand_skeleton import prepare_image, serialize


def hand_bounding_crop(points,image_shape,padding=.25,minimum_size=220):
    """Square crop from one complete proposal; retain its provenance, not its identity as truth."""
    p=np.asarray(points,float)
    if p.shape!=(21,2) or not np.isfinite(p).all():raise ValueError('Invalid whole-hand proposal')
    h,w=image_shape[:2]
    lower=p.min(axis=0);upper=p.max(axis=0)
    side=min(max(minimum_size,float((upper-lower).max())*(1+2*padding)),h,w)
    center=(lower+upper)/2
    x0=int(np.clip(np.floor(center[0]-side/2),0,w-side))
    y0=int(np.clip(np.floor(center[1]-side/2),0,h-side))
    return (x0,y0,min(w,x0+int(np.ceil(side))),min(h,y0+int(np.ceil(side))))


def select_whole_hand(candidates):
    """Select an actual 21-point inference by whole-skeleton agreement."""
    usable=[]
    for c in candidates:
        if len(c.get('hands',[]))!=1:
            continue
        p=np.asarray(c['hands'][0]['pixel_landmarks'],float)
        if p.shape!=(21,2) or not np.isfinite(p).all():
            raise ValueError('Expected one complete finite 21-point skeleton')
        usable.append((c,p))
    if not usable:
        return dict(status='no_unique_hand',selected=None,candidate_count=0,anatomical_validity='unknown')
    points=np.array([p for _,p in usable])
    pair=np.median(np.linalg.norm(points[:,None,:,:]-points[None,:,:,:],axis=3),axis=2)
    index=int(np.argmin(pair.sum(axis=1)))
    candidate=usable[index][0]
    selected=np.asarray(candidate['hands'][0]['pixel_landmarks'])
    return dict(status='whole_hand_candidate' if len(usable)>=3 else 'insufficient_views_candidate',
                selected=candidate,candidate_count=len(usable),
                pairwise_median_joint_distance_px=pair.tolist(),
                whole_skeleton_spread_px=float(np.percentile(np.linalg.norm(points-selected,axis=2),90)),
                skeleton_sha256=hashlib.sha256(selected.astype('<f8').tobytes()).hexdigest(),
                per_finger_mixing=False,coordinates_manually_adjusted=False,
                anatomical_validity='unknown',contact='unknown',
                confidence_calibrated=False,
                limitations=['Same-model agreement cannot prove anatomical correctness',
                             'Selection contains every point from one actual inference, never a per-finger medoid',
                             'Cropping parameters must include the complete target hand'])


class FrettingHandSkeletonDetector:
    def __init__(self,model_path,num_hands=1):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        self.mp=mp
        options=vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.IMAGE,num_hands=num_hands)
        self.detector=vision.HandLandmarker.create_from_options(options)

    def detect(self,image,crop,quarter_turns=None):
        candidates=[]
        for turns in (range(4) if quarter_turns is None else quarter_turns):
            transformed,matrix=prepare_image(image,crop,turns,False)
            result=self.detector.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB,
                           data=cv2.cvtColor(transformed,cv2.COLOR_BGR2RGB)))
            candidates.append(dict(candidate_id=f'focused_r{90*turns}',crop=list(crop),
                                   quarter_turns=turns,mirror=False,source_transform=matrix.tolist(),
                                   hands=serialize(result,transformed.shape,matrix)))
        return dict(candidates=candidates,selection=select_whole_hand(candidates))

    def detect_adaptive(self,image,search_crop):
        proposal=self.detect(image,search_crop)
        selected=proposal['selection']['selected']
        if selected is None:
            return dict(candidates=[],selection=select_whole_hand([]),proposal=proposal,
                        adaptive_crop=None,status='no_hand_proposal')
        crop=hand_bounding_crop(selected['hands'][0]['pixel_landmarks'],image.shape)
        result=self.detect(image,crop)
        result.update(proposal=proposal,adaptive_crop=list(crop),
                      status='adaptive_whole_hand_candidate',
                      crop_scope='current-frame whole-hand bounds, not scene-cut or prior-frame imputation')
        return result

    def close(self):self.detector.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
