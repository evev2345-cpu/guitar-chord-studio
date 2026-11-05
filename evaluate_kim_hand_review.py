"""Evaluate immutable raw observations against supplied Kim review; no fitting or inference."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from hand_frame_contract import file_sha256,adapt_geometry,apply_geometry_gate
from hand_quality import location_gate

ROOT=Path(__file__).resolve().parent
OUT=Path('dataset/hand_analysis/runs/frame120_Kim_review_20261103_v3')
NAMES={4:'thumb_tip',5:'index_MCP',6:'index_PIP',7:'index_DIP',8:'index_tip',12:'middle_tip',16:'ring_tip',20:'pinky_tip'}
TIP_NAMES={4:'thumb',8:'index',12:'middle',16:'ring',20:'pinky'}


def associate_visible_points(review,hands,max_median=50.,inlier_radius=30.,minimum_inliers=4,margin=50.):
    """Same landmark IDs, original pixels, no registration/translation or wrist imputation."""
    labels=[l for l in review['landmarks'] if l['visibility']=='visible']
    scores=[]
    for hand in hands:
        errors=[float(np.linalg.norm(np.asarray(hand['landmarks'][p['index']]['pixel'])-p['pixel'])) for p in labels]
        scores.append(dict(hand_index=hand['hand_index'],visible_points=len(labels),
                           median_error_px=float(np.median(errors)) if errors else None,
                           mean_error_px=float(np.mean(errors)) if errors else None,
                           inliers_within_30px=sum(e<=inlier_radius for e in errors),errors_px=errors))
    scores.sort(key=lambda s:float('inf') if s['median_error_px'] is None else s['median_error_px'])
    eligible=bool(scores and len(labels)>=minimum_inliers and scores[0]['median_error_px']<=max_median
                  and scores[0]['inliers_within_30px']>=minimum_inliers)
    separation=None if len(scores)<2 else scores[1]['median_error_px']-scores[0]['median_error_px']
    unambiguous=eligible and (separation is None or separation>=margin)
    return dict(status='matched_for_evaluation' if unambiguous else 'ambiguous_or_insufficient',
                derived_hand_index=scores[0]['hand_index'] if unambiguous else None,
                original_fretting_hand_index=review.get('fretting_hand_index'),candidates=scores,
                runner_up_median_margin_px=separation,
                method='same-ID multiple visible landmarks in original pixels; no coordinate fitting',
                thresholds=dict(max_median_px=max_median,inlier_radius_px=inlier_radius,minimum_inliers=minimum_inliers,minimum_margin_px=margin),
                thresholds_status='association_heuristics_not_a_validated_hand_accuracy_metric')


def validate_identity(review,observation,image_path):
    for key in ['source_id','frame_index','frame_pixel_sha256']:
        if review[key]!=observation[key]:raise ValueError('Review observation mismatch: '+key)
    if abs(review['frame_pts_s']-observation['frame_pts_s'])>1e-6:raise ValueError('Review PTS mismatch')
    if file_sha256(image_path)!=review['image_file_sha256']:raise ValueError('Review PNG hash mismatch')


def evaluate(review,obs):
    association=associate_visible_points(review,obs['hands'])
    if association['derived_hand_index'] is None:
        return dict(association=association,status='hand_association_unresolved',point_errors=[])
    hand=next(h for h in obs['hands'] if h['hand_index']==association['derived_hand_index'])
    roi_association=associate_visible_points(review,obs['roi_observations'])
    roi=next((h for h in obs['roi_observations'] if h['hand_index']==roi_association['derived_hand_index']),None)
    points=[]
    for label in review['landmarks']:
        if label['visibility']!='visible':continue
        index=label['index'];prediction=hand['landmarks'][index]['pixel'];target=label['pixel']
        error=float(np.linalg.norm(np.array(prediction)-target))
        roi_point=None if roi is None else roi['landmarks'][index]['pixel']
        roi_error=None if roi_point is None else float(np.linalg.norm(np.array(roi_point)-target))
        gate=obs['raw_location_quality'].get(TIP_NAMES.get(index,''))
        points.append(dict(index=index,name=NAMES[index],human_pixel=target,
                           full_observed_pixel=prediction,full_error_px=error,
                           roi_observed_pixel=roi_point,roi_error_px=roi_error,
                           production_raw_gate=gate,
                           production_gate_scope='fingertip_location' if gate else 'joint_not_gated_in_production',
                           additional_spatial_diagnostic=location_gate(hand,obs['roi_observations'],index),
                           within_current_6px=error<=6,
                           excessive_location_abstention_at_6px=bool(gate and gate['decision']=='abstain' and error<=6),
                           contact='unknown'))
    errors=np.array([p['full_error_px'] for p in points]);roi_errors=[p['roi_error_px'] for p in points if p['roi_error_px'] is not None]
    tips=[p for p in points if p['production_raw_gate'] is not None]
    accurate_tips=[p for p in tips if p['within_current_6px']]
    sensitivity=[]
    for radius in [3,6,9,12]:
        passing=sum(p['full_error_px']<=radius for p in points)
        sensitivity.append(dict(radius_px=radius,full_points_within_radius=passing,visible_points=len(points),
            empirical_coverage=passing/len(points),scope='one-frame development comparison, no threshold change'))
    ablations=[]
    for mode,threshold in [('current_ROI_6px',6),('development_ROI_12px',12),('development_ROI_24px',24),('development_ROI_32px',32),('development_without_ROI_gate',None)]:
        passed=[]
        for p in tips:
            gate=p['production_raw_gate']
            allow=threshold is None or (gate['secondary_pixel'] is not None and gate['cross_view_distance_px']<=threshold)
            allow=allow and not(gate['speed_px_per_second'] is not None and gate['speed_px_per_second']>180)
            passed.append(allow)
        ablations.append(dict(mode=mode,passed=sum(passed),withheld=len(tips)-sum(passed),
            excessive_withholding_within_6px=sum(not allow and p['within_current_6px'] for allow,p in zip(passed,tips)),
            passed_but_error_over_6px=sum(allow and not p['within_current_6px'] for allow,p in zip(passed,tips)),
            scope='development ablation on labeled frame only, not deployed'))
    return dict(status='evaluated',association=association,roi_association=roi_association,
                visible_points=len(points),unknown_points=sum(l['visibility']=='unknown' for l in review['landmarks']),
                full_error=dict(mean_px=float(errors.mean()),median_px=float(np.median(errors)),max_px=float(errors.max())),
                roi_error=dict(mean_px=float(np.mean(roi_errors)),median_px=float(np.median(roi_errors)),max_px=float(np.max(roi_errors))) if roi_errors else None,
                point_errors=points,development_radius_comparison=sensitivity,
                development_gate_ablations=ablations,
                current_fingertip_gate=dict(evaluable_tips=len(tips),passed=sum(p['production_raw_gate']['decision']!='abstain' for p in tips),
                    withheld=sum(p['production_raw_gate']['decision']=='abstain' for p in tips),
                    within_6px_tips=len(accurate_tips),excessive_withholding_count=sum(p['excessive_location_abstention_at_6px'] for p in tips),
                    denominator_note='geometric 6px criterion on this human-reviewed photo, not contact accuracy'),
                speed_gate_evaluation='not_evaluable_from_one_labeled_frame; frame120 previous selected observation unavailable',
                current_thresholds_unchanged=True,predictions_moved=False,contact='unknown')


def draw_comparison(raw,result,out):
    overlay=raw.copy();full=raw.copy();roi=raw.copy()
    for row in result['point_errors']:
        target=tuple(np.rint(row['human_pixel']).astype(int));pred=tuple(np.rint(row['full_observed_pixel']).astype(int))
        for canvas in [overlay,full]:
            cv2.line(canvas,target,pred,(0,120,255),1)
            cv2.circle(canvas,pred,4,(0,120,255),1)
        for canvas in [overlay,full,roi]:
            cv2.drawMarker(canvas,target,(0,255,0),cv2.MARKER_CROSS,12,2)
            cv2.putText(canvas,str(row['index']),target,cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,0),1)
        if row['roi_observed_pixel'] is not None:
            p=tuple(np.rint(row['roi_observed_pixel']).astype(int))
            for canvas in [overlay,roi]:
                cv2.line(canvas,target,p,(255,0,255),1);cv2.circle(canvas,p,4,(255,0,255),1)
    cv2.putText(overlay,'Kim=green cross; full=orange; ROI=magenta; raw coordinates unchanged',(5,20),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,255,0),1)
    cv2.imwrite(str(out/'frame120_comparison_original.png'),overlay)
    cv2.imwrite(str(out/'frame120_full_error_crop.png'),cv2.resize(full[160:380,880:1080],None,fx=3,fy=3))
    cv2.imwrite(str(out/'frame120_roi_error_crop.png'),cv2.resize(roi[160:380,880:1080],None,fx=3,fy=3))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--review',type=Path,default=Path('dataset/hand_analysis/human_review_20261103/validated_review.json'))
    parser.add_argument('--observations',type=Path,default=Path('dataset/hand_analysis/runs/clip_003_012_20261103_v1/observations.jsonl'))
    args=parser.parse_args()
    if (args.output/'evaluation.json').exists():raise FileExistsError('Preserve old evaluation; choose another --output')
    args.output.mkdir(parents=True,exist_ok=True)
    matching=[r for r in json.loads(args.review.read_text())['reviews'] if r['frame_index']==120]
    if len(matching)!=1:raise ValueError('Exactly one frame120 review is required for this frozen evaluation')
    review=matching[0]
    obs=next(json.loads(line) for line in args.observations.read_text().splitlines() if json.loads(line)['frame_index']==review['frame_index'])
    image_path=Path('dataset/chord_video_review/case_0005.00.png')
    validate_identity(review,obs,image_path)
    result=evaluate(review,obs)
    result.update(source_id=review['source_id'],frame_index=review['frame_index'],frame_pts_s=review['frame_pts_s'],
        reviewer=review['reviewer'],model_blind_declared=review['model_blind'],
        review_source_path=str(args.review),review_source_sha256=file_sha256(args.review),
        observation_source_path=str(args.observations),observation_source_sha256=file_sha256(args.observations),
        regression_sha256=file_sha256('dataset/regression/csharp_m7_wrong_center.json'),
        human_review_scope='visible joint/pad center coordinates only; no contact, wrist, or whole-hand identity truth',api_calls=0)
    semantic_path=Path('dataset/fretboard_review/human_semantic_review_frame120_20261103.json')
    if semantic_path.exists():
        semantic=json.loads(semantic_path.read_text())
        result['separate_board_semantic_reference']=dict(path=str(semantic_path),sha256=file_sha256(semantic_path),
            confirmations=semantic['confirmations'],independent_blind_annotation=False,
            exact_pixel_ground_truth=False,used_to_adjust_model_or_gate=False,
            contact='unknown',precise_fret_decision=None)
    (args.output/'evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    draw_comparison(cv2.imread(str(image_path)),result,args.output)
    print(result['association']);print(result['full_error']);print(result['current_fingertip_gate'])


if __name__=='__main__':main()
