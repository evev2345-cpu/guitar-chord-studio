"""Offline still-image hand candidates using resolved pipeline geometry.

No BAZE imports/calls. Hand indices are local to one image, not tracking IDs.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

TIPS = {8: 'index', 12: 'middle', 16: 'ring', 20: 'pinky'}
EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6),
         (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
         (9, 13), (13, 14), (14, 15), (15, 16), (13, 17),
         (0, 17), (17, 18), (18, 19), (19, 20)]


def project(points, matrix):
    points = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    homogeneous = np.column_stack((points, np.ones(len(points)))) @ matrix.T
    valid = np.isfinite(homogeneous).all(axis=1) & (abs(homogeneous[:, 2]) > 1e-9)
    output = np.full((len(points), 2), np.nan)
    output[valid] = homogeneous[valid, :2] / homogeneous[valid, 2:]
    # Same pixel transform as cv2.perspectiveTransform, with explicit pole handling.
    if valid.any():
        output[valid] = cv2.perspectiveTransform(points[valid, None, :], matrix)[:, 0]
    return output


class FretboardGeometry:
    def __init__(self, corners, frets, width=800, height=150):
        self.width, self.height = int(width), int(height)
        polygon = np.asarray(corners, np.float32)
        if (self.width <= 0 or self.height <= 0 or polygon.shape != (4, 2)
                or not np.isfinite(polygon).all() or not cv2.isContourConvex(polygon)
                or abs(cv2.contourArea(polygon)) < 10):
            raise ValueError('Invalid board corners or canvas')
        self.M = cv2.getPerspectiveTransform(polygon, np.float32(
            [[0, 0], [width, 0], [width, height], [0, height]]))
        self.M_inv = np.linalg.inv(self.M)
        self.frets = frets  # Preserve all evidence and unresolved records verbatim.
        self.wires = {}
        for wire in frets:
            n = wire['fret_num']
            if type(n) is not int or n < 0 or n in self.wires:
                raise ValueError('Invalid/duplicate physical fret number')
            self.wires[n] = wire
            if 'm' in wire or 'b' in wire:
                values = [wire['m'], wire['b'], wire['m'] * height + wire['b']]
                # Float32 homography round trips can place boundary lines ~1e-4px
                # outside the canvas. Accept numerical noise without moving geometry.
                if not np.isfinite(values).all() or not all(-1e-3 <= x <= width+1e-3 for x in values[1:]):
                    raise ValueError('Invalid resolved wire geometry')
        resolved = sorted(n for n, r in self.wires.items() if 'm' in r and 'b' in r)
        for a, b in zip(resolved, resolved[1:]):
            if any(self.x(a, y) >= self.x(b, y) for y in (0, height)):
                raise ValueError('Crossed/reversed resolved wires')

    @classmethod
    def from_pipeline(cls, pipeline):
        geometry = cls(pipeline.corners, pipeline.fret_records,
                       pipeline.canvas_w, pipeline.canvas_h)
        geometry.M = np.asarray(pipeline.M, dtype=float).copy()
        geometry.M_inv = np.asarray(pipeline.M_inv, dtype=float).copy()
        return geometry

    def x(self, n, y):
        wire = self.wires[n]
        return wire['m'] * y + wire['b']

    def candidate(self, point, estimate_strings=False):
        x, y = point
        if not np.isfinite(point).all():
            return dict(status='invalid_projection')
        if not (0 <= x < self.width and 0 <= y < self.height):
            return dict(status='outside_board')
        for n, right in sorted(self.wires.items()):
            left = self.wires.get(n - 1, {})
            if not all('m' in r and 'b' in r for r in (left, right)):
                continue
            if self.x(n - 1, y) <= x < self.x(n, y):
                result = dict(status='fingering_candidate', fret_num=n,
                              boundary_wires=[left, right], contact_confirmed=False)
                if estimate_strings:
                    result.update(string_estimate=6 - min(5, int(y / self.height * 6)),
                                  string_method='temporary_uniform_six_bands')
                return result
        return dict(status='unresolved_fret_geometry')


def analyze_result(detection, image_shape, board, player='right', mirrored='unknown',
                   estimate_strings=False):
    h, w = image_shape[:2]
    hands = []
    for i, landmarks in enumerate(detection.hand_landmarks):
        pixels = np.array([[lm.x * w, lm.y * h] for lm in landmarks])
        flat = project(pixels, board.M)
        categories = detection.handedness[i] if i < len(detection.handedness) else []
        label = categories[0].category_name if categories else None
        confidence = float(categories[0].score) if categories else 0.
        # MediaPipe convention assumes selfie-mirrored input. Unknown => no prior.
        anatomical = label if mirrored == 'yes' else (
            {'Left': 'Right', 'Right': 'Left'}.get(label) if mirrored == 'no' else None)
        desired = 'Left' if player == 'right' else 'Right'
        dx = np.maximum(np.maximum(-flat[:, 0], flat[:, 0] - board.width), 0) / board.width
        dy = np.maximum(np.maximum(-flat[:, 1], flat[:, 1] - board.height), 0) / board.height
        distances = np.hypot(dx, dy)
        tip_distance = float(np.median(distances[list(TIPS)]))
        near = np.isfinite(tip_distance) and tip_distance <= .75
        spatial = 1 / (1 + tip_distance) if near else 0.
        score = spatial + (.15 * confidence if anatomical == desired else 0.)
        records = [dict(index=j, normalized=[lm.x, lm.y, lm.z],
                        pixel=pixels[j].tolist(),
                        flat=flat[j].tolist() if np.isfinite(flat[j]).all() else None)
                   for j, lm in enumerate(landmarks)]
        hands.append(dict(hand_index=i, handedness_raw=label, handedness_score=confidence,
                          anatomical_handedness=anatomical, selection_score=score,
                          near_board=bool(near), landmarks=records, candidates=[]))
    ranked = sorted((hand for hand in hands if hand['near_board']),
                    key=lambda hand: hand['selection_score'], reverse=True)
    status, selected = 'no_hands' if not hands else 'no_hand_near_board', None
    if ranked:
        if len(ranked) > 1 and ranked[0]['selection_score'] - ranked[1]['selection_score'] < .12:
            status = 'ambiguous_hand_selection'
        else:
            selected, status = ranked[0]['hand_index'], 'selected'
            for tip, name in TIPS.items():
                landmark = hands[selected]['landmarks'][tip]
                candidate = board.candidate(landmark['flat'] or [np.nan, np.nan], estimate_strings)
                hands[selected]['candidates'].append(dict(finger=name, landmark_index=tip, **candidate))
    return dict(status=status, selected_hand_index=selected, hands=hands,
                config=dict(player=player, mirrored=mirrored, estimate_strings=estimate_strings),
                interpretation='Fingering candidates only; no string contact or TAB confirmed',
                limitations=['off-plane projection error', 'physical fret numbering unverified',
                             'no actual string detection', 'fingertips do not represent barre contact'])


def detect_image(image, model_path):
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)), num_hands=2,
        running_mode=vision.RunningMode.IMAGE)
    with vision.HandLandmarker.create_from_options(options) as detector:
        return detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                        data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))


def render(image, board, result):
    original = image.copy()
    flat = cv2.warpPerspective(image, board.M, (board.width, board.height))
    colors = {'observed': (0, 220, 0), 'interpolated': (255, 255, 0),
              'boundary_estimated': (255, 0, 255)}
    for wire in board.frets:
        if 'm' not in wire or 'b' not in wire:
            continue
        pts = np.array([[wire['b'], 0], [wire['m'] * board.height + wire['b'], board.height]])
        color = colors.get(wire.get('source'), (140, 140, 140))
        for canvas, points in ((flat, pts), (original, project(pts, board.M_inv))):
            cv2.line(canvas, tuple(np.rint(points[0]).astype(int)),
                     tuple(np.rint(points[1]).astype(int)), color, 1)
    for hand in result['hands']:
        color = (0, 180, 255) if hand['hand_index'] == result['selected_hand_index'] else (150, 150, 150)
        for canvas, key in ((original, 'pixel'), (flat, 'flat')):
            points = [lm[key] for lm in hand['landmarks']]
            for a, b in EDGES:
                if points[a] is not None and points[b] is not None:
                    # Clip before integer conversion; projected off-plane points can be huge.
                    ends = [tuple(np.rint(np.clip(points[j], -100000, 100000)).astype(int)) for j in (a, b)]
                    ok, p, q = cv2.clipLine((0, 0, canvas.shape[1], canvas.shape[0]), *ends)
                    if ok:
                        cv2.line(canvas, p, q, color, 1)
            for candidate in hand['candidates']:
                point = points[candidate['landmark_index']]
                if point is None or not (0 <= point[0] < canvas.shape[1] and 0 <= point[1] < canvas.shape[0]):
                    continue
                p = tuple(np.rint(point).astype(int))
                cv2.circle(canvas, p, 4, color, -1)
                label = candidate['finger'] + ':' + str(candidate.get('fret_num', candidate['status']))
                cv2.putText(canvas, label, (p[0] + 4, p[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, .35, color, 1)
    for canvas in (original, flat):
        cv2.putText(canvas, 'CANDIDATES ONLY / ' + result['status'], (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, .35, (0, 0, 255), 1)
    return original, flat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board-result', required=True, help='Resolved pipeline *_result.json')
    parser.add_argument('--image', help='Override raw_image path (must be the same frame)')
    parser.add_argument('--canvas-width', type=int, default=800)
    parser.add_argument('--canvas-height', type=int, default=150)
    parser.add_argument('--model', default=str(Path(__file__).with_name('hand_landmarker.task')))
    parser.add_argument('--player', choices=['right', 'left'], default='right')
    parser.add_argument('--mirrored', choices=['yes', 'no', 'unknown'], default='unknown')
    parser.add_argument('--estimate-strings', action='store_true')
    parser.add_argument('--out-prefix', default='sample_images/hand_tracking/result')
    args = parser.parse_args()
    cached = json.loads(Path(args.board_result).read_text(encoding='utf-8'))
    image_path = args.image or cached['raw_image']
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(image_path)
    board = FretboardGeometry(cached['corners'], cached['frets'], args.canvas_width, args.canvas_height)
    result = analyze_result(detect_image(image, args.model), image.shape, board,
                            args.player, args.mirrored, args.estimate_strings)
    result.update(image=str(image_path), board_result=args.board_result,
                  image_size=[image.shape[1], image.shape[0]],
                  canvas_size=[board.width, board.height], M=board.M.tolist(),
                  M_inv=board.M_inv.tolist(), frets=board.frets)
    original, flat = render(image, board, result)
    prefix = Path(args.out_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    for suffix, canvas in (('_original.png', original), ('_flat.png', flat)):
        if not cv2.imwrite(str(prefix) + suffix, canvas):
            raise OSError('Failed to save visualization')
    Path(str(prefix) + '.json').write_text(json.dumps(result, indent=2, ensure_ascii=False,
                                                    allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(status=result['status'], hands=len(result['hands']), output=str(prefix))))


if __name__ == '__main__':
    main()
