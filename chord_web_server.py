"""Local-only chord web app. Start: python chord_web_server.py --open"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid
import webbrowser
from chord_web_analysis import ROOT, write_result

STATIC = ROOT / 'webapp' / 'static'
RUNS = ROOT / 'webapp' / 'runs'
MODEL_PYTHON = ROOT / '.venv-audio-model' / 'Scripts' / 'python.exe'
MAX_BYTES = 150 * 1024 * 1024
MAX_SECONDS = 300
POOL = ThreadPoolExecutor(max_workers=1)
LOCK = threading.RLock()
JOBS = {}


def save_state(job_id, **fields):
    with LOCK:
        JOBS[job_id].update(fields)
        (RUNS / job_id / 'job.json').write_text(json.dumps(JOBS[job_id], ensure_ascii=False), encoding='utf-8')


def run(command, log):
    with log.open('ab') as out:
        subprocess.run([str(v) for v in command], cwd=ROOT, stdout=out, stderr=out,
                       check=True, timeout=1800, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def analyze(job_id, demo=False):
    directory = RUNS / job_id
    log = directory / 'analysis.log'
    try:
        save_state(job_id, status='running', progress=8, message='미디어 확인 중')
        if demo:
            prediction = ROOT / 'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions/tutorial_raw.npz'
            audio = ROOT / 'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav'
            (directory / 'prediction').mkdir()
            shutil.copyfile(prediction, directory / 'prediction/upload_raw.npz')
            shutil.copyfile(audio, directory / 'media.wav')
            duration = 32.
            media = 'media.wav'
            save_state(job_id, progress=80, message='기존 분석 결과를 불러오는 중')
        else:
            if not MODEL_PYTHON.exists():
                raise ValueError('기존 .venv-audio-model 환경을 찾을 수 없습니다.')
            source = directory / 'input.bin'
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(source)],
                                   capture_output=True, check=True, timeout=30)
            info = json.loads(probe.stdout)
            duration = float(info['format']['duration'])
            if not 0.5 <= duration <= MAX_SECONDS:
                raise ValueError('첫 버전은 0.5초~5분 파일을 지원합니다. 짧은 구간으로 잘라주세요.')
            if not any(s['codec_type'] == 'audio' for s in info['streams']):
                raise ValueError('오디오 트랙이 없는 파일입니다.')
            save_state(job_id, progress=20, message='오디오 준비 중')
            run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', source, '-map', '0:a:0', '-vn',
                 '-ac', '1', '-ar', '22050', '-c:a', 'pcm_s16le', directory / 'audio.wav'], log)
            if any(s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic') for s in info['streams']):
                save_state(job_id, progress=30, message='브라우저 재생용 영상 준비 중')
                run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', source, '-map', '0:v:0', '-map', '0:a:0',
                     '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-preset', 'veryfast',
                     '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', directory / 'media.mp4'], log)
                media = 'media.mp4'
            else:
                shutil.copyfile(directory / 'audio.wav', directory / 'media.wav')
                media = 'media.wav'
            (directory / 'tasks.json').write_text(json.dumps([dict(id='upload', audio=str(directory / 'audio.wav'))]), encoding='utf-8')
            save_state(job_id, progress=45, message='기존 오디오 모델로 음 후보 분석 중')
            run([MODEL_PYTHON, ROOT / 'basic_pitch_worker.py', '--tasks', directory / 'tasks.json',
                 '--output', directory / 'prediction', '--modes', 'raw'], log)
            save_state(job_id, progress=85, message='코드 후보와 시간축 생성 중')
        write_result(directory, duration)
        save_state(job_id, status='complete', progress=100, message='분석 완료', duration_s=duration,
                   media_url=f'/media/{job_id}/{media}', result_url=f'/api/jobs/{job_id}/result')
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else '분석에 실패했습니다. 파일 형식과 서버의 analysis.log를 확인해 주세요.'
        with log.open('a', encoding='utf-8') as f:
            f.write('\n' + repr(exc))
        save_state(job_id, status='error', message=message)


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


class Handler(BaseHTTPRequestHandler):
    def allowed(self):
        expected = f'127.0.0.1:{self.server.server_port}'
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        return host in (expected, f'localhost:{self.server.server_port}') and (origin is None or origin == 'http://' + host)

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
            return self.json(dict(error='로컬 주소에서 열어주세요.'), 403)
        path = urlsplit(self.path).path
        static = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        if path in static:
            return self.file(STATIC / static[path])
        if path == '/api/jobs':
            with LOCK:
                return self.json(list(JOBS.values()))
        match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})(/result)?', path)
        if match:
            with LOCK:
                job = JOBS.get(match[1])
                if job is None:
                    return self.json(dict(error='분석을 찾을 수 없습니다.'), 404)
                if not match[2]:
                    return self.json(dict(job))
                if job['status'] != 'complete':
                    return self.json(dict(error='분석이 아직 완료되지 않았습니다.'), 409)
            return self.file(RUNS / match[1] / 'result.json')
        match = re.fullmatch(r'/media/([a-f0-9]{32})/(media\.(?:wav|mp4))', path)
        if match:
            return self.file(RUNS / match[1] / match[2])
        return self.json(dict(error='경로를 찾을 수 없습니다.'), 404)

    def do_POST(self):
        if not self.allowed():
            self.close_connection = True
            return self.json(dict(error='허용되지 않은 요청입니다.'), 403)
        url = urlsplit(self.path)
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
            return self.json(dict(error='150MB 이하의 파일을 선택해 주세요.'), 413)
        with LOCK:
            if sum(j['status'] in ('uploading', 'queued', 'running') for j in JOBS.values()) >= 4:
                self.close_connection = True
                return self.json(dict(error='분석 대기열이 가득 찼습니다. 잠시 후 시도해 주세요.'), 429)
            job_id = uuid.uuid4().hex
            directory = RUNS / job_id
            directory.mkdir(parents=True)
            name = parse_qs(url.query).get('name', ['업로드 파일'])[0][:160]
            JOBS[job_id] = dict(id=job_id, name='튜토리얼 · 기타 분리음 (3:14–3:46)' if demo else name,
                                created_at=time.time(), status='uploading', progress=0, message='업로드 중', demo=demo)
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
        save_state(job_id, status='queued', message='분석 대기 중')
        POOL.submit(analyze, job_id, demo)
        return self.json(dict(id=job_id), 202)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)
    for file in RUNS.glob('*/job.json'):
        try:
            job = json.loads(file.read_text(encoding='utf-8'))
            if job['status'] not in ('complete', 'error'):
                job.update(status='error', message='서버가 재시작되었습니다. 다시 분석해 주세요.')
            JOBS[job['id']] = job
        except (ValueError, KeyError):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{server.server_port}'
    print('Chord Studio:', url, flush=True)
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
