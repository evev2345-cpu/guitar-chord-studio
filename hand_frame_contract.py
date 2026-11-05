"""Hand-owned adapter for source/frame/PTS and upstream geometry validity."""
import hashlib
import math
from fractions import Fraction
from pathlib import Path


def file_sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def frame_identity(source_id, frame_index, probe_frame, time_base, raw, image_file=None):
    pts=probe_frame.get('pts',probe_frame.get('best_effort_timestamp'))
    if pts is None:
        raise ValueError('Actual video PTS is required; FPS-derived times are not accepted')
    seconds=float(int(pts)*Fraction(time_base))
    return dict(source_id=source_id,case_id=f'frame_{frame_index:06d}',frame_index=frame_index,
                frame_pts=int(pts),frame_time_base=time_base,frame_pts_s=seconds,
                frame_pixel_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),
                pixel_hash_basis='decoded_uint8_BGR_contiguous_row_major',
                image_file_sha256=file_sha256(image_file) if image_file else None,
                image_file=str(image_file) if image_file else None,
                image_size=[raw.shape[1],raw.shape[0]])


def adapt_geometry(frame, upstream):
    """Never turn small motion or absent validity into verified geometry."""
    if upstream is None:
        return dict(status='unknown',source_kind='unknown',reason='awaiting_upstream_same_frame_geometry',
                    precise_fret_decision=None,contact='unknown')
    for key in ('source_id','frame_index','frame_pixel_sha256'):
        if upstream.get(key)!=frame.get(key):
            raise ValueError('Geometry frame identity mismatch: '+key)
    pts=upstream.get('frame_pts_s')
    if pts is None or not math.isfinite(pts) or abs(pts-frame['frame_pts_s'])>1e-6:
        raise ValueError('Geometry PTS mismatch')
    validity=upstream.get('geometry_validity',{})
    if isinstance(validity,str):validity=dict(status=validity)
    status=validity.get('status','unknown')
    if status not in ('valid','suspect','unknown','invalid'):
        raise ValueError('Unrecognized upstream geometry validity')
    source_kind=upstream.get('geometry_source_kind','unknown')
    if source_kind=='unknown' and 'manual' in upstream.get('source',''):
        source_kind='manual_approximation'
    return dict(status=status,source_kind=source_kind,upstream_validity=validity,
                evidence=upstream,precise_fret_decision=None,contact='unknown',
                contact_fret_decision_allowed=bool(validity.get('contact_fret_decision_allowed',False)),
                reason='geometry_allows_location_candidates_only' if status=='valid' else 'upstream_geometry_not_valid')


def apply_geometry_gate(location, geometry):
    result=dict(location,reasons=list(location['reasons']))
    if geometry['status']!='valid':
        result['decision']='abstain'
        result['reasons'].append('upstream_geometry_'+geometry['status'])
    elif not geometry.get('contact_fret_decision_allowed',False):
        result['decision']='abstain'
        result['reasons'].append('upstream_exact_fret_permission_missing')
    result['contact']='unknown'
    result['precise_fret_decision']=None
    return result
