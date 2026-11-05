"""Global two-hand proposals ranked by soft spatial cues; scores are not probabilities."""
import math
import numpy as np
from fretting_hand_skeleton import hand_bounding_crop,select_whole_hand


def board_segment(corners):
    c=np.asarray(corners,float)
    if c.shape!=(4,2) or not np.isfinite(c).all():raise ValueError('Expected nut-top, body-top, body-bottom, nut-bottom')
    nut=(c[0]+c[3])/2;body=(c[1]+c[2])/2
    thickness=float((np.linalg.norm(c[0]-c[3])+np.linalg.norm(c[1]-c[2]))/2)
    if np.linalg.norm(nut-body)<1 or thickness<1:raise ValueError('Degenerate board')
    # Nut and body extension scale with observed board thickness, not screen position.
    axis=(nut-body)/np.linalg.norm(nut-body)
    return body-axis*thickness,nut+axis*thickness*2,thickness


def score_hand(hand,image_shape,corners=None,previous=None):
    p=np.asarray(hand['pixel_landmarks'],float)
    if p.shape!=(21,2) or not np.isfinite(p).all():raise ValueError('Invalid hand')
    roots=p[[5,9,13,17]].mean(axis=0);direction=roots-p[0]
    up=float((1-direction[1]/max(np.linalg.norm(direction),1e-9))/2)
    cues={'upward':up};weights={}
    if corners is not None:
        a,b,thickness=board_segment(corners);axis=b-a
        q=p[[5,9,13,17,8,12,16,20]]
        t=np.clip((q-a)@axis/(axis@axis),0,1)
        distance=np.linalg.norm(q-(a+t[:,None]*axis),axis=1)
        cues['board_proximity']=float(np.exp(-.5*(np.median(distance)/(thickness*1.5))**2))
        weights['board_proximity']=.5
        c=np.asarray(corners,float);nut=(c[0]+c[3])/2;body=(c[1]+c[2])/2
        length=np.linalg.norm(body-nut);neck_axis=(body-nut)/length
        center=np.median(q,axis=0);delta=center-nut
        along=float(delta@neck_axis);across=float(delta@np.array([-neck_axis[1],neck_axis[0]]))
        # Broad anisotropic nut prior: still supports body-side/high-fret positions.
        cues['nut_prior']=float(np.exp(-.5*((along/(.85*length))**2+(across/(1.8*thickness))**2)))
        weights['nut_prior']=.35
    if previous is not None:
        old=np.asarray(previous,float)
        if old.shape!=(21,2) or not np.isfinite(old).all():raise ValueError('Invalid previous hand')
        scale=math.hypot(*image_shape[:2])*.15
        cues['continuity']=float(np.exp(-.5*(np.linalg.norm(roots-old[[5,9,13,17]].mean(axis=0))/scale)**2))
        weights['continuity']=.15
    # Direction can add support, never dilute strong board/continuity evidence.
    base=sum(cues[k]*w for k,w in weights.items())/sum(weights.values()) if weights else 0.
    bonus=.15*up
    return dict(score=float(base+bonus),base_score=float(base),direction_bonus=float(bonus),
                cues=cues,weights=dict(weights,upward_bonus=.15),
                scoring_version='nut_prior_hand_groups_v3',calibrated_probability=False)


def rank_view(hands,image_shape,corners=None,previous=None,minimum_score=.6,minimum_margin=.12):
    ranked=sorted([dict(hand=h,**score_hand(h,image_shape,corners,previous)) for h in hands],key=lambda x:x['score'],reverse=True)
    margin=ranked[0]['score']-ranked[1]['score'] if len(ranked)>1 else None
    accepted=bool(ranked and ranked[0]['score']>=minimum_score and (margin is None or margin>=minimum_margin))
    return dict(ranked=ranked,margin=margin,selected=ranked[0]['hand'] if accepted else None,
                status='candidate' if accepted else 'abstain',minimum_score=minimum_score,minimum_margin=minimum_margin)


def palm_center(hand):
    return np.asarray(hand['pixel_landmarks'],float)[[5,9,13,17]].mean(axis=0)


def select_hand_groups(candidates,image_shape,corners=None,previous=None,anchor=None):
    """Group physical hand locations before scoring; detection frequency is not a role vote."""
    radius=.08*math.hypot(*image_shape[:2]);groups=[]
    for candidate in candidates:
        for hand in candidate['hands']:
            center=palm_center(hand)
            if anchor is not None and np.linalg.norm(center-palm_center(anchor))>radius:continue
            member=dict(candidate, hands=[hand])
            choices=[g for g in groups if all(m['candidate_id']!=candidate['candidate_id'] and
                     np.linalg.norm(center-palm_center(m['hands'][0]))<=radius for m in g)]
            if choices:
                min(choices,key=lambda g:np.linalg.norm(center-np.mean([palm_center(m['hands'][0]) for m in g],axis=0))).append(member)
            else:groups.append([member])
    ranked=[]
    for i,members in enumerate(groups):
        scores=[score_hand(m['hands'][0],image_shape,corners,previous) for m in members]
        ranked.append(dict(group_id=i,score=float(np.median([s['score'] for s in scores])),
                           member_scores=scores,selection=select_whole_hand(members),members=members))
    ranked.sort(key=lambda g:g['score'],reverse=True)
    margin=None if len(ranked)<2 else ranked[0]['score']-ranked[1]['score']
    accepted=bool(ranked and ranked[0]['score']>=.6 and (margin is None or margin>=.12))
    return dict(selection=ranked[0]['selection'] if accepted else select_whole_hand([]),groups=ranked,
                margin=margin,minimum_score=.6,minimum_margin=.12,grouping_radius_px=radius,
                frequency_used_as_role_score=False,status='candidate' if accepted else 'abstain')


def detect_native_first(detector,image,crop,corners=None,previous=None,anchor=None):
    native=detector.detect(image,crop,quarter_turns=[0])
    first=select_hand_groups(native['candidates'],image.shape,corners,previous,anchor)
    reasons=[]
    if first['selection']['selected'] is None:reasons.append('native_selection_abstained')
    else:
        best=first['groups'][0]
        if best['score']<.8:reasons.append('native_role_score_below_0.8')
        if first['margin'] is not None and first['margin']<.2:reasons.append('native_role_margin_below_0.2')
    candidates=list(native['candidates'])
    if reasons:candidates.extend(detector.detect(image,crop,quarter_turns=[1,2,3])['candidates'])
    grouped=select_hand_groups(candidates,image.shape,corners,previous,anchor)
    return dict(candidates=candidates,group_ranking=grouped,
                rotation_policy=dict(mode='native_first',extra_rotations_used=bool(reasons),reasons=reasons,
                                     inference_count=len(candidates),native_group_ranking=first,
                                     role_confidence_is_anatomical_confidence=False))


def detect_global_fretting(detector,image,corners=None,previous=None):
    h,w=image.shape[:2]
    global_result=detect_native_first(detector,image,(0,0,w,h),corners,previous)
    rankings=[]
    for c in global_result['candidates']:
        rank=rank_view(c['hands'],image.shape,corners,previous);rankings.append(dict(candidate_id=c['candidate_id'],**rank))
    grouped=global_result['group_ranking']
    selection=grouped['selection']
    selected=selection['selected']
    refined=None;crop=None
    if selected is not None:
        crop=hand_bounding_crop(selected['hands'][0]['pixel_landmarks'],image.shape)
        local=detect_native_first(detector,image,crop,corners,previous,anchor=selected['hands'][0])
        local_groups=local['group_ranking']
        refined=dict(candidates=local['candidates'],selection=local_groups['selection'],group_ranking=local_groups,
                     rotation_policy=local['rotation_policy'])
    return dict(global_candidates=global_result['candidates'],rankings=rankings,global_selection=selection,group_ranking=grouped,
                refined=refined,adaptive_crop=crop,anatomical_validity='unknown',contact='unknown',
                selection=selection if refined is None or refined['selection']['selected'] is None else refined['selection'],
                output_stage='global' if refined is None or refined['selection']['selected'] is None else 'refined',
                global_rotation_policy=global_result['rotation_policy'],
                inference_count=global_result['rotation_policy']['inference_count']+(0 if refined is None else refined['rotation_policy']['inference_count']),
                calibrated_probability=False)
