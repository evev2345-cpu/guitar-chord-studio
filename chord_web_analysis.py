"""Web-facing adapter for the offline audio pipeline, without labels."""
import json
from pathlib import Path
import numpy as np
from harmony_engine import NAMES, SUFFIX, TEMPLATES, rank_saliences, pooled_chroma
from chord_display_cleanup import stabilize
from harmonic_context import enrich, key_hypotheses, bass_track, CONFIG
from chord_presentation import prepare, CONFIG as PRESENTATION_CONFIG
from onset_transition import add_layer
from beat_grid import estimate_tempo_and_phase

ROOT = Path(__file__).resolve().parent


def predictions(grid, frames, queries, width):
    valid = (queries - width / 2 >= grid[0]) & (queries + width / 2 <= grid[-1])
    sal = np.zeros((len(queries), 12))
    if np.any(valid):
        sal[valid] = pooled_chroma(grid, frames, queries[valid], width)
    scores, order, usable = rank_saliences(sal)
    rows = []
    for i in range(len(queries)):
        top = (
            [
                dict(
                    TEMPLATES[j],
                    score=float(scores[i, j]),
                    capo1_shape=NAMES[(TEMPLATES[j]['root_pc'] - 1) % 12] + SUFFIX.get(TEMPLATES[j]['quality'], TEMPLATES[j]['quality']),
                )
                for j in order[i, :3]
            ]
            if usable[i]
            else []
        )
        ties = int(np.isclose(scores[i], scores[i, order[i, 0]], atol=1e-10, rtol=0).sum()) if usable[i] else 0
        rows.append(
            dict(
                top3=top,
                tied_top1_count=ties,
                status='audio_edge_no_full_window' if not valid[i] else 'provisional' if usable[i] else 'insufficient_note_evidence',
            )
        )
    return rows


def make_timeline(prediction, duration, full_mix_prediction=None):
    # Keep the existing 24Hz cleanup semantics; do not change thresholds for UI.
    times = np.arange(0, duration, 1 / 24)
    pred_path = Path(prediction)
    if full_mix_prediction is None and (pred_path.parent / 'full_mix_raw.npz').exists() and pred_path.name != 'full_mix_raw.npz':
        full_mix_prediction = pred_path.parent / 'full_mix_raw.npz'

    with np.load(prediction) as data:
        key=key_hypotheses(data['note'],duration)
        bass=bass_track(data['times'],data['note'],times)
        onsets_arr=data['onset'] if 'onset' in data else None
        tempo=estimate_tempo_and_phase(data['times'],data['note'],onsets_arr)

        full_mix_ctx = None
        if full_mix_prediction and Path(full_mix_prediction).exists():
            with np.load(full_mix_prediction) as fm_data:
                fm_key = key_hypotheses(fm_data['note'], duration)
                fm_bass = bass_track(fm_data['times'], fm_data['note'], times)
                full_mix_ctx = dict(
                    key=fm_key,
                    bass=fm_bass,
                    grid=fm_data['times'].copy(),
                    frames=fm_data['note'].copy()
                )

        branches = {}
        for width in (.2, .4):
            raw = predictions(data['times'], data['note'], times, width)
            display = stabilize(times, raw)
            if full_mix_ctx is not None:
                fm_raw = predictions(full_mix_ctx['grid'], full_mix_ctx['frames'], times, width)
                fm_width = dict(
                    key=full_mix_ctx['key'],
                    bass=full_mix_ctx['bass'],
                    raw=fm_raw,
                    grid=full_mix_ctx['grid'],
                    frames=full_mix_ctx['frames']
                )
            else:
                fm_width = None
            context=enrich(data['times'],data['note'],times,width,raw,display,key,bass,full_mix=fm_width)
            branches[str(width)] = [dict(time_s=float(t), **r, display=d, context=c)
                                   for t, r, d, c in zip(times, raw, display, context)]
            presentation=prepare(times,branches[str(width)],tempo=tempo)
            for row,shown in zip(branches[str(width)],presentation):row['presentation']=shown
        grid=data['times'].copy();notes=data['note'].copy();onsets=data['onset'].copy() if 'onset' in data else None
    result=dict(schema_version='chord_web.v3', duration_s=duration, branches=branches,
                tempo=tempo,
                full_mix_anchor_available=bool(full_mix_ctx is not None),
                presentation_config=PRESENTATION_CONFIG,
                harmonic_context=dict(key=key,config=CONFIG,bass_attribution='unknown',
                                      full_mix_key=full_mix_ctx['key'] if full_mix_ctx else None),
                engine='Basic Pitch ONNX · dual-track mix anchor · max pooling · coverage scorer',
                analysis_mode='offline_audio_dual_track' if full_mix_ctx else 'offline_audio_only',
                vision_connected=False,
                score_type='ranking_score_not_probability',
                limitations=['근거가 약한 동점은 원곡 화성 앵커 및 복수 후보로 표시합니다. 저음·진행 가점은 확정 근거가 아닙니다.',
                             '분수코드의 저음은 모델 추정이며 기타와 베이스 기타를 구분하지 못합니다.', '손·지판 비전은 아직 웹 분석에 연결하지 않았습니다.',
                             '입력 악기 분리는 자동 실행하지 않습니다. 기타 분리음 입력을 권장합니다.',
                             '중앙 시간창과 앞뒤 표시 정리를 사용하는 사전 분석입니다.'])
    return add_layer(result,grid,notes,onsets)


def write_result(directory, duration):
    directory = Path(directory)
    fm_pred = directory / 'prediction' / 'full_mix_raw.npz'
    result = make_timeline(directory / 'prediction' / 'upload_raw.npz', duration, full_mix_prediction=fm_pred if fm_pred.exists() else None)
    (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result
