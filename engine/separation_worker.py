"""Offline six-source inference shared by development Python and portable EXE.

Uses Demucs load_safetensors_model/apply_model and its normalization policy.
Only decoded WAV and a fixed local model are read; no network model loading.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

MODEL_SHA256 = 'd2a1745f0744721f6b8ca5bf469b67c651ea5ed1b52998cab033b2158609d411'


def model_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'models/htdemucs_6s.safetensors'
    root = Path(__file__).resolve().parent.parent
    packaged = root / 'models/htdemucs_6s.safetensors'
    if packaged.is_file():return packaged
    cache = root / '.cache/audio-models/huggingface/hub/models--adefossez--HTDemucs-6s/snapshots'
    return next(iter(sorted(cache.glob('*/5c90dfd2.safetensors'))), packaged)


def separate(audio, output):
    audio = Path(audio).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():raise ValueError('Choose a new output directory; existing results are preserved.')
    weights = model_path()
    if not weights.is_file():raise ValueError('Bundled htdemucs_6s weights are missing.')
    model_sha = hashlib.sha256(weights.read_bytes()).hexdigest()
    if model_sha != MODEL_SHA256:raise ValueError('Unexpected htdemucs_6s weights checksum.')
    output.mkdir(parents=True)
    started = time.perf_counter()
    manifest = dict(status='running',model='htdemucs_6s',requested_stem='guitar',device='cpu',
        runtime='frozen_worker' if getattr(sys,'frozen',False) else 'isolated_python',
        executable=sys.executable,input=str(audio),input_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),
        model_sha256=model_sha,network='offline_local_safetensors',shifts=0,segment_s=7)
    dest = output / 'separation_manifest.json'
    dest.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    try:
        os.environ.update(HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
        import numpy as np
        import soundfile as sf
        import torch
        from demucs.apply import apply_model
        from demucs.audio import convert_audio
        from demucs.hf import load_safetensors_model
        torch.set_num_threads(4)
        model = load_safetensors_model(weights).eval().cpu()
        if 'guitar' not in model.sources or len(model.sources)!=6:
            raise ValueError('Expected a six-source model with a guitar stem.')
        pcm,rate = sf.read(audio,dtype='float32',always_2d=True)
        if len(pcm)<2 or not np.isfinite(pcm).all():raise ValueError('Invalid input audio.')
        wav = convert_audio(torch.from_numpy(pcm.T.copy()),rate,model.samplerate,model.audio_channels)
        ref = wav.mean(0);mean = ref.mean();std = ref.std()+1e-8
        with torch.inference_mode():
            prediction = apply_model(model,((wav-mean)/std)[None],device='cpu',shifts=0,
                split=True,overlap=.25,segment=7,num_workers=0,progress=False)[0]*std+mean
        guitar = prediction[model.sources.index('guitar')]
        if not torch.isfinite(guitar).all():raise ValueError('Non-finite separation output.')
        target = output / 'htdemucs_6s' / audio.stem
        target.mkdir(parents=True)
        sf.write(target/'guitar.wav',guitar.T.numpy(),model.samplerate,subtype='FLOAT')
        sf.write(target/'no_guitar.wav',(prediction.sum(0)-guitar).T.numpy(),model.samplerate,subtype='FLOAT')
        manifest.update(status='completed',returncode=0,sources=list(model.sources),
            duration_s=guitar.shape[-1]/model.samplerate,sample_rate=model.samplerate,
            outputs=[str(p.relative_to(output)) for p in target.glob('*.wav')],
            output_sha256=hashlib.sha256((target/'guitar.wav').read_bytes()).hexdigest())
    except Exception as exc:
        manifest.update(status='failed',returncode=1,error=repr(exc))
        raise
    finally:
        manifest['elapsed_s']=time.perf_counter()-started
        dest.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',choices=['htdemucs_6s'],default='htdemucs_6s')
    parser.add_argument('--stem',choices=['guitar'],default='guitar')
    args=parser.parse_args()
    print(json.dumps(separate(args.input,args.output),indent=2),flush=True)


if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
