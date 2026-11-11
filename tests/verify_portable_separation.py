"""Real packaged-EXE upload smoke test; not part of unit-test discovery.

python tests/verify_portable_separation.py --app <folder> --input <new WAV> --output <evidence folder>
No project Python, source directory or existing stem is passed to the EXE.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import Request,urlopen


def verify(app,audio,out):
    app=app.resolve(strict=True);audio=audio.resolve(strict=True);out=out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('_PYI_') or key in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','TORCH_HOME','HF_HOME','HF_HUB_CACHE'):
            env.pop(key,None)
    env.update(PATH=str(Path(os.environ['SystemRoot'])/'System32'),HF_HOME=str(out/'empty_hf'),
               TORCH_HOME=str(out/'empty_torch'),HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
               PYINSTALLER_RESET_ENVIRONMENT='1')
    flags=dict(creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    with (out/'server.log').open('wb') as log:
        process=subprocess.Popen([str(app/'GuitarChordStudio.exe'),'--serve-only','--port',str(port)],
            cwd=out,env=env,stdout=log,stderr=log,**flags)
        try:
            for _ in range(120):
                if process.poll() is not None:raise RuntimeError('Packaged server stopped before readiness')
                try:
                    with urlopen(base+'/api/jobs',timeout=1) as response:json.load(response)
                    break
                except OSError:time.sleep(.25)
            else:raise TimeoutError('Packaged server did not start')
            request=Request(base+'/api/jobs?name=portable-fresh-mixture.wav&separate=1',data=audio.read_bytes(),headers={'Content-Type':'audio/wav'})
            with urlopen(request,timeout=30) as response:job_id=json.load(response)['id']
            (out/'job_id.txt').write_text(job_id)
            started=time.perf_counter()
            while time.perf_counter()-started<240:
                with urlopen(base+'/api/jobs/'+job_id,timeout=5) as response:job=json.load(response)
                print(job.get('status'),job.get('message'),flush=True)
                if job['status'] in ('complete','error'):break
                time.sleep(1)
            (out/'job.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
            if job['status']!='complete':raise RuntimeError(job)
            assert job['separation_status']=='separated_htdemucs_6s',job
            assert job['separation_runtime']=='frozen_worker',job
            run=app/'_internal/chord_studio_v2/runs'/job_id
            manifest=json.loads((run/'separation/separation_manifest.json').read_text())
            assert manifest['runtime']=='frozen_worker' and manifest['status']=='completed'
            assert Path(manifest['executable']).is_relative_to(app)
            assert '.venv' not in manifest['executable']
            with urlopen(base+job['guitar_audio_url'],timeout=5) as response:guitar=response.read()
            assert hashlib.sha256(guitar).hexdigest()==manifest['output_sha256']
            with urlopen(base+job['result_url'],timeout=10) as response:result=json.load(response)
            tasks=json.loads((run/'tasks.json').read_text())
            assert any(Path(t['audio']).name=='guitar.wav' for t in tasks)
            assert result['full_mix_anchor_available'] is True
            from scipy.io import wavfile
            import numpy as np
            import io
            rate,pcm=wavfile.read(io.BytesIO(guitar))
            assert rate==44100 and pcm.shape[1]==2 and np.isfinite(pcm).all() and np.max(abs(pcm))>0
            (out/'guitar.wav').write_bytes(guitar)
            (out/'input.wav').write_bytes(audio.read_bytes())
            (out/'separation_manifest.json').write_text(json.dumps(manifest,indent=2))
            summary=dict(job_id=job_id,status='passed',elapsed_s=time.perf_counter()-started,
                runtime=manifest['runtime'],worker_executable=manifest['executable'],input_sha256=manifest['input_sha256'],
                model_sha256=manifest['model_sha256'],guitar_sha256=manifest['output_sha256'],duration_s=len(pcm)/rate,
                guitar_peak=float(np.max(abs(pcm))),sources=manifest['sources'],
                isolated_path=env['PATH'],empty_model_caches=True,
                analysis_mode=result['analysis_mode'],full_mix_anchor_available=result['full_mix_anchor_available'])
            (out/'validation.json').write_text(json.dumps(summary,indent=2))
            print(json.dumps(summary,indent=2),flush=True)
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app',type=Path,required=True);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();verify(args.app,args.input,args.output)
