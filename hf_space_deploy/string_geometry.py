"""Native-image warping and explicit common-coordinate metadata, no API."""
import hashlib
import cv2
import numpy as np
from string_detector import detect_strings


def analyze_saved_board(raw,board,source_id=None,high_resolution=True):
    canonical_w,canonical_h=board.get('canvas_size',[800,150])
    src=np.asarray(board['corners'],np.float32)
    length=max(np.linalg.norm(src[1]-src[0]),np.linalg.norm(src[2]-src[3]))
    native_width=max(np.linalg.norm(src[3]-src[0]),np.linalg.norm(src[2]-src[1]))
    dw=max(canonical_w,min(4096,int(np.ceil(length*2)))) if high_resolution else canonical_w
    dh=max(300,min(1024,int(np.ceil(native_width*2)))) if high_resolution else canonical_h
    sx,sy=dw/canonical_w,dh/canonical_h
    target=np.array([[0,0],[canonical_w,0],[canonical_w,canonical_h],[0,canonical_h]],np.float32)
    matrix=cv2.getPerspectiveTransform(src,target)
    inverse=np.linalg.inv(matrix)
    detector_matrix=np.diag([sx,sy,1.])@matrix
    image=cv2.warpPerspective(raw,detector_matrix,(dw,dh))
    common=cv2.warpPerspective(raw,matrix,(canonical_w,canonical_h))
    frets=board.get('frets',[])
    scaled=[dict(f,xt=f['xt']*sx,xb=f['xb']*sx) for f in frets if 'xt' in f]
    sides=board.get('physical_order','low_e_top')
    detected=detect_strings(image,scaled,float(native_width),physical_order=sides)
    for s in detected['strings']:
        s['m']*=sx/sy;s['b']/=sy
        s['y_left']=s['b'];s['y_right']=s['m']*(canonical_w-1)+s['b']
        s['model']=dict(type='line',equation='y=m*x+b',m=s['m'],b=s['b'],domain_x=[0,canonical_w-1])
        s['observed_intervals']=[[a/sx,b/sx] for a,b in s['observed_intervals']]
    detected.update(width=canonical_w,height=canonical_h,canvas_size=[canonical_w,canonical_h],
        detection_canvas_size=[dw,dh],source_id=source_id,
        image_size=[raw.shape[1],raw.shape[0]],image_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),image_hash_basis='decoded_BGR_uint8_bytes',
        native_end_widths_px=[float(np.linalg.norm(src[3]-src[0])),float(np.linalg.norm(src[2]-src[1]))],
        M=matrix.tolist(),M_inv=inverse.tolist(),M_detection=detector_matrix.tolist(),
        detection_to_common=np.diag([1/sx,1/sy,1.]).tolist(),
        corners=src.tolist(),frets=frets,
        geometry_source=board.get('source','saved_fretboard_result'),
        physical_mapping_provenance=board.get('physical_mapping_provenance','named corner convention: nut_top/body_top low-E side; verify on mirrored inputs'),
        source_metadata=board.get('source_metadata',{}),api_calls=0,
        native_long_edge_px=float(length),native_short_edge_px=float(native_width),
        common_canvas_downsamples_native=[bool(length>canonical_w),bool(native_width>canonical_h)])
    if board.get('frame_identity'):
        from fretboard_frame_identity import attach_frame_identity
        detected=attach_frame_identity(detected,board['frame_identity'])
    return detected,common,image,matrix,inverse
