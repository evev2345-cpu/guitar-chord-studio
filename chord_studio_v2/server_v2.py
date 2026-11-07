"""Chord Studio v2 (Pre-deployment Verification Edition) — Standalone separated server.

Features:
1. Completely isolated from v1 (`chord_studio_v2/runs`, default port 8766).
2. Full-song guitar stem separation (`htdemucs_6s`) enabled by default on upload (with graceful fallback).
3. Interactive chord segment editing (`POST /api/jobs/<id>/edit`) persisted to `result.json`.
4. User-driven 4-point fretboard calibration (`POST /api/jobs/<id>/calibrate`) without external APIs.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid
import wave
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT / 'bin'
if BIN_DIR.exists():
    os.environ['PATH'] = str(BIN_DIR) + os.pathsep + os.environ.get('PATH', '')
ENGINE_DIR = ROOT / 'engine'
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from chord_web_analysis import write_result
from harmony_engine import NAMES, QUALITIES, SUFFIX

V2_ROOT = Path(__file__).resolve().parent
STATIC = V2_ROOT / 'static'
RUNS = V2_ROOT / 'runs'
PROFILES = V2_ROOT / 'vision_profiles'


def _resolve_python(venv_name):
    for candidate in (
        ROOT / venv_name / 'Scripts' / 'python.exe',
        ROOT / venv_name / 'bin' / 'python',
    ):
        if candidate.exists():
            return candidate
    if sys.executable and Path(sys.executable).name.lower().startswith('python'):
        return Path(sys.executable)
    return None


MODEL_PYTHON = _resolve_python('.venv-audio-model')
SEPARATION_PYTHON = _resolve_python('.venv-audio-separation')
HAS_SEPARATION_ENV = (
    SEPARATION_PYTHON is not None
    and Path(SEPARATION_PYTHON).exists()
    and Path(SEPARATION_PYTHON).name.lower().startswith('python')
)

MAX_BYTES = 2048 * 1024 * 1024  # 2GB
MAX_SECONDS = None  # 길이 제한 없음
POOL = ThreadPoolExecutor(max_workers=1)
LOCK = threading.RLock()
JOBS = {}


def save_state(job_id, **fields):
    with LOCK:
        JOBS[job_id].update(fields)
        (RUNS / job_id / 'job.json').write_text(
            json.dumps(JOBS[job_id], ensure_ascii=False), encoding='utf-8'
        )


def run_cmd(command, log):
    with log.open('ab') as out:
        subprocess.run(
            [str(v) for v in command],
            cwd=ROOT,
            stdout=out,
            stderr=out,
            check=True,
            timeout=1800,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )


def build_calibration_from_4corners(video_path, time_s, corners, capo_candidate=0, total_frets=20, perspective_k=0.0):
    """Build a source-specific calibration dictionary from 4 user-clicked fretboard corners.

    Corner order:
      0: Nut top (6th string at nut)
      1: Last-fret / fretboard-end top (6th string)
      2: Last-fret / fretboard-end bottom (1st string)
      3: Nut bottom (1st string at nut)
    """
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(video_path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
    ref_frame = max(0, min(count - 1, int(round(float(time_s) * fps))))
    cap.set(cv2.CAP_PROP_POS_FRAMES, ref_frame)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise ValueError('기준 프레임을 영상에서 읽지 못했습니다.')

    h, w = frame.shape[:2]
    c = np.asarray(corners, dtype=float)
    if c.shape != (4, 2):
        raise ValueError('지판 모서리 4점 좌표가 필요합니다.')

    total_frets = max(12, min(24, int(total_frets or 20)))
    denom = 1.0 - 2.0 ** (-total_frets / 12.0)
    k = float(np.clip(float(perspective_k or 0.0), -0.8, 0.8))
    # Fret positions 0..total_frets using 12-TET spacing warped by projective perspective k:
    frets = []
    for n in range(min(13, total_frets + 1)):
        un = float((1.0 - 2.0 ** (-n / 12.0)) / denom)
        ratio = float((1.0 + k) * un / (1.0 + k * un)) if un < 1.0 else 1.0
        top_pt = (1.0 - ratio) * c[0] + ratio * c[1]
        bot_pt = (1.0 - ratio) * c[3] + ratio * c[2]
        frets.append(
            {
                'number': int(n),
                'endpoints': [
                    [round(float(top_pt[0]), 1), round(float(top_pt[1]), 1)],
                    [round(float(bot_pt[0]), 1), round(float(bot_pt[1]), 1)],
                ],
            }
        )

    # Inset texture polygon inside the neck for optical flow feature tracking
    tex_top_left = 0.92 * c[1] + 0.08 * c[0] + 0.12 * (c[2] - c[1])
    tex_top_right = 0.35 * c[1] + 0.65 * c[0] + 0.12 * (c[3] - c[0])
    tex_bot_right = 0.35 * c[2] + 0.65 * c[3] - 0.12 * (c[3] - c[0])
    tex_bot_left = 0.92 * c[2] + 0.08 * c[3] - 0.12 * (c[2] - c[1])
    texture_polygon = [
        [int(round(tex_top_left[0])), int(round(tex_top_left[1]))],
        [int(round(tex_top_right[0])), int(round(tex_top_right[1]))],
        [int(round(tex_bot_right[0])), int(round(tex_bot_right[1]))],
        [int(round(tex_bot_left[0])), int(round(tex_bot_left[1]))],
    ]

    return {
        'reference_frame': int(ref_frame),
        'reference_pixel_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
        'image_size': [int(w), int(h)],
        'corners': [[round(float(pt[0]), 1), round(float(pt[1]), 1)] for pt in c],
        'texture_polygon': texture_polygon,
        'frets': frets,
        'capo_candidate': int(capo_candidate),
        'total_frets': int(total_frets),
        'perspective_k': float(k),
        'geometry_status': 'user_manual_4point_provisional',
        'physical_strings_verified': False,
        'tuning': 'assumed_standard',
        'source': 'User interactive 4-corner fretboard calibration in Chord Studio v2',
        'fps': fps,
    }


def apply_chord_edit_to_result(result_path, window_key, start_s, end_s, root_pc, quality, bass_pc=None):
    """Apply a user chord edit across [start_s, end_s] in result.json and persist it."""
    if quality not in QUALITIES:
        raise ValueError(f'지원하지 않는 코드 종류입니다: {quality}')
    root_pc = int(root_pc) % 12
    bass_pc = int(bass_pc) % 12 if bass_pc is not None and bass_pc != '' else None
    pcs = sorted({(root_pc + i) % 12 for i in QUALITIES[quality]})
    base_symbol = NAMES[root_pc] + SUFFIX.get(quality, quality)
    symbol = base_symbol + ('/' + NAMES[bass_pc] if bass_pc is not None and bass_pc != root_pc else '')

    custom_cand = {
        'root_pc': root_pc,
        'quality': quality,
        'pcs': pcs,
        'base_symbol': base_symbol,
        'symbol': symbol,
        'bass_pc': bass_pc,
        'score': 1.0,
        'adjusted_score': 1.0,
        'bass_display_status': 'user_edited_slash' if (bass_pc is not None and bass_pc != root_pc) else 'user_edited',
        'user_edited': True,
    }

    data = json.loads(result_path.read_text(encoding='utf-8'))
    target_branches = [window_key] if window_key in data.get('branches', {}) else list(data.get('branches', {}).keys())
    edited_frames = 0
    for b_key in target_branches:
        rows = data['branches'][b_key]
        for row in rows:
            t = float(row.get('time_s', 0.0))
            if start_s - 1e-4 <= t < end_s - 1e-4:
                edited_frames += 1
                for pres_key in ('presentation', 'onset_presentation', 'vision_presentation', 'vision_onset_presentation'):
                    if pres_key in row and isinstance(row[pres_key], dict):
                        row[pres_key]['display_candidates'] = [copy.deepcopy(custom_cand)]
                        row[pres_key]['frame_display_candidates'] = [copy.deepcopy(custom_cand)]
                        row[pres_key]['status'] = 'user_edited_segment'
                if 'context' in row and isinstance(row['context'], dict):
                    row['context']['display_candidates'] = [copy.deepcopy(custom_cand)]
                    row['context']['status'] = 'user_edited_segment'

    if edited_frames == 0:
        raise ValueError('지정한 시간 구간에 해당하는 분석 프레임을 찾지 못했습니다.')

    edits = data.setdefault('user_edits', [])
    edits.append(
        {
            'window': str(window_key),
            'start_s': round(float(start_s), 4),
            'end_s': round(float(end_s), 4),
            'symbol': symbol,
            'root_pc': root_pc,
            'quality': quality,
            'bass_pc': bass_pc,
            'updated_at': time.time(),
        }
    )
    result_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return {'edited_frames': edited_frames, 'candidate': custom_cand, 'total_edits': len(edits)}


def analyze(job_id, demo=False, separate_guitar=True):
    directory = RUNS / job_id
    log = directory / 'analysis.log'
    try:
        save_state(job_id, status='running', progress=8, message='미디어 확인 중')
        extra = {}
        if demo:
            prediction = ROOT / 'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions/tutorial_raw.npz'
            audio = ROOT / 'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav'
            (directory / 'prediction').mkdir(exist_ok=True)
            shutil.copyfile(prediction, directory / 'prediction/upload_raw.npz')
            shutil.copyfile(audio, directory / 'media.wav')
            shutil.copyfile(audio, directory / 'guitar.wav')
            duration = 32.0
            media = 'media.wav'
            extra['guitar_audio_url'] = f'/media/{job_id}/guitar.wav'
            extra['separation_status'] = 'separated_htdemucs_6s'
            save_state(job_id, progress=80, message='분리된 기타 트랙 분석 결과를 불러오는 중')
        else:
            source = directory / 'input.bin'
            probe = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(source)],
                capture_output=True,
                check=True,
                timeout=30,
            )
            info = json.loads(probe.stdout)
            reported = info.get('format', {}).get('duration')
            duration = float(reported) if reported not in (None, 'N/A') else None
            if duration is not None and duration < 0.5:
                raise ValueError('0.5초 이상의 파일을 지원합니다.')
            if not any(s['codec_type'] == 'audio' for s in info['streams']):
                raise ValueError('오디오 트랙이 없는 파일입니다.')
            save_state(job_id, progress=18, message='오디오 추출 중')
            run_cmd(
                [
                    'ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', source,
                    '-map', '0:a:0', '-vn',
                    '-ac', '1', '-ar', '22050', '-c:a', 'pcm_s16le', directory / 'audio.wav',
                ],
                log,
            )
            with wave.open(str(directory / 'audio.wav'), 'rb') as wf:
                duration = wf.getnframes() / wf.getframerate()
            if duration < 0.5:
                raise ValueError('0.5초 이상의 파일을 지원합니다.')

            if any(
                s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')
                for s in info['streams']
            ):
                save_state(job_id, progress=28, message='브라우저 재생용 영상 준비 중')
                run_cmd(
                    [
                        'ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', source,
                        '-map', '0:v:0', '-map', '0:a:0',
                        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart',
                        directory / 'media.mp4',
                    ],
                    log,
                )
                media = 'media.mp4'
            else:
                shutil.copyfile(directory / 'audio.wav', directory / 'media.wav')
                media = 'media.wav'

            analysis_audio = directory / 'audio.wav'
            if separate_guitar and HAS_SEPARATION_ENV:
                try:
                    save_state(job_id, progress=36, message='전체 음원에서 기타 트랙 분리 중')
                    run_cmd(
                        [
                            SEPARATION_PYTHON,
                            ENGINE_DIR / 'run_local_separation.py',
                            '--input', analysis_audio,
                            '--model', 'htdemucs_6s',
                            '--stem', 'guitar',
                            '--output', directory / 'separation',
                        ],
                        log,
                    )
                    separated_wav = directory / 'separation/htdemucs_6s/audio/guitar.wav'
                    if separated_wav.exists():
                        shutil.copyfile(separated_wav, directory / 'guitar.wav')
                        analysis_audio = directory / 'guitar.wav'
                        extra['guitar_audio_url'] = f'/media/{job_id}/guitar.wav'
                        extra['separation_status'] = 'separated_htdemucs_6s'
                    else:
                        extra['separation_status'] = 'fallback_original_audio'
                except Exception as sep_err:
                    with log.open('a', encoding='utf-8') as f:
                        f.write('\nSeparation fallback: ' + repr(sep_err))
                    extra['separation_status'] = 'fallback_original_audio'
            else:
                extra['separation_status'] = 'original_audio_mode'

            tasks = [dict(id='upload', audio=str(analysis_audio))]
            if (directory / 'audio.wav').exists() and str(analysis_audio) != str(directory / 'audio.wav'):
                tasks.append(dict(id='full_mix', audio=str(directory / 'audio.wav')))
            (directory / 'tasks.json').write_text(json.dumps(tasks), encoding='utf-8')
            save_state(job_id, progress=55, message='Basic Pitch 오디오 모델로 음 후보 분석 중')
            try:
                from basic_pitch_worker import run_basic_pitch_tasks
                with log.open('a', encoding='utf-8') as f:
                    f.write('\n[In-process Basic Pitch analysis started]\n')
                run_basic_pitch_tasks(
                    directory / 'tasks.json',
                    directory / 'prediction',
                    modes=['raw'],
                )
                with log.open('a', encoding='utf-8') as f:
                    f.write('[In-process Basic Pitch analysis completed]\n')
            except Exception as bp_err:
                with log.open('a', encoding='utf-8') as f:
                    f.write(f'\n[In-process Basic Pitch failed: {bp_err!r}], trying fallback...\n')
                if MODEL_PYTHON and Path(MODEL_PYTHON).exists() and Path(MODEL_PYTHON).name.lower().startswith('python'):
                    run_cmd(
                        [
                            MODEL_PYTHON,
                            ENGINE_DIR / 'basic_pitch_worker.py',
                            '--tasks', directory / 'tasks.json',
                            '--output', directory / 'prediction',
                            '--modes', 'raw',
                        ],
                        log,
                    )
                else:
                    raise bp_err
            save_state(job_id, progress=85, message='16박자 격자 및 코드 진행 정돈 중')

        write_result(directory, duration)
        if media == 'media.mp4':
            extra['vision_status'] = 'user_calibration_ready'
        save_state(
            job_id,
            status='complete',
            progress=100,
            message='분석 완료',
            duration_s=duration,
            media_url=f'/media/{job_id}/{media}',
            result_url=f'/api/jobs/{job_id}/result',
            **extra,
        )
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else '분석에 실패했습니다. 파일 형식과 서버 로그를 확인해 주세요.'
        with log.open('a', encoding='utf-8') as f:
            f.write('\n' + repr(exc))
        save_state(job_id, status='error', message=message)


def run_user_calibration_job(job_id, time_s, corners, capo_candidate=0, total_frets=20, perspective_k=0.0):
    directory = RUNS / job_id
    log = directory / 'analysis.log'
    video_path = directory / 'media.mp4'
    if not video_path.exists():
        raise ValueError('영상 파일(media.mp4)이 있는 분석에서만 지판 직접 지정이 가능합니다.')
    PROFILES.mkdir(parents=True, exist_ok=True)
    calibration = build_calibration_from_4corners(
        video_path, time_s, corners, capo_candidate=capo_candidate, total_frets=total_frets, perspective_k=perspective_k
    )
    profile_path = directory / 'user_calibration.json'
    profile_path.write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding='utf-8')
    save_state(job_id, user_calibration=calibration)

    # Automatically archive user 4-point calibration frame and coordinates for future AI training
    try:
        fret_dir = V2_ROOT / 'fretboard_data'
        (fret_dir / 'frames').mkdir(parents=True, exist_ok=True)
        (fret_dir / 'annotations').mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        item_name = f'fret_{ts}_{job_id[:8]}'
        annot = {
            'job_id': job_id,
            'timestamp': ts,
            'time_s': float(time_s),
            'corners': corners,
            'total_frets': int(total_frets),
            'capo': int(capo_candidate),
            'perspective_k': float(perspective_k),
            'image_size': calibration.get('image_size'),
            'reference_frame': calibration.get('reference_frame'),
            'reference_pixel_sha256': calibration.get('reference_pixel_sha256'),
        }
        (fret_dir / 'annotations' / f'{item_name}.json').write_text(json.dumps(annot, ensure_ascii=False, indent=2), encoding='utf-8')
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, calibration.get('reference_frame', 0))
        ok, frame = cap.read()
        cap.release()
        if ok and frame is not None:
            cv2.imwrite(str(fret_dir / 'frames' / f'{item_name}.jpg'), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    except Exception:
        pass

    def _worker():
        try:
            save_state(job_id, vision_status='calibrating', message='사용자 지정 지판으로 비전 추적 중')
            vision_dir = directory / f'vision_user_{int(time.time())}'
            try:
                from web_vision_worker import run as run_vision
                with log.open('a', encoding='utf-8') as f:
                    f.write('\n[In-process Vision tracking started]\n')
                cal_data = json.loads(profile_path.read_text(encoding='utf-8'))
                run_vision(video_path, cal_data, vision_dir)
                with log.open('a', encoding='utf-8') as f:
                    f.write('[In-process Vision tracking completed]\n')
            except Exception as vis_err:
                with log.open('a', encoding='utf-8') as f:
                    f.write(f'\n[In-process Vision tracking failed: {vis_err!r}], trying fallback...\n')
                if sys.executable and Path(sys.executable).name.lower().startswith('python'):
                    run_cmd(
                        [
                            sys.executable,
                            ENGINE_DIR / 'web_vision_worker.py',
                            '--video', video_path,
                            '--calibration', profile_path,
                            '--output', vision_dir,
                        ],
                        log,
                    )
                else:
                    raise vis_err
            from attach_web_vision import attach
            attach(directory, vision_dir)
            save_state(
                job_id,
                status='complete',
                progress=100,
                message='사용자 지판 비전 반영 완료',
                vision_url=f'/api/jobs/{job_id}/vision',
                vision_status='user_calibrated_active',
            )
        except Exception as err:
            with log.open('a', encoding='utf-8') as f:
                f.write('\nUser calibration vision fallback: ' + repr(err))
            save_state(
                job_id,
                status='complete',
                progress=100,
                message='지판 좌표 저장 완료 (비전 추적 생략 · 오디오 유지)',
                vision_status='calibration_saved_audio_preserved',
            )

    POOL.submit(_worker)
    return calibration


def range_bounds(value, size):
    if value is None:
        return 0, size - 1, False
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
    if not match or not any(match.groups()):
        raise ValueError('Invalid range')
    first, last = match.groups()
    if not first:
        if int(last) <= 0:
            raise ValueError('Invalid suffix')
        start, end = max(0, size - int(last)), size - 1
    else:
        start, end = int(first), min(int(last) if last else size - 1, size - 1)
    if start >= size or end < start:
        raise ValueError('Unsatisfiable range')
    return start, end, True


class HandlerV2(BaseHTTPRequestHandler):
    def allowed(self):
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        host_only = host.split(':')[0]
        if getattr(self.server, 'allow_public', False) or host_only.endswith('.trycloudflare.com') or host_only.endswith('.loca.lt'):
            origin_host = urlsplit(origin).hostname if origin else None
            return bool(host_only) and (
                origin is None
                or origin_host == host_only
                or (origin_host and (origin_host.endswith('.trycloudflare.com') or origin_host.endswith('.loca.lt') or origin_host == 'huggingface.co' or origin_host.endswith('.hf.space')))
            )
        expected = f'127.0.0.1:{self.server.server_port}'
        return host in (expected, f'localhost:{self.server.server_port}') and (
            origin is None or origin == 'http://' + host
        )

    def json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def file(self, path):
        if not path.is_file():
            return self.json(dict(error='파일을 찾을 수 없습니다.'), 404)
        size = path.stat().st_size
        try:
            start, end, partial = range_bounds(self.headers.get('Range'), size)
        except ValueError:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        with path.open('rb') as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self):
        if not self.allowed():
            return self.json(dict(error='허용되지 않은 주소입니다.'), 403)
        path = urlsplit(self.path).path
        static_map = {
            '/': 'index.html',
            '/app.js': 'app.js',
            '/style.css': 'style.css',
            '/favicon.ico': 'favicon.ico',
            '/icon.png': 'icon.png',
            '/legacy': 'index_legacy.html',
            '/app_legacy.js': 'app_legacy.js',
            '/style_legacy.css': 'style_legacy.css',
        }
        if path in static_map:
            return self.file(STATIC / static_map[path])
        if path == '/api/jobs':
            client_id = self.headers.get('X-Client-Id')
            with LOCK:
                visible_jobs = [
                    j for j in JOBS.values()
                    if (client_id and j.get('client_id') == client_id) or j.get('is_demo') or j.get('demo')
                ]
                return self.json(visible_jobs)
        match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})(/result|/vision)?', path)
        if match:
            with LOCK:
                job = JOBS.get(match[1])
                if job is None:
                    return self.json(dict(error='분석을 찾을 수 없습니다.'), 404)
                if not match[2]:
                    return self.json(dict(job))
                if job['status'] != 'complete':
                    return self.json(dict(error='분석이 아직 완료되지 않았습니다.'), 409)
            return self.file(
                RUNS / match[1] / ('vision_overlay.json' if match[2] == '/vision' else 'result.json')
            )
        match = re.fullmatch(r'/media/([a-f0-9]{32})/((?:media|guitar)\.(?:wav|mp4))', path)
        if match:
            return self.file(RUNS / match[1] / match[2])
        return self.json(dict(error='경로를 찾을 수 없습니다.'), 404)

    def do_POST(self):
        url = urlsplit(self.path)
        if not self.allowed():
            self.close_connection = True
            return self.json(dict(error='허용되지 않은 요청입니다.'), 403)

        edit_match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})/edit', url.path)
        if edit_match:
            job_id = edit_match.group(1)
            with LOCK:
                if job_id not in JOBS:
                    return self.json(dict(error='분석을 찾을 수 없습니다.'), 404)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
                res = apply_chord_edit_to_result(
                    RUNS / job_id / 'result.json',
                    window_key=str(payload.get('window', '0.2')),
                    start_s=float(payload['start_s']),
                    end_s=float(payload['end_s']),
                    root_pc=int(payload['root_pc']),
                    quality=str(payload['quality']),
                    bass_pc=payload.get('bass_pc'),
                )
                return self.json(res, 200)
            except Exception as err:
                return self.json(dict(error=str(err)), 400)

        cal_match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})/calibrate', url.path)
        if cal_match:
            job_id = cal_match.group(1)
            with LOCK:
                if job_id not in JOBS:
                    return self.json(dict(error='분석을 찾을 수 없습니다.'), 404)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
                cal = run_user_calibration_job(
                    job_id,
                    time_s=float(payload.get('time_s', 0.0)),
                    corners=payload['corners'],
                    capo_candidate=int(payload.get('capo', 0)),
                    total_frets=int(payload.get('total_frets', 20)),
                    perspective_k=float(payload.get('perspective_k', 0.0)),
                )
                return self.json(dict(status='calibration_queued', calibration=cal), 202)
            except Exception as err:
                return self.json(dict(error=str(err)), 400)

        if url.path not in ('/api/jobs', '/api/demo'):
            self.close_connection = True
            return self.json(dict(error='경로를 찾을 수 없습니다.'), 404)
        demo = url.path == '/api/demo'
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = -1
        if (not demo and not 0 < length <= MAX_BYTES) or (demo and length != 0):
            self.close_connection = True
            return self.json(dict(error='2GB 이하의 파일을 선택해 주세요.'), 413)
        params = parse_qs(url.query)
        client_id = self.headers.get('X-Client-Id') or params.get('client_id', [None])[0]
        separate_guitar = params.get('separate', ['1'])[0] != '0'
        with LOCK:
            if sum(j['status'] in ('uploading', 'queued', 'running') for j in JOBS.values()) >= 4:
                self.close_connection = True
                return self.json(dict(error='분석 대기열이 가득 찼습니다. 잠시 후 시도해 주세요.'), 429)
            job_id = uuid.uuid4().hex
            directory = RUNS / job_id
            directory.mkdir(parents=True)
            name = params.get('name', ['업로드 파일'])[0][:160]
            JOBS[job_id] = dict(
                id=job_id,
                name='튜토리얼 · 기타 분리음 (3:14–3:46)' if demo else name,
                created_at=time.time(),
                status='uploading',
                progress=0,
                message='업로드 중',
                demo=demo,
                is_demo=demo,
                client_id=client_id,
                separate_guitar=separate_guitar,
            )
        if not demo:
            try:
                self.connection.settimeout(60)
                with (directory / 'input.bin').open('wb') as target:
                    while length:
                        chunk = self.rfile.read(min(length, 1024 * 1024))
                        if not chunk:
                            raise ValueError('Upload interrupted')
                        target.write(chunk)
                        length -= len(chunk)
            except Exception:
                save_state(job_id, status='error', message='업로드가 중단되었습니다.')
                self.close_connection = True
                return self.json(dict(error='업로드가 중단되었습니다.'), 400)
        save_state(job_id, status='queued', message='전체 음원 분리 및 분석 대기 중')
        POOL.submit(analyze, job_id, demo, separate_guitar)
        return self.json(dict(id=job_id), 202)


def seed_existing_runs():
    """Copy completed runs from v1 (`webapp/runs`) into `chord_studio_v2/runs` on first launch so v2 can be verified immediately without touching v1."""
    RUNS.mkdir(parents=True, exist_ok=True)
    v1_runs = ROOT / 'webapp' / 'runs'
    if not v1_runs.exists():
        return
    for src_dir in v1_runs.iterdir():
        if not src_dir.is_dir() or not (src_dir / 'job.json').exists() or not (src_dir / 'result.json').exists():
            continue
        dst_dir = RUNS / src_dir.name
        if dst_dir.exists():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for fname in ('job.json', 'result.json', 'vision_overlay.json', 'media.wav', 'media.mp4', 'guitar.wav'):
            sfile = src_dir / fname
            if sfile.exists():
                shutil.copy2(sfile, dst_dir / fname)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--public', action='store_true')
    args = parser.parse_args()
    seed_existing_runs()
    for file in RUNS.glob('*/job.json'):
        try:
            job = json.loads(file.read_text(encoding='utf-8'))
            if job['status'] not in ('complete', 'error'):
                job.update(status='error', message='서버가 재시작되었습니다. 다시 분석해 주세요.')
            cal_file = file.parent / 'user_calibration.json'
            if cal_file.exists() and 'user_calibration' not in job:
                try:
                    job['user_calibration'] = json.loads(cal_file.read_text(encoding='utf-8'))
                except Exception:
                    pass
            JOBS[job['id']] = job
        except (ValueError, KeyError):
            pass
    server = ThreadingHTTPServer((args.host, args.port), HandlerV2)
    server.allow_public = args.public or args.host not in ('127.0.0.1', 'localhost')
    url = f'http://{args.host}:{server.server_port}'
    print('Chord Studio v2 (Pre-deploy Verification):', url, flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
