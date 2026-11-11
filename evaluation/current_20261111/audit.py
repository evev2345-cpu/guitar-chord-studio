"""Verify actual invocation evidence, fixed inputs and unchanged source files."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import numpy as np
    import soundfile as sf
    m=json.loads((RUN/'manifest.json').read_text());changed=[name for name,h in m['source_hashes'].items() if sha(ROOT/name)!=h]
    if changed:raise ValueError('Production sources changed during evaluation: '+str(changed))
    results=[];pending=[]
    for mode in ['github','patched']:
        for r in m['records']:
            p=RUN/mode/'records'/(r['id']+'.json')
            if not p.exists():pending.append([mode,r['id']]);continue
            d=json.loads(p.read_text(encoding='utf-8'))
            if d['status']!='complete':continue
            job=RUN/mode/'artifacts'/d['job_id'];model=d['model']
            assert sha(job/'input.bin')==r['audio_sha256']
            assert model['sha256']=='2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec'
            assert model['basic_pitch']=='0.4.0' and model['providers']==['CPUExecutionProvider'] and model['threads']==4
            tasks=json.loads((job/'tasks.json').read_text());item=dict(mode=mode,id=r['id'],basic_pitch_used=True,
                basic_pitch_version=model['basic_pitch'],runtime_version=model['runtime'],model_sha256=model['sha256'],
                separation_status=d['separation_status'],source_input_hash_verified=True)
            for task in tasks:
                meta=d['prediction_meta'][task['id']+'_raw'];assert sha(task['audio'])==meta['source_sha256']
                with np.load(job/'prediction'/(task['id']+'_raw.npz')) as n:
                    clock=n['times'];assert len(clock)>0 and np.all(np.diff(clock)>0);assert clock[-1]>=meta['duration_s']-.05
            item['prediction_audio_hashes_verified']=True
            if mode=='patched':
                manifest=d['separation_manifest'];assert manifest['status']=='completed' and manifest['sources']==['drums','bass','other','vocals','guitar','piano']
                assert sha(job/'guitar.wav')==manifest['output_sha256']
                assert len(tasks)==2 and any(t['id']=='full_mix' for t in tasks)
                assert d['full_mix_anchor_available'] is True
                x,sr=sf.read(job/'audio.wav',dtype='float32',always_2d=True);y,yr=sf.read(job/'guitar.wav',dtype='float32',always_2d=True)
                item.update(demucs_used=True,demucs_model_sha256=manifest['model_sha256'],
                    guitar_pcm_sha256=hashlib.sha256(y.astype('<f4').tobytes()).hexdigest(),
                    source_rms=float(np.sqrt(np.mean(x*x))),guitar_rms=float(np.sqrt(np.mean(y*y))),
                    guitar_duration_s=len(y)/yr)
            else:
                assert d['separation_status']=='fallback_original_audio'
                item['demucs_used']=False
            results.append(item)
    output=dict(complete=not pending,unchanged_production_sources=True,source_files_checked=len(m['source_hashes']),
                pending=pending,records=results,note='WAV file headers can include timestamps; guitar PCM SHA is separately provided.')
    (RUN/'execution_audit.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Audited:',len(results),'pending:',len(pending),'production sources unchanged')


if __name__=='__main__':main()
