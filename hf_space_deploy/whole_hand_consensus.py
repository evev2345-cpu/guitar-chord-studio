"""Select one observed whole skeleton from current-frame views; never mix points."""
import numpy as np

def choose_candidate(candidates,previous=None,continuity_weight=.25):
    usable=[c for c in candidates if len(c.get('hands',[]))==1]
    if not usable:return dict(selected=None,status='no_current_observation')
    p=np.array([c['hands'][0]['pixel_landmarks'] for c in usable],float)
    if p.shape[1:]!=(21,2) or not np.isfinite(p).all():raise ValueError('Invalid whole skeleton')
    distance=np.median(np.linalg.norm(p[:,None]-p[None,:],axis=3),axis=2);scale=max(30.,float(np.median(np.ptp(p,axis=1).max(axis=1))))
    medoid=distance.mean(axis=1)/scale;continuity=np.zeros(len(p));weight=0.
    if previous is not None:
        old=np.asarray(previous,float)
        if old.shape!=(21,2) or not np.isfinite(old).all():raise ValueError('Invalid previous observation')
        # Relax history on a large actual current-frame palm move; never pin a moving hand.
        palms=p[:,[0,5,9,13,17]].mean(axis=1);shift=np.linalg.norm(palms.mean(axis=0)-old[[0,5,9,13,17]].mean(axis=0))/scale
        weight=continuity_weight if shift<.2 else 0.
        continuity=np.median(np.linalg.norm(p-old,axis=2),axis=1)/scale
    cost=medoid+weight*continuity;index=int(np.argmin(cost));spread=np.percentile(np.linalg.norm(p-p[index],axis=2),90,axis=0)
    return dict(selected=usable[index],status='observed_whole_hand_consensus',candidate_count=len(usable),
        medoid_cost=medoid.tolist(),continuity_cost=continuity.tolist(),continuity_weight_used=weight,
        per_landmark_cross_view_p90_px=spread.tolist(),selected_index=index,
        anatomical_validity='unknown',contact='unknown',per_finger_mixing=False,coordinates_adjusted=False)
