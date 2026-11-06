"""Offline spatial fingering/audio compatibility diagnostics, never contact inference."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import cv2
import numpy as np

from chord_photo_validation import probability_candidates
from fingertip_probability import circle_distribution
from harmony_engine import analyze
from harmony_input_adapter import adapt_audio
from string_geometry import analyze_saved_board

ROOT = Path(__file__).resolve().parent
BOARD = ROOT / 'dataset/fretboard_review/runs/clip_003_012_20261103_v2_semantic'
HAND = ROOT / 'dataset/hand_analysis/runs/clip_003_012_20261103_v1/observations.jsonl'
AUDIO = ROOT / 'dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5/accompaniment/fixtures'
TUNING = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}
TIPS = {4: 'thumb', 8: 'index', 12: 'middle', 16: 'ring', 20: 'pinky'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def same_frame(a, b):
    for key in ('source_id', 'frame_index', 'frame_pixel_sha256'):
        if a.get(key) is None or a[key] != b.get(key):
            raise ValueError('Frame mismatch: ' + key)
    if abs(a['frame_pts_s'] - b['frame_pts_s']) > 1e-6:
        raise ValueError('Frame PTS mismatch')


def select_frame(hands, start, end, string_indices):
    # Half-open support: never carry a reviewed earlier pose into an audio window.
    eligible = [h for h in hands if start <= h['frame_pts_s'] < end and h['status'] == 'selected']
    if not eligible:
        return None
    with_strings = [h for h in eligible if h['frame_index'] in string_indices]
    return min(with_strings or eligible, key=lambda h: abs(h['frame_pts_s'] - (start+end)/2))


def possible_strings(lines, flat_point, physical_order):
    """Conditional order-preserving assignments; never manufacture missing lines."""
    if not lines:
        return dict(status='no_same_frame_string_evidence', strings=list(TUNING),
                    mapping_count=None, nearest_line_id=None, observed_at_x=False)
    x, y = flat_point
    ordered = sorted(lines, key=lambda s: s['m']*x+s['b'])
    closest = min(range(len(ordered)), key=lambda i: abs(ordered[i]['m']*x+ordered[i]['b']-y))
    line = ordered[closest]
    supported = any(a <= x <= b for a, b in line.get('observed_intervals', []))
    # Closeness is only a spatial diagnostic. It does not establish string contact.
    result = dict(nearest_line_id=line.get('line_id'),
                  line_distance_flat_px=abs(line['m']*x+line['b']-y),
                  observed_at_x=supported, physical_string_confirmed=None)
    if len(ordered) > 6 or physical_order not in ('low_e_top', 'high_e_top'):
        return dict(result, status='unusable_order_or_excess_lines', strings=list(TUNING), mapping_count=None)
    numbers = list(range(6, 0, -1)) if physical_order == 'low_e_top' else list(range(1, 7))
    mappings = list(itertools.combinations(numbers, len(ordered)))
    return dict(result, status='conditional_nearest_line_order_hypothesis',
                strings=sorted({m[closest] for m in mappings}), mapping_count=len(mappings),
                assumptions=['every detected line is a distinct real string',
                             'physical edge orientation is correct',
                             'nearest line is relevant to fingertip; no contact inferred'],
                warning='False lines, missing lines, off-plane fingers or position errors invalidate this constraint')


def audio_matches(midi, candidates, tolerance_cents=35):
    matches = []
    expected = 440 * 2 ** ((midi-69)/12)
    for c in candidates:
        hz = c.get('median_frequency_hz')
        if hz is None or not math.isfinite(hz) or hz <= 0:
            continue
        cents = 1200 * math.log2(hz/expected)
        if abs(cents) <= tolerance_cents:
            matches.append(dict(candidate_id=c['candidate_id'], cents_error=cents,
                                evidence_ids=c['evidence_ids'],
                                coincident_vocal_stem_evidence_ids=c.get('coincident_vocal_stem_evidence_ids', []),
                                pitch_status=c['pitch_status'], instrument_attribution='unknown'))
    return matches


def joint_string_scenarios(lines, fingers, physical_order, width):
    """One mapping per frame, not independent best-fit string choices per finger."""
    if not 0 < len(lines) <= 6 or physical_order not in ('low_e_top', 'high_e_top'):
        return []
    lines = sorted(lines, key=lambda s: s['b'])
    if any(a['m']*width+a['b'] >= b['m']*width+b['b'] for a, b in zip(lines, lines[1:])):
        return []
    numbers = list(range(6, 0, -1)) if physical_order == 'low_e_top' else list(range(1, 7))
    scenarios = []
    for combination in itertools.combinations(numbers, len(lines)):
        mapping = dict(zip([s['line_id'] for s in lines], combination))
        matched = []
        for finger in fingers:
            nearest = finger.get('nearest_line_diagnostic', {}).get('nearest_line_id')
            for h in finger.get('hypotheses', []):
                if h['audio_matches'] and h['string_hypothesis'] == mapping.get(nearest):
                    matched.append(dict(finger=finger['finger'], string_hypothesis=h['string_hypothesis'],
                                        physical_fret_candidate=h['physical_fret_candidate'],
                                        midi=h['midi_if_fretted_and_standard_tuning'],
                                        evidence_ids=[e for m in h['audio_matches'] for e in m['evidence_ids']]))
        collisions = [s for s in combination if len({m['physical_fret_candidate'] for m in matched
                                                    if m['string_hypothesis'] == s}) > 1]
        scenarios.append(dict(line_to_string_hypothesis=mapping, compatible_finger_hypotheses=matched,
                              same_string_different_fret_collisions=collisions,
                              contact_confirmed=False,
                              scope='one conditional mapping; matched fingers are not simultaneous sounding assertions'))
    return scenarios


def compare_frame(hand, board, strings, audio):
    same_frame(hand, board)
    if hand['source_id'] != audio['source_id']:
        raise ValueError('Audio/video source mismatch')
    if not audio['start_s'] <= hand['frame_pts_s'] < audio['end_s']:
        raise ValueError('Hand frame outside audio window')
    matrix = np.asarray(board['M'], float)
    if strings is not None:
        same_frame(hand, strings)
        if not np.allclose(matrix, strings['M'], atol=1e-8, rtol=1e-8):
            raise ValueError('String/board homography mismatch')
        if strings['canvas_size'] != board['canvas_size']:
            raise ValueError('Canvas mismatch')
    for c in audio['fingering_comparison_candidates']:
        if not (audio['start_s'] <= c['start_s'] < c['end_s'] <= audio['end_s']):
            raise ValueError('Pitch comparison support outside window')
    selected = next(h for h in hand['hands'] if h['hand_index'] == hand['selected_hand_index'])
    rows = []
    for index, name in TIPS.items():
        pixel = selected['landmarks'][index]['pixel']
        distribution = circle_distribution(pixel, 6., matrix)
        mass = probability_candidates(distribution, board['frets'], board['canvas_size'], samples=16384)
        if distribution['status'] != 'ok':
            rows.append(dict(finger=name, status=distribution['status'], contact='unknown'))
            continue
        line = possible_strings([] if strings is None else strings['strings'],
                                distribution['flat_mean'], board.get('physical_order'))
        hypotheses = []
        # Every string remains available in the broad path. The restricted path is diagnostic only.
        for cell in mass['candidates']:
            if cell['probability'] < .01:
                continue
            fret = cell['fret_num']
            for string, open_midi in TUNING.items():
                midi = open_midi + fret
                matches = audio_matches(midi, audio['fingering_comparison_candidates'])
                hypotheses.append(dict(string_hypothesis=string, physical_fret_candidate=fret,
                                       midi_if_fretted_and_standard_tuning=midi,
                                       spatial_fret_mass=cell['probability'],
                                       within_conditional_line_constraint=string in line['strings'],
                                       audio_matches=matches, contact='unknown',
                                       interpretation='conditional spectral compatibility, not a played note'))
        rows.append(dict(finger=name, landmark_index=index, raw_pixel=pixel,
                         reprojected_flat=distribution['flat_mean'],
                         production_gate=hand.get('location_quality', {}).get(name),
                         radius_95_original_px=6, radius_calibrated=False,
                         nearest_line_diagnostic=line, spatial_frets=mass,
                         hypotheses=hypotheses, contact='unknown'))
    scenarios = joint_string_scenarios([] if strings is None else strings['strings'], rows,
                                      board.get('physical_order'), board['canvas_size'][0])
    return dict(frame_index=hand['frame_index'], frame_pts_s=hand['frame_pts_s'],
                frame_pixel_sha256=hand['frame_pixel_sha256'], fingers=rows,
                joint_string_scenarios=scenarios,
                board_geometry=board['geometry_validity'],
                capo=board.get('capo'), tuning_assumption='unconfirmed standard 6-to-1 EADGBE',
                physical_frets_not_capo_relative=True,
                string_evidence_status='not_provided' if strings is None else strings['status'],
                confirmed_contacts=[], confirmed_guitar_notes=[],
                status='diagnostic_only_geometry_strings_contact_unverified')


def build(output):
    if output.exists():
        raise FileExistsError('Use a new output directory')
    output.mkdir(parents=True)
    hands = [json.loads(line) for line in HAND.read_text().splitlines() if line.strip()]
    fixtures = read(BOARD/'same_frame_fixture.json')['frames']
    string_indices = {f['frame_index'] for f in fixtures if f.get('strings_json')}
    input_paths = {HAND, BOARD/'same_frame_fixture.json'}
    windows = []
    for path in sorted(AUDIO.glob('audio_*.json')):
        audio = read(path); input_paths.add(path)
        hand = select_frame(hands, audio['start_s'], audio['end_s'], string_indices)
        if hand is None:
            window_hands = [h for h in hands if audio['start_s'] <= h['frame_pts_s'] < audio['end_s']]
            windows.append(dict(start_s=audio['start_s'], end_s=audio['end_s'], status='no_selected_hand_in_window',
                                hand_statuses=[dict(frame_index=h['frame_index'], status=h['status']) for h in window_hands]))
            continue
        stem = f"clip003012_f{hand['frame_index']:06d}"
        bp = BOARD/'frames'/f'{stem}_board.json'; board = read(bp); input_paths.add(bp)
        sp = BOARD/'frames'/f'{stem}_strings.json'; strings = read(sp) if sp.exists() else None
        if strings is not None:
            input_paths.add(sp)
        # Verify actual pixels and encoded file separately, without moving observations.
        image = Path(board['image_file'])
        if hashlib.sha256(image.read_bytes()).hexdigest() != board['image_file_sha256']:
            raise ValueError('Image file hash mismatch')
        pixels = cv2.imread(str(image))
        if hashlib.sha256(np.ascontiguousarray(pixels).tobytes()).hexdigest() != hand['frame_pixel_sha256']:
            raise ValueError('Decoded image hash mismatch')
        if strings is None:
            # Reuse the upstream detector on this exact frame; never reuse a neighbor's lines.
            strings, *_ = analyze_saved_board(pixels, board, source_id=hand['source_id'])
            strings['integration_provenance'] = 'fresh_local_call_to_existing_upstream_string_detector'
            strings['geometry_validity'] = board['geometry_validity']
            sp = output/f'{stem}_strings.json'
            sp.write_text(json.dumps(strings, indent=2), encoding='utf-8')
            input_paths.add(sp)
        compared = compare_frame(hand, board, strings, audio)
        harmony = analyze(adapt_audio(audio))
        compared.update(start_s=audio['start_s'], end_s=audio['end_s'], source_id=audio['source_id'],
                        audio_fixture=str(path), board_fixture=str(bp),
                        audio_source_identity=audio['source_identity'],
                        provisional_audio_harmony=harmony.get('provisional_audio_harmony'),
                        audio_pitch_candidates=audio['fingering_comparison_candidates'])
        windows.append(compared)
    evaluation = read(ROOT/'dataset/hand_analysis/runs/frame120_Kim_review_20261103_v3/evaluation.json')
    result = dict(schema_version='joint_compatibility_review.v1', windows=windows,
                  reviewed_frame120_context=dict(frame_pts_s=evaluation['frame_pts_s'],
                     visible_points=evaluation['visible_points'], full_error=evaluation['full_error'],
                     used_as_window_pose=False, reason='PTS5.041667 precedes first audio window; no pose carry-forward'),
                  limitations=['No actual contact, string identity, open/mute status or guitar pitch established',
                               'Spectral compatibility may arise from piano, harmonics or chance',
                               'No agreement is not evidence of mute or a wrong fingering',
                               'One selected frame is not evidence of a stable pose throughout the audio window',
                               'New same-frame string candidates retain upstream detector and identity uncertainty',
                               'Spatial radius and board coordinates are uncalibrated; comparisons are diagnostic only',
                               'No open-string sound inferred from absence of fingers',
                               'Container timeline join does not verify perceptual AV synchronization'])
    (output/'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    summaries = []
    for w in windows:
        fingers = []
        for f in w.get('fingers', []):
            matches = [h for h in f.get('hypotheses', []) if h['audio_matches']]
            fingers.append(dict(finger=f['finger'], top_frets=[(c['fret_num'],round(c['probability'],3))
                           for c in f.get('spatial_frets', {}).get('candidates', [])[:3]],
                           compatible_midis=sorted({h['midi_if_fretted_and_standard_tuning'] for h in matches}),
                           conditional_midis=sorted({h['midi_if_fretted_and_standard_tuning'] for h in matches
                                                    if h['within_conditional_line_constraint']}),
                           nearby_line=f.get('nearest_line_diagnostic')))
        summaries.append(dict(start_s=w['start_s'], end_s=w['end_s'], frame_index=w.get('frame_index'),
                              frame_pts_s=w.get('frame_pts_s'), strings=w.get('string_evidence_status'),
                              status=w.get('status'), hand_statuses=w.get('hand_statuses'), fingers=fingers,
                              joint_string_scenarios=w.get('joint_string_scenarios', [])))
    summary = dict(windows=summaries, confirmed_guitar_notes=0, confirmed_contacts=0,
                   inputs=[dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                           for p in sorted(input_paths)])
    (output/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    lines = ['# 운지·오디오 후보 대조', '', '확정 기타음/접촉 0개. 아래는 표준 튜닝과 미검증 기하를 가정한 주파수 호환성이다.',
             '일치가 실제 기타 발음임을 뜻하지 않는다. 피아노·배음·우연한 일치가 가능하다.', '',
             '|오디오 구간|영상 frame / PTS|현 증거|손가락|공간 프렛 후보(가정 질량)|오디오와 맞는 MIDI 가설|',
             '|---|---|---|---|---|---|']
    for w in summaries:
        if not w['fingers']:
            lines.append(f"|{w['start_s']}–{w['end_s']}|없음|대조 보류|—|{w['status']}|—|")
        for f in w['fingers']:
            lines.append(f"|{w['start_s']}–{w['end_s']}|{w['frame_index']} / {w['frame_pts_s']:.6f}|{w['strings']}|{f['finger']}|{f['top_frets']}|{f['compatible_midis']}|")
    lines += ['', '모든 가설은 손끝의 위치이며 눌림·뮤트·개방·지속 발음으로 해석하지 않는다.',
              '아직 물리 현 번호는 미확정이다. 기본 비교는 여섯 현을 모두 열어둬 우연한 일치 가능성이 크다.',
              '조건부 nearest-line 제약과 근거 ID는 result.json/summary.json에 별도 보존했다.',
              'Kim의 frame120 검수는 시간창 밖이므로 음향 대조에 재사용하지 않고 위치오차 참고로만 보존했다.',
              '최신 semantic 지판을 직접 연결했으며 손 담당의 기존 연결 대기 파일은 수정하지 않았다.',
              '다음은 실제 현·접촉 가설 검증과 시간창 내 자세 변화 점검이다. 이 결과로 정확도 개선을 주장하지 않는다.']
    lines += ['', '## 같은 현 번호 가정을 공유한 공동 대조', '',
              '손가락마다 유리한 현 번호를 독립 선택해 만든 합집합은 실제 운지로 취급하지 않는다. 모든 경우를 보존한다.']
    for w in summaries:
        lines += ['', f"### {w['start_s']}–{w['end_s']}초"]
        for scenario in w['joint_string_scenarios']:
            matches = [(m['finger'], m['string_hypothesis'], m['physical_fret_candidate'], m['midi'])
                       for m in scenario['compatible_finger_hypotheses']]
            lines.append(f"- 선→현 가정 `{scenario['line_to_string_hypothesis']}`: (손가락,현,프렛,MIDI) `{matches}`; 같은 현의 다른 프렛 충돌 `{scenario['same_string_different_fret_collisions']}`")
    (output/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(summaries, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
