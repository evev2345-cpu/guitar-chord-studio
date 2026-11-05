"""Validate model-blind human review JSON without inventing hidden coordinates."""
import argparse
import json
from pathlib import Path
import numpy as np


def validate_review(reviews,queue):
    cases={c['case_id']:c for c in queue['cases']}
    output=[];visible=0;marked=0
    for review in reviews:
        if review.get('review_status')!='reviewed':continue
        source=cases[review['case_id']]
        if not review.get('model_blind') or not str(review.get('reviewer','')).strip():
            raise ValueError('Named model-blind reviewer required')
        if 'agent' in review['reviewer'].lower():
            raise ValueError('Agent references cannot be imported as independent human labels')
        for key in ['source_id','frame_index','frame_pixel_sha256','image_file_sha256']:
            if review.get(key)!=source.get(key):raise ValueError('Review identity mismatch: '+key)
        if abs(review['frame_pts_s']-source['frame_pts_s'])>1e-6:raise ValueError('Review PTS mismatch')
        seen=set();points=[]
        for point in review.get('landmarks',[]):
            index=point['index']
            if index not in queue['required_landmark_indices']:continue
            if index in seen:raise ValueError('Duplicate landmark index')
            seen.add(index)
            state=point['visibility']
            if state=='unreviewed':continue
            if state not in ['visible','hidden','unknown']:raise ValueError('Invalid visibility')
            pixel=point.get('pixel')
            if state=='visible':
                p=np.asarray(pixel,float)
                if p.shape!=(2,) or not np.isfinite(p).all() or not(0<=p[0]<source['image_size'][0] and 0<=p[1]<source['image_size'][1]):
                    raise ValueError('Invalid visible point')
                visible+=1
            elif pixel is not None:raise ValueError('Hidden/unknown points must have null coordinates')
            points.append(point);marked+=1
        output.append(dict(review,landmarks=points,review_provenance='user_declared_human_model_blind'))
    return dict(reviews=output,visible_points=visible,reviewed_items=marked,
                truth_status='human_declared_not_contact_ground_truth',contact='unknown')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-json',type=Path,required=True)
    parser.add_argument('--queue',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=validate_review(json.loads(args.review_json.read_text()),json.loads(args.queue.read_text()))
    if args.output.exists():raise FileExistsError('Preserve previous review; choose a new output')
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
