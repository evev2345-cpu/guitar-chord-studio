"""Scope-limited semantic confirmation; never promotes precise geometry."""
import copy
import hashlib
from pathlib import Path
import cv2
import numpy as np
from scipy.signal import find_peaks
from fretboard_frame_identity import assert_same_frame

# Reviewed one-by-one; the values are source-specific geometry anchors, NOT n-1.
WIRE_CATALOG=[
 dict(wire_id='metal_x1057',physical_candidate=1,reference_x=1057.,frame120_visibility='visible',
      evidence='user first-metal semantic confirmation + original visible metal segment'),
 dict(wire_id='metal_x1004',physical_candidate=2,reference_x=1004.,frame120_visibility='partial',
      evidence='visible upper segment in frame120; next exposed metal after anchored first wire in frame71'),
 dict(wire_id='metal_x954',physical_candidate=3,reference_x=954.5,frame120_visibility='occluded',
      evidence='not visible in frame120; exposed third line in frame71 only, transfer remains estimate'),
 dict(wire_id='metal_x908',physical_candidate=4,reference_x=908.,frame120_visibility='visible',
      evidence='separate visible line frame120 + exposed sequence in frame71'),
 dict(wire_id='metal_x865',physical_candidate=5,reference_x=865.,frame120_visibility='visible',
      evidence='visible line and nearby single-inlay cell; exposed sequence in frame71'),
 dict(wire_id='metal_x824',physical_candidate=6,reference_x=824.,frame120_visibility='visible',
      evidence='visible line and adjacent inlay cell; exposed sequence in frame71')]


def validate_semantic_review(review,reference_identity):
    if review['source_id']!=reference_identity['source_id'] or review['frame_index']!=120 or reference_identity['frame_index']!=120:
        raise ValueError('Semantic review belongs to another source/frame')
    if abs(review['frame_pts_s']-reference_identity['frame_pts_s'])>5e-7:
        raise ValueError('Semantic review PTS mismatch')
    confirmations={c['object']:c for c in review['confirmations']}
    required=['original_nut','capo','first_physical_metal_fret']
    if not all(confirmations.get(k,{}).get('semantic_identity_confirmed') is True for k in required):
        raise ValueError('Missing scoped semantic confirmation')
    if confirmations['first_physical_metal_fret'].get('physical_fret_number_confirmed')!=1:
        raise ValueError('Only the first physical metal wire was confirmed')
    return dict(method=review['review_method'],reviewer=review['reviewer'],
        user_response=review['user_response_verbatim'],frame_index=120,
        scope='object identity and first physical metal wire number only',
        displayed_image_method=review['displayed_image_method'],
        independent_pixel_ground_truth=False,precise_endpoints_confirmed=False,
        other_frames_confirmed=False,other_fret_numbers_confirmed=False,
        strings_confirmed=False,contact_confirmed=False)


def original_wire_support(image,endpoints,visible=True,partial=False):
    if not visible:return dict(status='not_measured_occluded',points=[],reason='Do not infer observation through hand')
    endpoints=np.asarray(endpoints,float)
    ylo,yhi=sorted(endpoints[:,1])
    ylo=max(ylo+4,0);yhi=min(yhi-3,image.shape[0]-1)
    if partial:yhi=min(yhi,ylo+22)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)
    ridge=gray-cv2.GaussianBlur(gray,(0,1),sigmaX=3)
    samples=[];strength=[]
    for y in np.arange(ylo,yhi+1,2):
        expected=float(np.interp(y,endpoints[:,1],endpoints[:,0]))
        a=max(0,int(expected)-8);b=min(image.shape[1],int(expected)+9)
        x=a+int(np.argmax(ridge[round(y),a:b]));value=float(ridge[round(y),x])
        if value>6:samples.append([float(x),float(y)]);strength.append(value)
    if len(samples)<6:return dict(status='insufficient_local_support',points=samples)
    pts=np.asarray(samples)
    keep=np.ones(len(pts),bool)
    for _ in range(3):
        m,b=np.polyfit(pts[keep,1],pts[keep,0],1)
        residual=np.abs(pts[:,0]-(m*pts[:,1]+b))
        keep=residual<=max(1.5,2.5*np.median(residual))
        if keep.sum()<6:return dict(status='ambiguous_local_ridge',points=samples)
    ys=[float(pts[keep,1].min()),float(pts[keep,1].max())]
    return dict(status='image_supported_segment',points=pts[keep].tolist(),
        fitted_endpoints=[[float(m*y+b),y] for y in ys],
        median_residual_px=float(np.median(residual[keep])),median_contrast=float(np.median(strength)),
        method='local positive horizontal highpass ridge in manually selected search band; heuristic, not pixel GT')


def exposed_wire_sequence(image):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)
    ridge=np.maximum(gray-cv2.GaussianBlur(gray,(0,1),sigmaX=3),0)
    profile=np.mean(ridge[230:270,780:1080],axis=0)
    peaks,properties=find_peaks(profile,distance=12,prominence=4)
    # Manual audit threshold distinguishes inlay spots from full metal segments
    # in this exposed frame; it is not a generic calibrated detector threshold.
    candidates=[dict(x=int(x+780),strength=float(profile[x]),prominence=float(p)) for x,p in zip(peaks,properties['prominences'])]
    metals=sorted([p for p in candidates if p['prominence']>=40],key=lambda p:-p['x'])
    return dict(frame_index=71,roi_original=[780,230,1080,270],candidates=candidates,
                selected_visible_metals=metals,threshold_source='agent clear-frame audit heuristic',
                number_source='agent visible order counted from transferred first-wire anchor; not user confirmation')


def apply_scoped_review(board,review,reference_identity,wire_reviews,review_file_hash):
    scope=validate_semantic_review(review,reference_identity)
    if board['source_id']!=reference_identity['source_id']:raise ValueError('Different source; reject semantic transfer')
    out=copy.deepcopy(board)
    is_reference=board['frame_index']==reference_identity['frame_index']
    if is_reference:assert_same_frame(board,reference_identity)
    alignment=board['geometry_validity']['alignment']
    transfer_ok=(board['source_id']==reference_identity['source_id'] and
        alignment.get('status')=='valid' and alignment.get('reference_frame_index')==120 and
        board.get('identity_validation',{}).get('status')=='verified_against_redecoded_source' and
        board.get('motion_validation',{}).get('status')=='consistent_with_recomputed_motion')
    out['semantic_review']=dict(**scope,review_file_sha256=review_file_hash,
        applies_directly_to_this_frame=is_reference,
        reference_frame_pts_s=reference_identity['frame_pts_s'],
        reference_frame_pixel_sha256=reference_identity['frame_pixel_sha256'],
        transfer_status='reference_frame' if is_reference else ('candidate_only' if transfer_ok else 'unknown'))
    out['objects']={name:dict(semantic_identity_status='user_confirmed_on_generated_annotation' if is_reference else ('reference_transfer_candidate' if transfer_ok else 'unknown'),
        human_pixel_annotation=False,precise_geometry_status='unverified',source_frame_index=120)
        for name in ['original_nut','capo','first_physical_metal_fret']}
    seen_geometry_ids=set()
    for fret in out['frets']:
        # Geometry binding precedes any semantic number. Don't decrement IDs.
        endpoints=fret.get('reference_endpoints')
        x=float(np.mean(np.asarray(endpoints)[:,0])) if endpoints else None
        matches=[c for c in WIRE_CATALOG if x is not None and abs(c['reference_x']-x)<2]
        if x is not None and abs(x-1114.)<2:
            fret.update(object_type='nut_boundary',numbering_status='nut_zero_convention',
                        confirmed_physical_fret_num=None)
            continue
        if len(matches)!=1:
            fret.update(confirmed_physical_fret_num=None,numbering_status='unknown_unmatched_geometry')
            continue
        entry=matches[0]
        if entry['wire_id'] in seen_geometry_ids:raise ValueError('Duplicate geometry binding')
        seen_geometry_ids.add(entry['wire_id'])
        evidence=wire_reviews[entry['wire_id']]
        # Keep existing correct physical candidate indices; a source-specific
        # correspondence record explains old annotations without arithmetic.
        fret['parent_fret_num']=fret['fret_num']
        fret['fret_num']=entry['physical_candidate']
        fret['physical_fret_candidate']=entry['physical_candidate']
        fret['wire_id']=entry['wire_id']
        fret['numbering_evidence']=copy.deepcopy(evidence)
        confirmed=is_reference and entry['physical_candidate']==1 and evidence['frame120_support']['status']=='image_supported_segment'
        fret['confirmed_physical_fret_num']=1 if confirmed else None
        fret['numbering_status']='semantic_confirmed_geometry_binding_provisional' if confirmed else (
            'agent_individually_reviewed_candidate' if is_reference else ('transferred_candidate_only' if transfer_ok else 'unknown_transfer_not_validated'))
        fret['confirmation_scope']='user semantic number only, not precise endpoints' if confirmed else None
        fret['coordinate_human_verified']=False
        fret['relative_fret']=None
        fret['relative_fret_candidate']=entry['physical_candidate']-1
        fret['relative_fret_status']='conditional_on_geometrically_inferred_capo1_not_user_confirmed'
        fret['visibility_status']=entry['frame120_visibility'] if is_reference else 'unreviewed_in_this_frame'
        if is_reference and entry['frame120_visibility']=='occluded':
            fret['source']='estimated'
            fret['geometry_source']='retained_parent_manual_geometry; frame71 supports identity only, not frame120 endpoints'
        # All lines remain model/manual estimates outside measured support.
    out['capo'].update(value=None,status='unknown',physical_fret_candidate=1,
        semantic_identity_status=out['objects']['capo']['semantic_identity_status'],
        candidate_source='agent_geometric_inference_clamp_between_original_nut_and_first_metal',
        user_confirmed_stop_fret=False,independently_verified=False,
        inference=dict(nut_x=1114,first_wire_x=1057,clamp_x=1075,
            normalized_position_in_first_space=(1114-1075)/(1114-1057),
            conclusion='candidate capo1, conditional on actual all-string clamping',reference_frame_index=120))
    out['geometry_validity'].update(exact_geometry_verified=False,contact_fret_decision_allowed=False,
        semantic_confirmation_applies=is_reference,
        reasons=['semantic label confirmation is not original-pixel endpoint ground truth',
                 'manual ROI and transferred coordinates remain unverified',
                 'physical string identities/contact not confirmed'])
    out['geometry_validity']['status']='suspect' if is_reference or transfer_ok else 'unknown'
    return out
