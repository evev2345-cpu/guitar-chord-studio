"""Run the pretrained audio path explicitly, without changing the FFT default.

Example: python run_pretrained_audio.py --audio clip.wav --source-id VIDEO_SHA
         --offset 194 --input-mode raw --output dataset/audio_analysis/runs/new_model_run
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--audio',type=Path,required=True);p.add_argument('--source-id',required=True)
    p.add_argument('--offset',type=float,required=True);p.add_argument('--input-mode',choices=['raw','cut'],required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    audio=a.audio.resolve();out=a.output.resolve();python=ROOT/'.venv-audio-model/Scripts/python.exe'
    if not audio.is_file() or not python.is_file():raise FileNotFoundError('Input audio or installed model environment missing')
    if out.exists():raise FileExistsError(out)
    if a.offset<0:raise ValueError('Offset must be nonnegative')
    out.mkdir(parents=True);tasks=out/'tasks.json';tasks.write_text(json.dumps([dict(id='input',audio=str(audio))],indent=2),encoding='utf-8')
    subprocess.run([str(python),str(ROOT/'basic_pitch_worker.py'),'--tasks',str(tasks),'--output',str(out/'predictions')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'export_basic_pitch_evidence.py'),'--prediction',str(out/'predictions'/f'input_{a.input_mode}.npz'),
                    '--source-id',a.source_id,'--offset',str(a.offset),'--output',str(out/'analysis')],check=True,cwd=ROOT)
    (out/'run.json').write_text(json.dumps(dict(engine='basic_pitch_pretrained_onnx',input_mode=a.input_mode,
        input_pitch_range_midi=[38,88] if a.input_mode=='cut' else None,output_pitch_range_midi=[38,88],
        evidence=str(out/'analysis/evidence.json'),harmony=str(out/'analysis/harmony.json')),indent=2),encoding='utf-8')
    print(out/'analysis/harmony.json',flush=True)

if __name__=='__main__':main()
