"""Extract still tutorial cases and manually inspected board fixtures, no APIs."""
import json
from pathlib import Path

import cv2
import numpy as np

from hand_fret_tracker import FretboardGeometry, analyze_result, detect_image, render

OUT = Path('dataset/chord_video_review')
# Source code names are tutorial SHAPES with Capo.1, not concert pitch labels.
CASES = [(5., 'G', 'open'), (94.35, 'A', 'open'), (194.86, 'F#', 'barre'),
         (217.20, 'C#m7', 'barre'), (239.54, 'E', 'open'), (206.03, None, 'transition')]


def main():
    video = next(Path('sample video').glob('*.mp4'))
    cap = cv2.VideoCapture(str(video))
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for time, chord, kind in CASES:
        cap.set(cv2.CAP_PROP_POS_MSEC, time*1000)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError('Frame extraction failed')
        index = int(cap.get(cv2.CAP_PROP_POS_FRAMES))-1
        name = f'case_{time:07.2f}'
        image_path = OUT / f'{name}.png'
        cv2.imwrite(str(image_path), frame)
        # Independent visual approximation from source frames, NOT a detector benchmark GT.
        corners = [[1114., 208.], [430., 204.], [430., 286.], [1114., 275.]]
        board = FretboardGeometry(corners, [])
        # Only identifiable lines are supplied; no invented fixed 12-TET spacing.
        # Capo is INSIDE physical cell 1, not itself a fret wire.
        endpoints = {0: [1114, 1114], 1: [1057, 1057], 2: [1003, 1005],
                     3: [953, 956], 4: [906, 910], 5: [863, 867], 6: [822, 826],
                     7: [784, 788], 8: [748, 753], 9: [713, 718], 10: [681, 686]}
        frets = []
        for n, (top, bottom) in endpoints.items():
            flat = project_points([[top, 210], [bottom, 273]], board.M)
            m = float((flat[1, 0]-flat[0, 0])/(flat[1, 1]-flat[0, 1]))
            b = float(flat[0, 0]-m*flat[0, 1])
            if n == 0:
                m, b = 0., 0.
            frets.append(dict(fret_num=n, m=m, b=b, xt=b, xb=m*150+b,
                              source='observed', detection_method='agent_manual_visual_approximation',
                              numbering_status='provisional_count_from_nut',
                              original_endpoints=[[top, 210], [bottom, 273]]))
        board_path = OUT / f'{name}_board.json'
        cached = dict(raw_image=str(image_path), corners=corners, frets=frets,
                      canvas_size=[800, 150], source='agent_manual_visual_approximation',
                      note='New per-frame manual fixture, not reused from unrelated photos; requires human review',
                      capo_physical_fret=1, api_calls=0)
        board_path.write_text(json.dumps(cached, indent=2), encoding='utf-8')
        board = FretboardGeometry(corners, frets)
        detection = detect_image(frame, 'hand_landmarker.task')
        result = analyze_result(detection, frame.shape, board)
        result.update(image=str(image_path), board_result=str(board_path),
                      image_size=[frame.shape[1], frame.shape[0]], canvas_size=[800, 150],
                      M=board.M.tolist(), M_inv=board.M_inv.tolist(), frets=frets,
                      frame_index=index, timestamp_ms=index/24*1000, capo_physical_fret=1,
                      chord_shape_reference=chord, chord_type_reference=kind,
                      reference_status='agent_visual_reading_of_tutorial_not_contact_ground_truth')
        track_path = OUT / f'{name}_tracking.json'
        track_path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
        original, flat = render(frame, board, result)
        cv2.imwrite(str(OUT / f'{name}_skeleton_original.png'), original)
        cv2.imwrite(str(OUT / f'{name}_skeleton_flat.png'), flat)
        manifest.append(dict(case_id=name, video=str(video), frame_index=index,
                             timestamp_seconds=index/24, chord_shape=chord, chord_type=kind,
                             capo=1, selection_status=result['status'], hands=len(result['hands']),
                             tracking_json=str(track_path), board_json=str(board_path),
                             labels_status='pending_independent_review'))
        print(name, chord, kind, result['status'], len(result['hands']))
    cap.release()
    (OUT / 'cases.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def project_points(points, matrix):
    return cv2.perspectiveTransform(np.array(points, np.float64)[:, None], matrix)[:, 0]


if __name__ == '__main__':
    main()
