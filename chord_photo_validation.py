"""Offline chord-photo review: cached hands/boards, distributions, no API calls.

No chord/contact classifier or string detector is implemented here.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from fingertip_probability import circle_distribution, COLORS
from hand_fret_tracker import EDGES, project

FINGERS = {'thumb': 4, 'index': 8, 'middle': 12, 'ring': 16, 'pinky': 20}


def probability_candidates(distribution, frets, canvas_size, samples=65536):
    """Integrate local Gaussian by repeatable Monte Carlo; no board conditioning."""
    if distribution['status'] != 'ok':
        return dict(status=distribution['status'], candidates=[], unassigned_probability=1.)
    generator = np.random.default_rng(20261102)
    points = generator.standard_normal((samples, 2)) @ np.linalg.cholesky(
        distribution['flat_covariance']).T + distribution['flat_mean']
    x, y = points.T
    width, height = canvas_size
    inside = (x >= 0) & (x < width) & (y >= 0) & (y < height)
    allocated = np.zeros(samples, bool)
    wires = {r['fret_num']: r for r in frets if 'm' in r and 'b' in r}
    candidates = []
    for n, right in sorted(wires.items()):
        left = wires.get(n-1)
        if left is None:
            continue
        mask = inside & (x >= left['m']*y+left['b']) & (x < right['m']*y+right['b'])
        if np.any(mask & allocated):
            raise ValueError('Overlapping fret geometry; cannot allocate probability')
        allocated |= mask
        probability = float(mask.mean())
        candidates.append(dict(fret_num=n, probability=probability,
                               monte_carlo_standard_error=float(np.sqrt(probability*(1-probability)/samples)),
                               boundary_wires=[left, right], numbering_status='unverified'))
    return dict(status='ok', candidates=sorted(candidates, key=lambda c: -c['probability']),
                outside_board_probability=float((~inside).mean()),
                unresolved_geometry_probability=float((inside & ~allocated).mean()),
                unassigned_probability=float((~allocated).mean()), samples=samples,
                integration='seeded_monte_carlo_local_gaussian', contact='unknown')


def string_interface(payload, tracking):
    """Accept existing detect_strings_offline JSON only for the identical board."""
    if payload is None:
        return dict(status='not_provided', strings=[], contact='unknown')
    expected = Path(tracking['board_result']).resolve()
    supplied = payload.get('input_geometry')
    if 'image_sha256' in payload:
        image = cv2.imread(tracking['image'])
        if image is None or hashlib.sha256(image.tobytes()).hexdigest() != payload['image_sha256']:
            raise ValueError('String image pixels do not match hand frame')
        if payload.get('image_size') != tracking['image_size']:
            raise ValueError('String source image size mismatch')
        for key in ('M', 'M_inv'):
            actual = np.asarray(payload.get(key), float)
            target = np.asarray(tracking[key], float)
            if actual.shape != (3, 3) or not np.isfinite(actual).all() or not np.allclose(actual, target, rtol=1e-7, atol=1e-7):
                raise ValueError('String homography mismatch')
        identity = 'decoded_bgr_pixel_sha256_and_homography'
    elif supplied is None or Path(supplied).resolve() != expected:
        raise ValueError('String input_geometry must match cached hand board_result')
    else:
        identity = 'legacy_path_only_not_pixel_verified'
    if tracking['canvas_size'] != payload.get('canvas_size', [800, 150]):
        raise ValueError('String canvas must match tracking canvas (legacy strings assume 800x150)')
    numbers = set()
    for line in payload.get('strings', []):
        number = line.get('string_num')
        if number is not None and (type(number) is not int or not 1 <= number <= 6 or number in numbers):
            raise ValueError('Invalid or duplicate string number')
        if number is not None:
            numbers.add(number)
        if not np.isfinite([line['m'], line['b']]).all():
            raise ValueError('Invalid string coordinates')
        if line.get('source') not in ('observed', 'estimated'):
            raise ValueError('String source must distinguish observed and estimated')
    # Preserve partial/missing evidence, never manufacture uniform six-string lines.
    result = dict(payload)
    result.update(coordinate_system='flat_pixels_y=m*x+b', canvas_size=tracking['canvas_size'],
                  identity_verification=identity, contact='unknown')
    return result


def calibrate(labels, tracks):
    """Reviewed image point labels only; provenance stays explicit."""
    errors = []
    cases = set()
    reviewers = set()
    for annotation in labels:
        if annotation.get('review_status') != 'reviewed':
            continue
        track = tracks[annotation['case_id']]
        hand_id = annotation.get('fretting_hand_index')
        if hand_id is None:
            continue
        hand = next(h for h in track['hands'] if h['hand_index'] == hand_id)
        reviewers.add(annotation.get('reviewer', 'unspecified'))
        for label in annotation.get('landmarks', []):
            if label.get('visibility') != 'visible' or label.get('pixel') is None:
                continue
            target = np.asarray(label['pixel'], float)
            if target.shape != (2,) or not np.isfinite(target).all():
                raise ValueError('Invalid human point label')
            predicted = hand['landmarks'][label['index']]['pixel']
            errors.append(float(np.linalg.norm(target-predicted)))
            cases.add(annotation['case_id'])
    if not errors:
        return dict(status='awaiting_human_landmark_labels', default_radius_px=6,
                    calibration_count=0, calibrated_radius_px=None)
    return dict(status='empirical_development_estimate_not_heldout_validated',
                calibration_count=len(errors), images=len(cases), errors_px=errors,
                median_error_px=float(np.median(errors)),
                calibrated_radius_px=float(max(.5, np.percentile(errors, 95))),
                reviewer_sources=sorted(reviewers), default_radius_unchanged_px=6,
                method='95th percentile Euclidean landmark error in original pixels',
                limitation='Scale-specific; validate coverage on separate labeled images')


def analyze(track, radii, strings=None):
    result = dict(schema_version='chord_photo_candidates.v1',
                  selection_status=track['status'], selected_hand_index=track['selected_hand_index'],
                  contact='unknown', chord_name=None, strings=string_interface(strings, track),
                  hands=track['hands'], fingers=[], index_segments=[],
                  uncertainty='Assumed landmark error; excludes board error and actual contact',
                  selection_review='pending')
    selected = track['selected_hand_index']
    if selected is None:
        return result
    if track['status'] == 'invalid_cached_fret_geometry':
        result['geometry_status'] = 'invalid_cached_fret_geometry'
        return result
    hand = track['hands'][selected]
    for finger, index in FINGERS.items():
        landmark = hand['landmarks'][index]
        entries = []
        for radius in radii:
            distribution = circle_distribution(landmark['pixel'], radius, np.array(track['M']))
            entry = dict(radius_px=radius, distribution=distribution,
                         **probability_candidates(distribution, track['frets'], track['canvas_size']))
            for candidate in entry['candidates']:
                capo = track.get('capo_physical_fret')
                candidate['capo_relative_fret'] = candidate['fret_num']-capo if capo is not None else None
            entries.append(entry)
        result['fingers'].append(dict(finger=finger, landmark_index=index, pixel=landmark['pixel'],
                                     flat=landmark['flat'], contact='unknown', sensitivity=entries))
    # Preserve MCP/PIP/DIP/TIP and whole phalanges, rather than interpreting a tip as barre.
    for a, b in ((5, 6), (6, 7), (7, 8)):
        endpoints = [hand['landmarks'][i]['pixel'] for i in (a, b)]
        points = np.linspace(endpoints[0], endpoints[1], 9)
        samples = []
        for t, point in zip(np.linspace(0, 1, 9), points):
            distribution = circle_distribution(point, 6., np.array(track['M']))
            samples.append(dict(t=float(t), pixel=point.tolist(),
                                **probability_candidates(distribution, track['frets'], track['canvas_size'], 8192)))
        result['index_segments'].append(dict(landmark_indices=[a, b], pixel_endpoints=endpoints,
                                            flat_endpoints=project(endpoints, np.array(track['M'])).tolist(),
                                            radius_px=6., samples=samples, contact='unknown',
                                            interpretation='segment location only; not a confirmed barre'))
    return result


def overlay(track, result, out, name):
    raw = cv2.imread(track['image'])
    if raw is None:
        raise FileNotFoundError(track['image'])
    width, height = track['canvas_size']
    matrix = np.array(track['M'])
    radii = [e['radius_px'] for e in result['fingers'][0]['sensitivity']] if result['fingers'] else [6.]
    for radius in radii:
        original = raw.copy()
        flat = cv2.warpPerspective(raw, matrix, (width, height))
        yy, xx = np.mgrid[:height, :width]
        for wire in track['frets']:
            if 'm' not in wire or 'b' not in wire:
                continue
            points = np.array([[wire['b'], 0], [wire['m']*height+wire['b'], height]])
            for canvas, pts in ((flat, points), (original, project(points, np.array(track['M_inv'])))):
                cv2.line(canvas, tuple(np.rint(pts[0]).astype(int)), tuple(np.rint(pts[1]).astype(int)), (100, 160, 100), 1)
            cv2.putText(flat, str(wire['fret_num']), (round(wire['b'])+2, height-4), cv2.FONT_HERSHEY_SIMPLEX, .3, (170, 220, 170), 1)
        for hand in track['hands']:
            color = (0, 200, 255) if hand['hand_index'] == track['selected_hand_index'] else (140, 140, 140)
            for canvas, key in ((original, 'pixel'), (flat, 'flat')):
                for a, b in EDGES:
                    endpoints = [hand['landmarks'][i][key] for i in (a, b)]
                    if any(p is None for p in endpoints):
                        continue
                    ends = [tuple(np.rint(np.clip(p, -100000, 100000)).astype(int)) for p in endpoints]
                    ok, p, q = cv2.clipLine((0, 0, canvas.shape[1], canvas.shape[0]), *ends)
                    if ok:
                        cv2.line(canvas, p, q, color, 1)
        for segment in result['index_segments']:
            for canvas, key in ((original, 'pixel_endpoints'), (flat, 'flat_endpoints')):
                ends = [tuple(np.rint(np.clip(p, -100000, 100000)).astype(int)) for p in segment[key]]
                ok, p, q = cv2.clipLine((0, 0, canvas.shape[1], canvas.shape[0]), *ends)
                if ok:
                    cv2.line(canvas, p, q, (255, 255, 0), 3)
        for finger, color in zip(result['fingers'], [(180, 180, 180)] + COLORS):
            entry = next(e for e in finger['sensitivity'] if e['radius_px'] == radius)
            distribution = entry['distribution']
            p = tuple(np.rint(finger['pixel']).astype(int))
            cv2.circle(original, p, round(radius), color, 2)
            cv2.putText(original, finger['finger'], p, cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1)
            if distribution['status'] != 'ok':
                continue
            delta = np.stack((xx, yy), axis=-1) - distribution['flat_mean']
            exponent = np.einsum('...i,ij,...j->...', delta, np.linalg.inv(distribution['flat_covariance']), delta)
            alpha = (.5*np.exp(-.5*exponent))[..., None]
            flat = np.rint(flat*(1-alpha)+np.array(color)*alpha).astype(np.uint8)
            boundary = np.rint(np.clip(distribution['exact_boundary'], -100000, 100000)).astype(np.int32)
            cv2.polylines(flat, [boundary], True, color, 1)
        for canvas in (original, flat):
            cv2.putText(canvas, f'r95={radius:g}px / {track["status"]} / contact unknown', (4, 15),
                        cv2.FONT_HERSHEY_SIMPLEX, .38, (0, 0, 255), 1)
        cv2.imwrite(str(out / f'{name}_r{radius:g}_original.png'), original)
        cv2.imwrite(str(out / f'{name}_r{radius:g}_flat.png'), flat)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracking-json', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, default=Path('dataset/chord_photo_validation'))
    parser.add_argument('--labels', type=Path)
    parser.add_argument('--strings-json', type=Path, help='Existing detector result; single tracking input only')
    args = parser.parse_args()
    if args.strings_json and len(args.tracking_json) != 1:
        parser.error('--strings-json requires exactly one tracking input')
    args.output.mkdir(parents=True, exist_ok=True)
    tracks = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in args.tracking_json}
    if len(tracks) != len(args.tracking_json):
        raise ValueError('Tracking input stems must be unique')
    labels = json.loads(args.labels.read_text(encoding='utf-8')) if args.labels else []
    calibration = calibrate(labels, tracks)
    radii = [3., 6., 9., 12.]
    if calibration.get('calibrated_radius_px') is not None:
        radii = sorted(set(radii + [calibration['calibrated_radius_px']]))
    external = json.loads(args.strings_json.read_text(encoding='utf-8')) if args.strings_json else None
    template, summary = [], []
    for name, track in tracks.items():
        result = analyze(track, radii, external)
        image = Path(track['image'])
        result.update(case_id=name, source_image=str(image), board_result=track['board_result'],
                      image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                      tracking_source=str(next(p for p in args.tracking_json if p.stem == name)),
                      calibration=calibration, api_calls=0)
        (args.output / f'{name}_candidates.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
        overlay(track, result, args.output, name)
        template.append(dict(case_id=name, review_status='pending', chord_type='unverified',
                             chord_name=None, fretting_hand_index=None, landmarks=[],
                             fret_labels=[], notes='Label visible points independently; do not copy predictions'))
        summary.append(dict(case_id=name, selection_status=result['selection_status'],
                            fingers=len(result['fingers']), chord_type='unverified'))
    (args.output / 'review_template.json').write_text(json.dumps(template, indent=2), encoding='utf-8')
    (args.output / 'summary.json').write_text(json.dumps(dict(cases=summary, calibration=calibration,
                                                           api_calls=0), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
