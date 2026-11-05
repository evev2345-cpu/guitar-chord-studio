"""Branch-scoped anatomical identity review sidecar; never repairs raw landmarks."""
import copy
import hashlib
import json

IDENTITY = ('source_id', 'frame_index', 'frame_pts_s', 'frame_pixel_sha256')

def skeleton_hash(points):
    if len(points) != 21 or any(len(p) != 2 for p in points):
        raise ValueError('Expected one original-pixel 21-point hand')
    return hashlib.sha256(json.dumps(points, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def same_frame(a, b):
    return all(abs(a[k]-b[k]) < 1e-6 if k == 'frame_pts_s' else a[k] == b[k] for k in IDENTITY)

def resolve_medoid(frame, tip):
    """medoid index belongs to filtered single-hand views, not the views array."""
    decision = frame['tip_decisions'][str(tip)]
    views = [v for v in frame['views'] if len(v['hands']) == 1]
    index = decision.get('medoid_view_index')
    if not isinstance(index, int) or not 0 <= index < len(views):
        raise ValueError('Unresolved medoid lineage')
    view = views[index]
    points = view['hands'][0]
    if points[tip] != decision['selected_pixel']:
        raise ValueError('Medoid coordinate does not match claimed raw hand')
    return dict(view_id=view['view_id'], bounds=view['bounds'], hand_index=0,
                skeleton_sha256=skeleton_hash(points), raw_points=copy.deepcopy(points))

def anatomical_validity(identity, lineage, landmark_indices, binding):
    exact = same_frame(identity, binding) and all(lineage.get(k) == binding['lineage'][k]
            for k in ('view_id', 'bounds', 'hand_index', 'skeleton_sha256'))
    affected = exact and any(i in range(9, 21) for i in landmark_indices)
    return dict(schema_version='hand_anatomical_validity.v1',
        status='invalid' if affected else 'unknown',
        reason='human_reviewed_chain_identity_error' if affected else 'anatomical_identity_not_verified',
        human_review_applied=exact, review_path=binding['review_path'] if exact else None,
        lineage=copy.deepcopy(lineage), landmark_indices=list(landmark_indices),
        anatomical_fingering_evidence_allowed=False,
        raw_observation_preserved=True, automatic_relabeling=False,
        anatomical_recovery='not_completed', contact='unknown', sounding='unknown')

def apply_validity(distribution, validity):
    """Independent hard gate: spatial mass/audio weights cannot undo this flag."""
    result = copy.deepcopy(distribution)
    result['anatomical_validity'] = copy.deepcopy(validity)
    result['anatomical_fingering_evidence_allowed'] = False
    result['decision'] = 'abstain'
    result['confirmed_cell'] = None
    result['contact'] = result['sounding'] = 'unknown'
    result['reasons'] = list(dict.fromkeys(result.get('reasons', []) + [validity['reason']]))
    for cell in result.get('cells', []):
        cell['anatomical_fingering_evidence_allowed'] = False
        cell['anatomical_validity_status'] = validity['status']
    return result
