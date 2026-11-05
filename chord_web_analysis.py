"""Web-facing adapter for the existing offline audio pipeline, without labels."""
import json
from pathlib import Path
import numpy as np
from render_audio_video_review import predictions
from chord_display_cleanup import stabilize

ROOT = Path(__file__).resolve().parent


def make_timeline(prediction, duration):
    # Keep the existing 24Hz cleanup semantics; do not change thresholds for UI.
    times = np.arange(0, duration, 1 / 24)
    with np.load(prediction) as data:
        branches = {}
        for width in (.2, .4):
            raw = predictions(data['times'], data['note'], times, width)
            display = stabilize(times, raw)
            branches[str(width)] = [dict(time_s=float(t), **r, display=d)
                                   for t, r, d in zip(times, raw, display)]
    return dict(schema_version='chord_web.v1', duration_s=duration, branches=branches,
                engine='Basic Pitch ONNX · max pooling · existing coverage scorer',
                analysis_mode='offline_audio_only', vision_connected=False,
                score_type='ranking_score_not_probability',
                limitations=['동점은 복수 후보로 표시합니다.', '손·지판 비전은 아직 웹 분석에 연결하지 않았습니다.',
                             '입력 악기 분리는 자동 실행하지 않습니다. 기타 분리음 입력을 권장합니다.',
                             '중앙 시간창과 앞뒤 표시 정리를 사용하는 사전 분석입니다.'])


def write_result(directory, duration):
    result = make_timeline(directory / 'prediction' / 'upload_raw.npz', duration)
    (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result
