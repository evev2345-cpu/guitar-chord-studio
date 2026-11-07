"""Video/frame identity contract and explicit legacy conversion, no API."""
import hashlib
import math
import re
from pathlib import Path


def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def is_sha256(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def make_frame_identity(source_id,frame_index,frame_pts_s,bgr,image_file,case_id):
    if not is_sha256(source_id):raise ValueError('source_id must be original video SHA-256')
    if type(frame_index) is not int or frame_index<0:raise ValueError('Invalid frame_index')
    return dict(source_id=source_id,case_id=case_id,frame_index=frame_index,
        frame_pts_s=float(frame_pts_s),frame_pixel_sha256=hashlib.sha256(bgr.tobytes()).hexdigest(),
        frame_pixel_hash_basis='decoded contiguous BGR uint8, C order; OpenCV video decode / FFmpeg bt601 bilinear equivalent',
        image_file_sha256=sha256_file(image_file),image_file=str(Path(image_file).resolve()),
        image_size=[int(bgr.shape[1]),int(bgr.shape[0])])


def attach_frame_identity(result,identity):
    if not is_sha256(identity.get('source_id')):raise ValueError('Missing canonical video source_id')
    result=dict(result)
    old=result.get('source_id')
    old_case=result.get('case_id') or (old if old and not is_sha256(old) else None)
    if old and old!=identity['source_id']:
        if is_sha256(old):raise ValueError('Different source video; cannot merge')
        result['legacy_source_id']=old
    previous_pixel=result.get('frame_pixel_sha256',result.get('image_sha256'))
    if previous_pixel and previous_pixel!=identity['frame_pixel_sha256']:
        raise ValueError('Different decoded frame pixels; cannot merge')
    for key in ['frame_index','frame_pts_s']:
        equal = (math.isclose(float(result[key]),float(identity[key]),abs_tol=5e-7,rel_tol=0) if key=='frame_pts_s' and result.get(key) is not None else result.get(key)==identity[key])
        if result.get(key) is not None and not equal:
            raise ValueError('Conflicting '+key)
    result.update(identity)
    if old_case and old_case!=identity.get('case_id'):
        result['case_id']=old_case
        result['canonical_case_id']=identity.get('case_id')
    # Legacy alias retained with an explicit meaning; never use as file hash.
    result['image_sha256']=identity['frame_pixel_sha256']
    result['identity_schema']='guitar_video_frame.v1'
    return result


def assert_same_frame(a,b):
    for key in ['source_id','frame_index','frame_pixel_sha256']:
        if a.get(key) is None or a.get(key)!=b.get(key):raise ValueError('Frame mismatch: '+key)
    if a.get('frame_pts_s') is None or b.get('frame_pts_s') is None or not math.isclose(float(a['frame_pts_s']),float(b['frame_pts_s']),abs_tol=5e-7,rel_tol=0):raise ValueError('Frame mismatch: frame_pts_s')
    return True
