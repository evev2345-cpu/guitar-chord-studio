"""Circle-to-conic geometry and local Gaussian fingertip uncertainty, offline.

The radius is a user-set 95% uncertainty radius, NOT calibrated contact confidence.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from hand_fret_tracker import project

CHI2_95 = -2 * np.log(.05)
COLORS = [(0, 100, 255), (0, 230, 100), (255, 150, 0), (220, 0, 220)]


def circle_distribution(center, radius, matrix):
    center, matrix = np.asarray(center, float), np.asarray(matrix, float)
    if not np.isfinite(radius) or radius <= 0:
        raise ValueError('radius must be positive and finite')
    homogeneous = matrix @ np.r_[center, 1.]
    denominator = homogeneous[2]
    # An uncertainty disk crossing the projective horizon is not an ellipse.
    if abs(denominator) <= radius * np.linalg.norm(matrix[2, :2]) + 1e-9:
        return dict(status='circle_crosses_projective_horizon')
    mean = homogeneous[:2] / denominator
    jacobian = (matrix[:2, :2] - mean[:, None] * matrix[2, :2]) / denominator
    sigma = radius / np.sqrt(CHI2_95)
    covariance = sigma ** 2 * jacobian @ jacobian.T
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if eigenvalues.min() <= 0 or not np.isfinite(covariance).all():
        return dict(status='degenerate_covariance')
    x, y = center
    circle = np.array([[1., 0, -x], [0, 1., -y], [-x, -y, x*x+y*y-radius*radius]])
    inverse = np.linalg.inv(matrix)
    conic = inverse.T @ circle @ inverse
    conic /= np.linalg.norm(conic)
    angle = np.linspace(0, 2*np.pi, 361)
    boundary = project(center + radius * np.column_stack((np.cos(angle), np.sin(angle))), matrix)
    return dict(status='ok', original_center=center.tolist(), radius_95_px=float(radius),
                original_sigma_px=float(sigma), original_circle_matrix=circle.tolist(),
                flat_mean=mean.tolist(), flat_covariance=covariance.tolist(),
                flat_exact_conic_matrix=conic.tolist(), exact_boundary=boundary.tolist(),
                ellipse_95_semiaxes=np.sqrt(CHI2_95*eigenvalues[::-1]).tolist(),
                ellipse_angle_degrees=float(np.degrees(np.arctan2(eigenvectors[1, -1], eigenvectors[0, -1]))),
                density_method='local_jacobian_gaussian', contact_confirmed=False)


def density_grid(distribution, width, height):
    yy, xx = np.mgrid[:height, :width]
    delta = np.stack((xx, yy), axis=-1) - distribution['flat_mean']
    covariance = np.array(distribution['flat_covariance'])
    exponent = np.einsum('...i,ij,...j->...', delta, np.linalg.inv(covariance), delta)
    return np.exp(-.5*exponent) / (2*np.pi*np.sqrt(np.linalg.det(covariance)))


def run(track_path, prefix, radius):
    track = json.loads(Path(track_path).read_text(encoding='utf-8'))
    image_path = track.get('image')
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(image_path)
    matrix = np.array(track['M'])
    width, height = track['canvas_size']
    selected = track['selected_hand_index']
    original = image.copy()
    flat = cv2.warpPerspective(image, matrix, (width, height))
    distributions, grids = [], {}
    output = dict(source=str(track_path), radius_95_px=radius,
                  selection_status=track['status'], selected_hand_index=selected,
                  interpretation='Assumed location uncertainty, not contact probability',
                  approximation='Local Jacobian Gaussian; exact transformed circle shown separately',
                  distributions=distributions)
    if selected is not None:
        hand = track['hands'][selected]
        for (tip, name), color in zip([(8, 'index'), (12, 'middle'), (16, 'ring'), (20, 'pinky')], COLORS):
            center = hand['landmarks'][tip]['pixel']
            distribution = circle_distribution(center, radius, matrix)
            distribution['finger'] = name
            distributions.append(distribution)
            cv2.circle(original, tuple(np.rint(center).astype(int)), round(radius), color, 2)
            cv2.putText(original, name, tuple(np.rint(np.array(center)+[radius+2, 0]).astype(int)),
                        cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1)
            if distribution['status'] != 'ok':
                continue
            density = density_grid(distribution, width, height)
            grids[name] = density
            # Sum density only over actual visible cells; never renormalize away outside mass.
            distribution['board_probability_approx'] = float(density.sum())
            yy, xx = np.mgrid[:height, :width]
            wires = {r['fret_num']: r for r in track['frets'] if 'm' in r and 'b' in r}
            masses = []
            for number, right in sorted(wires.items()):
                left = wires.get(number-1)
                if left is None:
                    continue
                inside = (xx >= left['m']*yy+left['b']) & (xx < right['m']*yy+right['b'])
                masses.append(dict(fret_num=number, probability_approx=float(density[inside].sum()),
                                   boundary_sources=[left['source'], right['source']]))
            distribution['fret_probability_mass'] = sorted(masses, key=lambda r: -r['probability_approx'])
            peak = 1 / (2*np.pi*np.sqrt(np.linalg.det(distribution['flat_covariance'])))
            alpha = (.65 * density / peak)[..., None]
            flat = np.rint(flat*(1-alpha) + np.array(color)*alpha).astype(np.uint8)
        # Exact transformed circle solid, local Gaussian 95% ellipse thin white.
        for distribution, color in zip(distributions, COLORS):
            if distribution['status'] != 'ok':
                continue
            boundary = np.array(distribution['exact_boundary'])
            cv2.polylines(flat, [np.rint(np.clip(boundary, -100000, 100000)).astype(np.int32)], True, color, 2)
            mean = tuple(np.rint(distribution['flat_mean']).astype(int))
            axes = tuple(np.maximum(1, np.rint(distribution['ellipse_95_semiaxes'])).astype(int))
            if max(axes) < 100000 and max(abs(v) for v in mean) < 100000:
                cv2.ellipse(flat, mean, axes, distribution['ellipse_angle_degrees'], 0, 360, (255, 255, 255), 1)
                cv2.putText(flat, distribution['finger'], mean, cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1)
    for canvas in (original, flat):
        cv2.putText(canvas, f'Assumed 95% radius={radius:g}px / NOT contact probability', (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 255), 1)
    prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(prefix)+'_original.png', original)
    cv2.imwrite(str(prefix)+'_flat.png', flat)
    np.savez_compressed(str(prefix)+'_density.npz', **grids)
    Path(str(prefix)+'.json').write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps([dict(finger=d['finger'], top=d.get('fret_probability_mass', [])[:3],
                           board=d.get('board_probability_approx')) for d in distributions]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracking-json', required=True)
    parser.add_argument('--radius', type=float, default=6., help='Original pixel radius containing 95%% Gaussian mass')
    parser.add_argument('--out-prefix', default='sample_images/fingertip_probability/result')
    args = parser.parse_args()
    run(args.tracking_json, args.out_prefix, args.radius)
