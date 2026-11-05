"""Investigate partial strings and missed full-frame fretting hands, offline."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS

import cv2
import numpy as np

from hand_fret_tracker import FretboardGeometry, analyze_result
from joint_evidence_review import ROOT, BOARD, HAND, AUDIO, read, compare_frame
from string_detector import detect_strings
from string_geometry import analyze_saved_board


def roi_candidate(record, board):
    """Fresh same-frame ROI evidence only. Never pick a distant full-frame hand."""
    if record['status'] == 'selected':
        return None, 'original_full_frame_selection_available'
    rois = record['roi_observations']
    if len(rois) != 1:
        return None, 'roi_missing' if not rois else 'roi_ambiguous'
    w, h = board['image_size']
    points = rois[0]['landmarks']
    detection = NS(hand_landmarks=[[NS(x=p['pixel'][0]/w, y=p['pixel'][1]/h, z=0.) for p in points]],
                   handedness=[])
    geometry = FretboardGeometry(board['corners'], board['frets'], *board['canvas_size'])
    result = analyze_result(detection, (h, w, 3), geometry)
    if result['status'] != 'selected':
        return None, 'roi_not_near_current_board'
    candidate = {key: copy.deepcopy(record[key]) for key in
                 ['source_id', 'frame_index', 'frame_pts_s', 'frame_pixel_sha256']}
    candidate.update(status='selected', selected_hand_index=0, hands=result['hands'],
                     location_quality={}, production_status=record['status'],
                     recovery_status='uncorroborated_roi_location_candidate_only',
                     evidence_source='existing_same_frame_independent_roi_inference',
                     original_full_frame_hand_indices=[h['hand_index'] for h in record['hands']],
                     original_roi_hand_index=rois[0]['hand_index'],
                     missing_z=True, synthetic_z_for_2d_adapter_only=True,
                     contact='unknown', confirmed_guitar_notes=[],
                     observation_reused_from_previous_frame=False)
    return candidate, 'same_frame_roi_candidate_near_board'


def padded_strings(raw, board, pad):
    # A local diagnostic, not a replacement or automatic threshold calibration.
    transform = np.array([[2., 0., 0.], [0., 2., pad], [0., 0., 1.]])
    image = cv2.warpPerspective(raw, transform@np.array(board['M']), (1600, 300+2*pad))
    native_width = np.mean([np.linalg.norm(np.array(board['corners'][a])-board['corners'][b])
                            for a, b in [(0, 3), (1, 2)]])
    result = detect_strings(image, [], float(native_width), physical_order=board['physical_order'])
    lines = []
    for original in result['strings']:
        line = copy.deepcopy(original)
        line['b'] = (line['b']-pad)/2
        # Equal 2x scaling in x and y leaves slope unchanged.
        line['observed_intervals'] = [[a/2, b/2] for a, b in line['observed_intervals']]
        line.update(string_num=None, number_source='diagnostic_unverified',
                    padding_diagnostic_px=pad,
                    common_line_equation=dict(m=line['m'], b=line['b']))
        lines.append(line)
    return dict(padding_detector_px=pad, strings=lines,
                detected_count=len(lines), numbering_status='not_confirmed',
                observation_scope='image_supported_candidates_not_independent_ground_truth')


def diagnostics_figure(raw, board, original, variations, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(15, 5.5))
    axes[0].imshow(cv2.cvtColor(raw, cv2.COLOR_BGR2RGB))
    inv = np.array(board['M_inv'])
    for s in original['strings']:
        x = np.linspace(0, 799, 60)
        pts = cv2.perspectiveTransform(np.c_[x, s['m']*x+s['b']][:,None,:], inv)[:,0]
        axes[0].plot(pts[:,0], pts[:,1], lw=.8, label=s['line_id'])
    axes[0].set(xlim=(430,1125), ylim=(310,175), title='Detected line positions on original frame; physical numbers unknown')
    axes[0].legend(ncol=5)
    for v in variations:
        for line in v['strings']:
            x = np.array([0., 799.])
            axes[1].plot(x, line['m']*x+line['b'], lw=.8,
                         label=f"padding={v['padding_detector_px']}px" if line is v['strings'][0] else None)
    axes[1].set(xlim=(0,799), ylim=(170,-20), xlabel='Common flat x', ylabel='Common flat y',
                title='Padding sensitivity: overlapping paths are not independent observations')
    axes[1].legend()
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def main(out):
    if out.exists():
        raise FileExistsError('Use a new output directory')
    out.mkdir(parents=True)
    records = {d['frame_index']: d for d in (json.loads(line) for line in HAND.read_text().splitlines())}
    inputs = {HAND}
    def board_for(idx):
        path = BOARD/'frames'/f'clip003012_f{idx:06d}_board.json'
        inputs.add(path)
        return read(path)
    line_reviews = []
    for idx in [124, 190]:
        board = board_for(idx); raw = cv2.imread(board['image_file'])
        original, *_ = analyze_saved_board(raw, board, source_id=board['source_id'])
        variations = [padded_strings(raw, board, pad) for pad in [20, 30, 40]]
        line_reviews.append(dict(frame_index=idx, original_strings=original,
                                 padding_variations=variations,
                                 physical_string_identity='unresolved',
                                 reason='five-line family and edge-sensitive additional lines do not establish six identities'))
        diagnostics_figure(raw, board, original, variations, out/f'frame_{idx}_string_diagnostic.png')
    recovered = []; diagnosis = []
    for idx in range(209, 217):
        record = records[idx]; board = board_for(idx)
        candidate, reason = roi_candidate(record, board)
        diagnosis.append(dict(frame_index=idx, frame_pts_s=record['frame_pts_s'],
                              full_status=record['status'], full_hands=len(record['hands']),
                              full_wrist_pixels=[h['landmarks'][0]['pixel'] for h in record['hands']],
                              roi_hands=len(record['roi_observations']), recovery_reason=reason,
                              causal_interpretation='full-frame fretting-hand miss' if candidate else 'no valid ROI recovery'))
        if candidate:
            recovered.append(candidate)
    (out/'roi_candidate_observations.json').write_text(json.dumps(recovered, indent=2), encoding='utf-8')
    audio_path = AUDIO/'audio_8.75_9.05.json'; audio = read(audio_path); inputs.add(audio_path)
    comparisons = []
    for candidate in recovered:
        board = board_for(candidate['frame_index'])
        raw = cv2.imread(board['image_file'])
        if hashlib.sha256(np.ascontiguousarray(raw).tobytes()).hexdigest() != candidate['frame_pixel_sha256']:
            raise ValueError('Recovery pixel identity mismatch')
        strings, *_ = analyze_saved_board(raw, board, source_id=board['source_id'])
        comparison = compare_frame(candidate, board, strings, audio)
        comparison['recovery_status'] = candidate['recovery_status']
        comparison['production_status_unchanged'] = candidate['production_status']
        comparisons.append(comparison)
    summary = dict(full_frame_selected=0, frames=8, roi_candidates=len(recovered),
                   no_roi=8-len(recovered), confirmed_contacts=0, confirmed_guitar_notes=0,
                   production_selection_modified=False,
                   frames_diagnosis=diagnosis,
                   limitations=['ROI model was worse on Kim frame120; this is not validated recovery',
                                'Board geometry, physical strings, contact and perceptual AV sync remain unverified',
                                'User score/TAB references were not used as detector or matching inputs'])
    if recovered:
        points = np.array([[p['pixel'] for p in r['hands'][0]['landmarks']] for r in recovered])
        center = np.median(points, axis=0)
        summary['roi_temporal_diagnostics'] = [dict(frame_index=r['frame_index'],
            median_fingertip_deviation_from_clip_median_px=float(np.median(
                np.linalg.norm(p[[8,12,16,20]]-center[[8,12,16,20]], axis=1))),
            max_landmark_deviation_px=float(np.max(np.linalg.norm(p-center, axis=1))),
            interpretation='observed variability, not ground-truth error or pure detector jitter')
            for r, p in zip(recovered, points)]
    concise = []
    for c in comparisons:
        best = max(c['joint_string_scenarios'],
                   key=lambda s: len({m['finger'] for m in s['compatible_finger_hypotheses']}), default=None)
        # This maximum is only a diagnostic; do not choose the true mapping using audio fit.
        concise.append(dict(frame_index=c['frame_index'], frame_pts_s=c['frame_pts_s'],
                            production_status=c['production_status_unchanged'],
                            roi_status=c['recovery_status'],
                            hypothetical_mapping_count=len(c['joint_string_scenarios']),
                            max_compatible_fingers_under_one_mapping=0 if best is None else
                            len({m['finger'] for m in best['compatible_finger_hypotheses']}),
                            best_compatibility_is_not_mapping_confirmation=True))
    result = dict(summary=summary, string_reviews=line_reviews,
                  roi_audio_comparisons=comparisons, concise_comparisons=concise,
                  inputs=[dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(inputs)])
    (out/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    lines = ['# 현 대응·손 선택 실패 진단', '',
             '원시 관측을 보존하고 동일 프레임 ROI의 별도 후보를 비교했다. 확정 접촉·확정 기타 음은0개다.', '',
             f"ROI candidate recovery: {len(recovered)}/8; production selection remains unchanged.", '',
             '|frame|PTS|full status|ROI candidate|', '|---|---|---|---|']
    for d in diagnosis:
        lines.append(f"|{d['frame_index']}|{d['frame_pts_s']:.6f}|{d['full_status']}|{d['recovery_reason']}|")
    lines += ['', '## 해석', '',
              '- 전체 화면은 지판 쪽 손을 놓치고 반대편 피킹 손만 검출했으며, 210번은 손 자체가 미검출됐다.',
              '- 같은 프레임 ROI는7개에서 지판 근처 손 후보를 제공했다. 212번은 ROI도 없어 복구하지 않았다.',
              '- ROI 후보의 좌표·출처를 별도 보존하고 기존 production 실패 상태는 변경하지 않았다.',
              '- ROI는 기존 Kim 검수에서 오차가 더 컸다. 후보 증가를 정확도 향상이나 접촉 복구로 보고하지 않는다.',
              '- 현 padding에 따라 가장자리 추가 선이 나타나거나 사라진다. 6개가 나왔다는 이유만으로6현 정답으로 승격하지 않는다.',
              '- 3번째 창도 같은 프레임 손·지판·현·음향 후보를 이제 진단 비교할 수 있다. 실제 현 번호와 접촉은 계속 unknown이다.',
              '- 창 중앙값에 대한 좌표 변동은 실제 움직임을 포함하므로 순수 지터/위치오차로 부르지 않는다.']
    (out/'diagnosis.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(dict(summary=summary, comparisons=concise,
                         string_counts=[dict(frame_index=r['frame_index'], baseline=len(r['original_strings']['strings']),
                                             padded=[v['detected_count'] for v in r['padding_variations']]) for r in line_reviews]),
                     indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
