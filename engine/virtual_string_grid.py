"""Conditional fret x virtual-string regions. No contact inference or API calls.

Coordinates are continuous common-board coordinates [0,W] x [0,H].
Fret models use x(y)=xt+(xb-xt)*y/H; string models use y(x)=m*x+b.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from fretboard_frame_identity import assert_same_frame, sha256_file

ROOT = Path(__file__).resolve().parent
VERSION = 'virtual_string_grid.v1'


def area(poly):
    p = np.asarray(poly, float)
    if len(p) < 3:
        return 0.0
    return float(abs(np.dot(p[:, 0], np.roll(p[:, 1], -1)) -
                     np.dot(p[:, 1], np.roll(p[:, 0], -1))) / 2)


def clip(poly, a, b, c):
    """Clip convex polygon to a*x+b*y+c >= 0."""
    out = []
    if not poly:
        return out
    for p, q in zip(poly, poly[1:] + poly[:1]):
        fp, fq = a*p[0]+b*p[1]+c, a*q[0]+b*q[1]+c
        inside_p, inside_q = fp >= -1e-9, fq >= -1e-9
        if inside_p:
            out.append(list(p))
        if inside_p != inside_q:
            t = fp / (fp-fq)
            out.append([p[0]+t*(q[0]-p[0]), p[1]+t*(q[1]-p[1])])
    return out


def check_board(board):
    w, h = map(float, board['canvas_size'])
    if w <= 0 or h <= 0:
        raise ValueError('Invalid canvas')
    for name in ['M', 'M_inv']:
        m = np.asarray(board[name], float)
        if m.shape != (3, 3) or not np.isfinite(m).all() or abs(np.linalg.det(m)) < 1e-12:
            raise ValueError('Invalid transform: '+name)
    product = np.asarray(board['M']) @ np.asarray(board['M_inv'])
    if not np.allclose(product/product[2, 2], np.eye(3), atol=1e-6):
        raise ValueError('M and M_inv disagree')
    identity = board.get('frame_identity', {})
    assert_same_frame(board, identity)
    if board.get('image_size') != identity.get('image_size'):
        raise ValueError('Image size mismatch')
    # Named corners must map to nut-top, body-top, body-bottom, nut-bottom.
    corners = cv2.perspectiveTransform(np.asarray(board['corners'], np.float64)[None],
                                       np.asarray(board['M'], float))[0]
    if not np.allclose(corners, [[0, 0], [w, 0], [w, h], [0, h]], atol=.05):
        raise ValueError('Corner orientation/common coordinates disagree')
    return w, h


def build_grid(board, config, observed=None):
    """Build conditional cells; config explicitly supplies spacing independent of anchor.

    anchor_y: y at nut/body for hypothetical physical string6.
    opposite_margin: distance from opposite board edge to string1 at nut/body.
    spacing endpoints = (width - anchor margin - opposite margin)/5.
    spacing_scale is a separate sensitivity assumption, never fitted to hand/audio.
    """
    w, h = check_board(board)
    if observed is not None:
        assert_same_frame(board, observed)
        if observed['canvas_size'] != board['canvas_size']:
            raise ValueError('Observed canvas mismatch')
        for key in ['M', 'M_inv']:
            if not np.allclose(board[key], observed[key], atol=1e-7):
                raise ValueError('Observed transform mismatch')
    cfg = copy.deepcopy(config)
    side = cfg['six_side']
    if side not in ['top', 'bottom']:
        raise ValueError('six_side must be explicit top or bottom')
    direction = 1 if side == 'top' else -1
    anchor = np.asarray(cfg['anchor_y'], float)
    opposite = np.asarray(cfg['opposite_margin'], float)
    scale = float(cfg.get('spacing_scale', 1))
    if anchor.shape != (2,) or opposite.shape != (2,) or not np.isfinite(np.r_[anchor, opposite, scale]).all():
        raise ValueError('Invalid endpoint parameters')
    anchor_margin = anchor if direction == 1 else h-anchor
    if np.any(anchor_margin < 0) or np.any(anchor_margin >= h) or np.any(opposite < 0):
        raise ValueError('Margins outside board')
    spacing = (h-anchor_margin-opposite)/5 * scale
    if np.any(spacing <= 0):
        raise ValueError('Nonpositive spacing')
    centers = []
    for k in range(6, 0, -1):
        ys = anchor + direction*(6-k)*spacing
        if np.any(ys < 0) or np.any(ys > h):
            raise ValueError('Virtual center outside board; revise explicit assumptions')
        centers.append(dict(virtual_string_num=k, physical_string_num=None,
                            y_nut=float(ys[0]), y_body=float(ys[1]),
                            m=float((ys[1]-ys[0])/w), b=float(ys[0]),
                            estimated=True, is_virtual=True, source='assumed_virtual_model'))
    ordered = sorted(centers, key=lambda z:z['b'])
    bounds = [dict(m=0., b=0.)]
    for p, q in zip(ordered, ordered[1:]):
        bounds.append(dict(m=(p['m']+q['m'])/2, b=(p['b']+q['b'])/2))
    bounds.append(dict(m=0., b=h))
    strips = []
    for i, line in enumerate(ordered):
        top, bottom = bounds[i:i+2]
        poly = clip([[0., 0.], [w, 0.], [w, h], [0., h]], -top['m'], 1, -top['b'])
        poly = clip(poly, bottom['m'], -1, bottom['b'])
        strips.append(dict(virtual_string_num=line['virtual_string_num'],
                           polygon=poly, lower_y_boundary=top, upper_y_boundary=bottom))
    frets = {}
    unresolved = []
    for f in board.get('frets', []):
        n = f.get('physical_fret_candidate')
        if type(n) is not int or n < 0 or not all(np.isfinite(f.get(k, np.nan)) for k in ['xt', 'xb']):
            unresolved.append(dict(reason='missing_physical_candidate_or_geometry', fret=copy.deepcopy(f)))
            continue
        if n in frets:
            raise ValueError('Duplicate physical fret candidate')
        frets[n] = f
    cells = []
    rect = [[0., 0.], [w, 0.], [w, h], [0., h]]
    covered = 0.
    invalid_boundaries = set()
    for n in sorted(frets):
        if n-1 in frets and (frets[n]['xt'] <= frets[n-1]['xt'] or frets[n]['xb'] <= frets[n-1]['xb']):
            invalid_boundaries.add(n)
            unresolved.append(dict(physical_fret_candidate=n, reason='crossing_or_reversed_boundaries'))
    for n in sorted(frets):
        if n == 0:
            continue
        if n-1 not in frets:
            unresolved.append(dict(physical_fret_candidate=n, reason='missing_preceding_boundary'))
            continue
        if n in invalid_boundaries or n-1 in invalid_boundaries:
            unresolved.append(dict(physical_fret_candidate=n, reason='interval_touches_invalid_boundary'))
            continue
        left, right = frets[n-1], frets[n]
        if right['xt'] <= left['xt'] or right['xb'] <= left['xb']:
            unresolved.append(dict(physical_fret_candidate=n, reason='crossing_or_reversed_boundaries'))
            continue
        lm, rm = (left['xb']-left['xt'])/h, (right['xb']-right['xt'])/h
        band = clip(rect, 1, -lm, -left['xt'])
        band = clip(band, -1, rm, right['xt'])
        covered += area(band)
        for strip in strips:
            poly = clip(strip['polygon'], 1, -lm, -left['xt'])
            poly = clip(poly, -1, rm, right['xt'])
            if area(poly) <= 1e-8:
                continue
            capo_info = board.get('capo', {})
            capo = capo_info.get('value') if (capo_info.get('independently_verified') is True or
                                             capo_info.get('user_confirmed_stop_fret') is True) else None
            cells.append(dict(cell_id=f"s{strip['virtual_string_num']}_f{n}",
                virtual_string_num=strip['virtual_string_num'], physical_string_num=None,
                physical_fret_candidate=n, confirmed_physical_fret_num=None,
                boundary_number_confirmations=[left.get('confirmed_physical_fret_num'), right.get('confirmed_physical_fret_num')],
                relative_fret=(n-capo if type(capo) is int and n >= capo else None),
                relative_fret_source=('confirmed_capo' if type(capo) is int else 'unknown_capo'),
                polygon=poly, area=area(poly), estimated=True, is_virtual=True,
                contact='unknown', sounding='unknown', confidence_calibrated=False,
                numbering_status='conditional_physical_fret_candidate_and_assumed_string_order',
                boundary_sources=[copy.deepcopy(left), copy.deepcopy(right)]))
    # Reject overlapping numbered bands (e.g. a displaced next interval).
    for i, a in enumerate(cells):
        for b in cells[i+1:]:
            intersection, _ = cv2.intersectConvexConvex(np.asarray(a['polygon'], np.float32),
                                                       np.asarray(b['polygon'], np.float32))
            if intersection > .02:
                raise ValueError('Overlapping cell geometry')
    result = dict(grid_version=VERSION, frame_identity=copy.deepcopy(board['frame_identity']),
        **{k:copy.deepcopy(board[k]) for k in ['source_id', 'frame_index', 'frame_pts_s', 'frame_pixel_sha256',
                                               'canvas_size', 'image_size', 'M', 'M_inv']},
        geometry_source='saved_board_candidate_geometry', geometry_status=board.get('geometry_validity', {}).get('status', 'unverified'),
        upstream_geometry_validity=copy.deepcopy(board.get('geometry_validity', {})),
        precise_geometry_verified=False, contact_fret_decision_allowed=False,
        anchor_status=cfg.get('anchor_status', 'assumed_not_observed'),
        spacing_source='endpoint_width_minus_explicit_margins_divided_by_5_then_sensitivity_scale',
        numbering_status='virtual_string_order_assumption_physical_identity_unverified',
        assumptions=cfg, anchor_y=anchor.tolist(), endpoint_spacing=spacing.tolist(),
        endpoint_outer_margins=dict(anchor=anchor_margin.tolist(), opposite=(h-anchor_margin-5*spacing).tolist()),
        virtual_lines=centers, string_regions=strips, cells=cells, unresolved_fret_boundaries=unresolved,
        unassigned_board_area=w*h-covered, covered_fret_area=covered,
        partition_area=sum(c['area'] for c in cells),
        observed_string_layer=copy.deepcopy(observed.get('strings', [])) if observed else [],
        contact='unknown', sounding='unknown', is_virtual=True, estimated=True,
        confidence_calibrated=False, spacing_error_px=None, spacing_error_status='not_evaluated_no_ground_truth',
        api_calls=0, synthetic=bool(board.get('synthetic', False)))
    fingerprint = dict(identity=result['frame_identity'], M=result['M'], frets=board.get('frets'), config=cfg, version=VERSION)
    result['grid_id'] = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    return result


def assert_grid_compatible(grid, other):
    assert_same_frame(grid, other)
    for key in ['grid_id', 'grid_version', 'canvas_size']:
        if grid.get(key) != other.get(key):
            raise ValueError('Grid mismatch: '+key)
    for key in ['M', 'M_inv']:
        if not np.allclose(grid[key], other[key], atol=1e-7):
            raise ValueError('Grid transform mismatch')
    return True


def render_grid(raw, grid):
    w, h = grid['canvas_size']
    flat = cv2.warpPerspective(raw, np.asarray(grid['M']), (w, h))
    original = raw.copy()
    inverse = np.asarray(grid['M_inv'])
    def draw(points, color, thickness=1, closed=False):
        p = np.asarray(points, float)
        cv2.polylines(flat, [np.rint(p).astype(np.int32)], closed, color, thickness)
        q = cv2.perspectiveTransform(p[None], inverse)[0]
        cv2.polylines(original, [np.rint(q).astype(np.int32)], closed, color, thickness)
    for cell in grid['cells']:
        draw(cell['polygon'], (150, 80, 30), closed=True)
        center = np.mean(cell['polygon'], axis=0)
        label = f"v{cell['virtual_string_num']}:f{cell['physical_fret_candidate']}?"
        cv2.putText(flat, label, tuple(np.rint(center).astype(int)), cv2.FONT_HERSHEY_SIMPLEX, .22, (255, 230, 180), 1)
    for line in grid['virtual_lines']:
        draw([[0, line['b']], [w, line['m']*w+line['b']]], (255, 0, 255))
    for line in grid['observed_string_layer']:
        for a, b in line.get('observed_intervals', []):
            draw([[a, line['m']*a+line['b']], [b, line['m']*b+line['b']]], (0, 220, 255))
    cv2.putText(original, f"frame {grid['frame_index']} PTS {grid['frame_pts_s']:.6f} VIRTUAL / contact UNKNOWN",
                (15, 25), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 0, 255), 1)
    return original, flat


def validate_run(folder):
    folder = Path(folder)
    fixture = json.loads((folder/'same_frame_fixture.json').read_text(encoding='utf-8'))
    count, max_residual = 0, 0.
    for frame in fixture['frames']:
        board = json.loads(Path(frame['board_json']).read_text(encoding='utf-8'))
        if sha256_file(frame['board_json']) != frame['board_json_sha256']:
            raise ValueError('Upstream board changed')
        assert_same_frame(frame['frame_identity'], board)
        raw = cv2.imread(frame['original'])
        if raw is None or hashlib.sha256(raw.tobytes()).hexdigest() != board['frame_pixel_sha256']:
            raise ValueError('Original pixels changed')
        for entry in frame['models']:
            g = json.loads(Path(entry['grid_json']).read_text(encoding='utf-8'))
            assert_same_frame(board, g)
            expected = build_grid(board, g['assumptions'])
            assert_grid_compatible(g, expected)
            for key in ['cells', 'virtual_lines', 'string_regions', 'upstream_geometry_validity']:
                if g[key] != expected[key]:
                    raise ValueError('Reconstructed geometry differs: '+key)
            residual = abs(g['partition_area']-g['covered_fret_area'])
            max_residual = max(max_residual, residual)
            if residual > 1e-5 or g['synthetic'] or g['contact_fret_decision_allowed'] or g['confidence_calibrated']:
                raise ValueError('Geometry area or uncertainty contract failure')
            for key in ['raw_overlay', 'flat_overlay']:
                if cv2.imread(entry[key]) is None:
                    raise ValueError('Missing overlay')
            count += 1
    result = dict(status='pass', frames=len(fixture['frames']), models=count,
                  max_area_partition_residual=max_residual, synthetic_models=0,
                  confirmed_physical_strings=0, contact_allowed=0, spacing_accuracy='not_evaluated', api_calls=0)
    (folder/'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def write_report(folder):
    folder = Path(folder).resolve()
    fixture = json.loads((folder/'same_frame_fixture.json').read_text(encoding='utf-8'))
    sensitivity = json.loads((folder/'sensitivity.json').read_text(encoding='utf-8'))
    validation = validate_run(folder)
    first = fixture['frames'][0]
    tiles = []
    for model in first['models']:
        flat = cv2.imread(model['flat_overlay'])
        tile = np.full((185, flat.shape[1], 3), 25, np.uint8)
        row = next(r for r in sensitivity if r['frame_index']==120 and r['model_name']==model['model_name'])
        cv2.putText(tile, f"{model['model_name']} delta={row['max_center_displacement_common_px']:.2f}px (not error)",
                    (8, 23), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        tile[35:] = flat
        tiles.append(tile)
    compare = folder/'frame120_sensitivity_comparison.jpg'
    cv2.imwrite(str(compare), np.vstack(tiles))
    rows = ['|frame|PTS|anchor nut/body|spacing nut/body|cells|', '|---|---:|---|---|---:|']
    for f in fixture['frames']:
        g = json.loads(Path(f['models'][0]['grid_json']).read_text(encoding='utf-8'))
        rows.append(f"|{g['frame_index']}|{g['frame_pts_s']:.6f}|{g['anchor_y'][0]:.2f}/{g['anchor_y'][1]:.2f}|{g['endpoint_spacing'][0]:.2f}/{g['endpoint_spacing'][1]:.2f}|{len(g['cells'])}|")
    report = f'''# 가상 현 × 프렛 구역 — 2026-11-03

원본 영상의 실제 11프레임(120,124,190,209~216)에 각6모델, 총66개의 조건부 grid를 생성했다. 외부 API/다운로드/설치0회. 원본·과거run·다른 담당 코드를 변경하지 않았다. v1은 초기 생성본으로 보존하고 최신은 이 v2다. 합성 검사는 별도이며 이 run은 실제 프레임이다.

## 의미와 가정

가상선은 마젠타, 실제 영상에서 추출한 **현 후보의 관측 지지 구간**은 노랑, 칸 경계는 파랑이다. 노란 후보도 테두리·반사일 수 있다. 가상6현을 관측6현 성공으로 세지 않는다. contact/sounding=unknown, physical_string_num=null, confidence_calibrated=false. 모든 exact geometry/contact는 보류한다. 위치 질량·접촉 확률·오디오 판단은 이 모듈에서 계산하지 않는다.

6번 현 쪽을 named low-E corner의 위쪽이라고 가정했다. baseline은 최상단 검출 후보를 anchor로 삼지만 실제6번 현 확인은 없다. 별도 margin_only_alternative은 관측 anchor 없이 너트/바디 위 여백을 각각 지판폭의10%로 둔다. 반대쪽 여백은 너트10%/바디14%라는 **검증되지 않은 설정값**이며 코드/TAB/손/오디오 정답에 맞추지 않았다. 이 값은 악기 치수 정답이 아니다.

각 끝점에서 `d=(지판폭-anchor쪽여백-반대쪽여백)/5`. 현 사이 간격은5개이며 전체 폭6등분을 하지 않는다. 너트와 바디의 d를 따로 계산해 x에 따라 보간한다. `y_k(x)=y_6(x)+(6-k)*d(x)`. 아래쪽6번 현 설정도 검사했다. 기준계는 연속 [0,W]×[0,H], x=0 너트·x=W 바디이며 원본 화면의 좌우와 분리한다.

가상 현 중간선을 구역 경계로 사용하고 최외곽은 지판 경계로 자른다. 프렛n 칸은 경계n-1~n으로만 생성한다. 누락·불명 번호는 건너뛰어 연결하지 않고 crossing 경계가 닿는 두 칸도 보류한다. 이 run은 프렛 후보0~6 범위만 제공하므로 바디 쪽 나머지 면적은 unassigned_board_area다. 원본 끝단이 마지막 실제 프렛이라는 확정도 없다. fret1의 기존 사용자 의미 확인은 boundary provenance에만 보존하며 가상 현·접촉 확인으로 승격하지 않는다. 미확인 카포 후보1은 상대 프렛에 가산하지 않는다.

## 실제 원본과 비교 사진

frame120, 실제PTS5.041667초. 원본 픽셀이며 생성형 편집/사람 정밀 좌표 GT가 아니다.

![frame120 원본]({first['original']})

frame120 baseline: 추정 가상선/칸과 관측 후보를 분리했다. 모든 칸 이름의 ?는 조건부 번호다.

![frame120 원본 grid]({first['models'][0]['raw_overlay']})

![frame120 평탄 grid]({first['models'][0]['flat_overlay']})

anchor±3 공통px, spacing±10%, 여백 대안의6개 모델 비교다. 수치는 baseline 대비 위치 변화이며 정답 오차나 확률구간이 아니다. 이 run 전체 최대 중심선 변위는 {max(r['max_center_displacement_common_px'] for r in sensitivity):.2f} 공통px다. 간격 오차는 독립 정답이 없어 미평가(null)다.

![frame120 민감도]({compare})

## 프레임별 baseline

{chr(10).join(rows)}

## 실패·미확정 사례

frame124/190의 경계 후보 혼동,209~216의 가림과 공통 기하 오류 가능성을 해소하지 않았다. 동일 검출기의 설정·시간 일치는 독립적인 실제 현 증거가 아니다. 아래 사진은 가상 격자를 생성할 수 있어도 실제6번 현/접촉 성공을 뜻하지 않는 사례다.
'''
    for index in [124, 190, 215]:
        f = next(f for f in fixture['frames'] if f['frame_identity']['frame_index']==index)
        report += f"\nframe{index}, 실제PTS{f['frame_identity']['frame_pts_s']:.6f}: 관측 후보 노랑/가상 마젠타/기하 및 실제현 미확정.\n\n![frame{index} 미확정 원본 grid]({f['models'][0]['raw_overlay']})\n\n![frame{index} 미확정 평탄 grid]({f['models'][0]['flat_overlay']})\n"
    report += f'''
## 계약과 검증

`same_frame_fixture.json`에 원본 식별자·실제PTS·픽셀해시·원본PNG·upstream board JSON/hash·6개 grid ID/경로/그림을 제공했다. `grid_id`는 frame identity, M, fret provenance, assumptions, 버전의 해시이며 다른 민감도 모델은 다른ID다. cell_id는 grid 안에서만 유일하므로 결합키는 (grid_id,cell_id)다. observed_string_layer는 가상선과 별도 보존한다. assert_grid_compatible는 source/frame/PTS/pixels/canvas/M/M_inv/grid ID/version이 다르면 거부한다.

```powershell
python virtual_string_grid.py --output dataset/virtual_string_grid/runs/<새run>
python virtual_string_grid.py --validate-run dataset/virtual_string_grid/runs/clip_003_012_20261103_v2
python -m unittest test_virtual_string_grid test_fretboard_semantic_review test_fretboard_frame_identity test_string_detector test_fret_geometry test_baze_client -q
```

실제 검증: {validation['frames']}프레임/{validation['models']}모델 재구성 pass, 원본픽셀/상류JSON hash 및 overlay 존재 확인. 구역 면적 합과 프렛 띠 면적의 최대 차 {validation['max_area_partition_residual']:.3g} 공통px². 구역 중복은 교차면적으로 검사하고 보드 외부는 포함하지 않는다. 이는 산술/계약 검증이며 지판 정밀도나 실제 현 정확도 평가가 아니다. 회귀 명령은 신규10개 포함42개 통과했다.

손 담당은 polygon에 위치 질량을 적분할 수 있으나 이 grid의 가정과 기하 보류를 함께 전달해야 한다. 각 민감도 모델을 별도로 평가하고 baseline만 확정값으로 사용하지 않는다. Kim8점 재검수 요청 없음. 다음 독립 자료가 부족한 항목은 실제 현 정체성·양끝 간격/여백·정밀 프렛 끝점이다. 완전6현 검출을 기다리지 않고 이 조건부 구역을 후속 실험에 제공한다.
'''
    (folder/'report.md').write_text(report.replace(chr(92), '/'), encoding='utf-8')
    return validation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--boards', type=Path, default=ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v2_semantic/frames')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--validate-run', type=Path)
    args = parser.parse_args()
    if args.validate_run:
        print(json.dumps(validate_run(args.validate_run)))
        return
    if args.output is None:
        parser.error('--output or --validate-run required')
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError('Use a new run directory')
    out.mkdir(parents=True)
    from string_geometry import analyze_saved_board
    manifest, sensitivity = [], []
    for index in [120, 124, 190, *range(209, 217)]:
        stem = f'clip003012_f{index:06}'
        board_path = args.boards/(stem+'_board.json')
        board = json.loads(board_path.read_text(encoding='utf-8'))
        raw = cv2.imread(board['image_file'])
        if raw is None or hashlib.sha256(raw.tobytes()).hexdigest() != board['frame_pixel_sha256']:
            raise ValueError('Source pixel mismatch')
        if sha256_file(board['image_file']) != board['frame_identity']['image_file_sha256']:
            raise ValueError('Source file mismatch')
        observed, *_ = analyze_saved_board(raw, board)
        # Preserve all observed candidates separately. Topmost candidate is a hypothetical anchor,
        # never a verified physical sixth string; include a pure margin model as alternative.
        lines = sorted(observed['strings'], key=lambda s:s['b'])
        w, h = board['canvas_size']
        anchor = [lines[0]['b'], lines[0]['m']*w+lines[0]['b']] if lines else [.10*h, .10*h]
        base = dict(model_name='candidate_anchor', six_side='top',
            six_side_source='assumed_named_low_E_corner_convention_not_independent_string_identity',
            anchor_y=anchor, anchor_status='unverified_topmost_observed_candidate' if lines else 'assumed_margin_no_observation',
            anchor_candidate_index=0 if lines else None, opposite_margin=[.10*h, .14*h], spacing_scale=1.,
            tuning='unknown_not_used', capo='unknown_not_used',
            spacing_not_inferred_from_one_line=True, fit_to_hand_or_audio=False,
            uncertainty='scenario_sensitivity_not_probability_or_calibrated_interval')
        configs = [base]
        for name, shift, scale in [('anchor_minus3', -3, 1), ('anchor_plus3', 3, 1),
                                    ('spacing_minus10pct', 0, .9), ('spacing_plus10pct', 0, 1.1)]:
            cfg = copy.deepcopy(base)
            cfg.update(model_name=name, anchor_y=[v+shift for v in anchor], spacing_scale=scale)
            configs.append(cfg)
        cfg = copy.deepcopy(base)
        cfg.update(model_name='margin_only_alternative', anchor_y=[.10*h, .10*h], anchor_status='assumed_margin_not_observed', anchor_candidate_index=None)
        configs.append(cfg)
        models = []
        for cfg in configs:
            model = build_grid(board, cfg, observed)
            filename = stem+'_'+cfg['model_name']
            path = out/(filename+'.json')
            path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding='utf-8')
            raw_overlay, flat_overlay = render_grid(raw, model)
            cv2.imwrite(str(out/(filename+'_raw.png')), raw_overlay)
            cv2.imwrite(str(out/(filename+'_flat.png')), flat_overlay)
            models.append(dict(model_name=cfg['model_name'], grid_id=model['grid_id'], grid_json=str(path),
                               raw_overlay=str(out/(filename+'_raw.png')), flat_overlay=str(out/(filename+'_flat.png'))))
            diff = max(abs(a['y_nut']-b['y_nut']) for a, b in zip(model['virtual_lines'], build_grid(board, base)['virtual_lines']))
            diff = max(diff, max(abs(a['y_body']-b['y_body']) for a, b in zip(model['virtual_lines'], build_grid(board, base)['virtual_lines'])))
            sensitivity.append(dict(frame_index=index, model_name=cfg['model_name'], max_center_displacement_common_px=diff,
                                    endpoint_spacing=model['endpoint_spacing'], cells=len(model['cells']),
                                    area_residual=model['partition_area']-model['covered_fret_area']))
        manifest.append(dict(frame_identity=board['frame_identity'], board_json=str(board_path.resolve()), board_json_sha256=sha256_file(board_path),
                             original=board['image_file'], models=models, synthetic=False))
    (out/'same_frame_fixture.json').write_text(json.dumps(dict(grid_version=VERSION, frames=manifest, synthetic=False, api_calls=0), indent=2), encoding='utf-8')
    (out/'sensitivity.json').write_text(json.dumps(sensitivity, indent=2), encoding='utf-8')
    write_report(out)
    print(json.dumps(dict(frames=len(manifest), models=len(sensitivity), api_calls=0, output=str(out))))


if __name__ == '__main__':
    main()
