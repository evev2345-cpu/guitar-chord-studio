"""Run the installed Demucs in its isolated environment, using cached weights."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--model',choices=['htdemucs','htdemucs_6s'],default='htdemucs')
    parser.add_argument('--stem',choices=['vocals','guitar'],default='vocals')
    parser.add_argument('--output', type=Path, required=True,
                        help='New directory; existing results are never overwritten')
    args = parser.parse_args()
    if args.stem=='guitar' and args.model!='htdemucs_6s':parser.error('Guitar output requires six-source model')
    audio = args.input.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        parser.error('Choose a new output directory')
    interpreter = ROOT / '.venv-audio-separation/Scripts/python.exe'
    if not interpreter.is_file():
        parser.error('Project separation environment is missing')
    env = os.environ.copy()
    env.update(HF_HOME=str(ROOT / '.cache/audio-models/huggingface'),
               TORCH_HOME=str(ROOT / '.cache/audio-models/torch'),
               HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
    command = [str(interpreter), '-m', 'demucs', '-n', args.model,
               '--two-stems', args.stem, '--float32', '--clip-mode', 'none',
               '--shifts', '0', '--segment', '7', '-d', 'cpu', '-j', '0',
               '-o', str(output), str(audio)]
    output.mkdir(parents=True)
    manifest = dict(input=str(audio), input_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),
                    command=command, model=args.model, requested_stem=args.stem,device='cpu',
                    network='offline_cached_weights', status='running',
                    limitations=['Source stems are model estimates, not verified isolated instruments',
                                 'separation quality and audiovisual timing require review',
                                 'shifts=0 is a quick reproducible baseline'])
    manifest_path = output / 'separation_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    started = time.perf_counter()
    with (output / 'execution.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    manifest.update(returncode=result.returncode, elapsed_s=time.perf_counter()-started,
                    status='completed' if result.returncode == 0 else 'failed')
    manifest['outputs'] = [str(p.relative_to(output)) for p in output.rglob('*.wav')]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
