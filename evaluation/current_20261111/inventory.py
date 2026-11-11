"""Capture environment/data facts for a prepared run; no inference or tuning."""
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import warnings

ROOT=Path(__file__).resolve().parents[2]
RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()


def main():
    from scipy.io import wavfile
    def ps(code):
        return json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',code+' | ConvertTo-Json -Compress'],text=True,encoding='utf-8-sig'))
    env=dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
        cpu=ps('Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors'),
        memory=ps('Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory'),
        gpu=ps('Get-CimInstance Win32_VideoController | Select-Object Name'),
        packages={x:md.version(x) for x in ['basic-pitch','onnxruntime','numpy','scipy','librosa','resampy','soundfile']},
        ffmpeg=subprocess.check_output([str(ROOT/'bin/ffmpeg.exe'),'-version'],text=True).splitlines()[0],
        accelerator_used='CPU only',basic_pitch_threads=4,demucs_threads=4,concurrent_recordings=1)
    (RUN/'environment.json').write_text(json.dumps(env,indent=2),encoding='utf-8')
    manifest=json.loads((RUN/'manifest.json').read_text(encoding='utf-8'));rows=[]
    for r in manifest['records']:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore');rate,x=wavfile.read(r['audio'],mmap=True)
        rows.append(dict(id=r['id'],dataset=r['dataset'],duration_s=len(x)/rate,rate=rate,dtype=str(x.dtype),
            channels=1 if x.ndim==1 else x.shape[1],query_count=len(r['times']),known_timing_issue=r['known_timing_issue']))
    (RUN/'data_inventory.json').write_text(json.dumps(rows,indent=2))
    for name,python in [('audio_model',ROOT/'.venv-audio-model/Scripts/python.exe'),('separation',ROOT/'.venv-audio-separation/Scripts/python.exe')]:
        result=subprocess.run(['uv','pip','freeze','--python',str(python)],capture_output=True,text=True,check=True)
        (RUN/(name+'_requirements.lock.txt')).write_text(result.stdout,encoding='utf-8')
    print('Environment and data inventory recorded:',len(rows),'files')


if __name__=='__main__':main()
