"""Conservative location gates; retain observations but abstain from decisions."""
import numpy as np


def location_gate(full_hand, roi_hands, tip, radius=6., previous=None, timestamp_ms=None):
    point = np.array(full_hand['landmarks'][tip]['pixel'], float)
    reasons = []
    roi_point = None
    if len(roi_hands) != 1:
        reasons.append('secondary_view_missing' if not roi_hands else 'secondary_view_ambiguous')
    else:
        roi_point = np.array(roi_hands[0]['landmarks'][tip]['pixel'], float)
        if np.linalg.norm(point-roi_point) > radius:
            reasons.append('cross_view_disagreement')
    velocity = None
    if previous is not None and timestamp_ms is not None:
        dt = timestamp_ms-previous['timestamp_ms']
        if dt <= 0:
            raise ValueError('Timestamps must increase')
        velocity = float(np.linalg.norm(point-previous['pixel'])/(dt/1000))
        if velocity > 180:
            reasons.append('rapid_landmark_change')
    # MediaPipe has no measured per-point visibility here; agreement is NOT visibility GT.
    return dict(decision='abstain' if reasons else 'candidate_only', reasons=reasons,
                full_pixel=point.tolist(), secondary_pixel=None if roi_point is None else roi_point.tolist(),
                cross_view_distance_px=None if roi_point is None else float(np.linalg.norm(point-roi_point)),
                speed_px_per_second=velocity, contact='unknown',
                visibility='unverified', occlusion_state='suspected_or_detection_failure' if 'secondary_view_missing' in reasons else 'unverified',
                calibration_status='not_independently_validated', agreement_threshold_px=radius)


def reviewed_gate(gate, label_pixel, radius=6.):
    result = dict(gate)
    error = float(np.linalg.norm(np.array(gate['full_pixel'])-label_pixel))
    result['review_error_px'] = error
    if error > radius:
        result['decision'] = 'abstain'
        result['reasons'] = list(gate['reasons']) + ['reviewed_center_disagreement']
    return result
