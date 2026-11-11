"""Resolve the isolated development or bundled portable Demucs worker."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def bundled_worker():
    return Path(sys.executable).resolve().parent / 'workers/GuitarSeparator/GuitarSeparator.exe'


def separation_command(audio, output, model='htdemucs_6s', stem='guitar'):
    args = ['--input', str(Path(audio).resolve()), '--output', str(Path(output).resolve()),
            '--model', model, '--stem', stem]
    if getattr(sys, 'frozen', False):
        worker = bundled_worker()
        if not worker.is_file():
            raise ValueError('기타 분리 실행기가 없습니다. workers 폴더를 포함한 배포본 전체를 압축 해제해 주세요.')
        return [str(worker), *args]
    interpreter = ROOT / '.venv-audio-separation/Scripts/python.exe'
    if not interpreter.is_file():
        interpreter = ROOT / '.venv-audio-separation/bin/python'
    if not interpreter.is_file():
        raise ValueError('프로젝트 루트의 .venv-audio-separation 환경을 찾을 수 없습니다.')
    return [str(interpreter), str(ROOT / 'engine/separation_worker.py'), *args]


def worker_environment():
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', PYINSTALLER_RESET_ENVIRONMENT='1')
    for key in list(env):
        if key.startswith('_PYI_') or key in ('PYTHONHOME', 'PYTHONPATH'):
            env.pop(key, None)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', choices=['htdemucs_6s'], default='htdemucs_6s')
    parser.add_argument('--stem', choices=['guitar'], default='guitar')
    args = parser.parse_args()
    flags = dict(creationflags=subprocess.CREATE_NO_WINDOW) if sys.platform == 'win32' else {}
    result = subprocess.run(separation_command(args.input, args.output, args.model, args.stem),
                            env=worker_environment(), **flags)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
