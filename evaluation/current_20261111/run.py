"""Run unchanged production analyze() for every frozen dataset recording.

Requires .venv-audio-model Python. Evaluation output is kept outside user runs.
The only wrappers measure wall time and immediately call the original functions.
"""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]
RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()


def execute(mode,limit=None):
    manifest=json.loads((RUN/'manifest.json').read_text(encoding='utf-8'))
    source=RUN/'github_source' if mode=='github' else ROOT
    sys.path.insert(0,str(source/'engine'))
    sys.path.insert(0,str(source))
    spec=importlib.util.spec_from_file_location('production_server',source/'chord_studio_v2/server_v2.py')
    server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
    from labels import load_reference
    from metrics import collect,temporal,choices
    from chord_web_analysis import predictions
    import numpy as np
    from scipy.io import wavfile
    base=RUN/mode;base.mkdir(exist_ok=True)
    server.RUNS=base/'artifacts';server.RUNS.mkdir(exist_ok=True);server.JOBS={}
    records=manifest['records'][:limit] if limit else manifest['records']
    began=time.perf_counter()
    for index,rec in enumerate(records):
        target=base/'records'/(rec['id']+'.json');target.parent.mkdir(exist_ok=True)
        if target.exists():continue
        job_id=hashlib.sha256(rec['id'].encode()).hexdigest()[:32]
        directory=server.RUNS/job_id
        result=dict(id=rec['id'],dataset=rec['dataset'],mode=mode,known_timing_issue=rec['known_timing_issue'],job_id=job_id,status='pending')
        try:
            if directory.exists():
                # Preserve unsuccessful attempts; a resume never reuses a prediction cache.
                directory.rename(directory.with_name(job_id+'_attempt_'+str(time.time_ns())))
            directory.mkdir()
            for key,sha in [('audio','audio_sha256'),('annotation','annotation_sha256')]:
                if hashlib.sha256(Path(rec[key]).read_bytes()).hexdigest()!=rec[sha]:raise ValueError('Dataset integrity mismatch: '+key)
            shutil.copyfile(rec['audio'],directory/'input.bin')
            server.JOBS[job_id]=dict(id=job_id,status='queued',name='benchmark_input',created_at=time.time())
            measured={};original_write=server.write_result
            def timed_write(*args,**kwargs):
                t=time.perf_counter()
                try:return original_write(*args,**kwargs)
                finally:measured['B_backend_and_result_write_s']=time.perf_counter()-t
            server.write_result=timed_write
            t=time.perf_counter()
            try:server.analyze(job_id,demo=False,separate_guitar=True)
            finally:server.write_result=original_write
            measured['B_analyze_wall_s']=time.perf_counter()-t
            job=json.loads((directory/'job.json').read_text(encoding='utf-8'))
            result.update(job=job,timing=measured)
            if job['status']!='complete':raise RuntimeError(job['message'])
            if mode=='patched' and job.get('separation_status')!='separated_htdemucs_6s':raise RuntimeError('Expected real Demucs separation')
            if mode=='github' and job.get('separation_status') not in ['fallback_original_audio','original_audio_mode','separated_htdemucs_6s']:raise RuntimeError('Unexpected committed pipeline state')
            result.update(status='complete',duration_s=job['duration_s'],separation_status=job.get('separation_status'))
            if (directory/'separation/separation_manifest.json').exists():
                result['separation_manifest']=json.loads((directory/'separation/separation_manifest.json').read_text())
            data=json.loads((directory/'result.json').read_text(encoding='utf-8'))
            result['tempo']=data.get('tempo');result['analysis_mode']=data['analysis_mode'];result['full_mix_anchor_available']=data.get('full_mix_anchor_available')
            models=json.loads((directory/'prediction/model.json').read_text());result['model']=models
            result['prediction_meta']={p.stem:json.loads(p.read_text()) for p in (directory/'prediction').glob('*_raw.json')}
            # Measure the native raw candidate function separately, with no copied scorer.
            with np.load(directory/'prediction/upload_raw.npz') as d:
                grid=d['times'];notes=d['note'];queries=np.arange(0,job['duration_s'],1/24)
                t=time.perf_counter()
                for width in [.2,.4]:predictions(grid,notes,queries,width)
                measured['A_native_raw_postprocess_both_widths_s']=time.perf_counter()-t
            if rec['dataset']=='guitarset':layers,_=load_reference(rec['annotation'])
            else:layers={'nominal':[dict(time=float(a),duration=float(b)-float(a),value=c.replace(':5',':(1,5)')) for a,b,c in (line.split() for line in Path(rec['annotation']).read_text().splitlines() if line.strip())]}
            result['branches']={};result['temporal']={}
            csv_path=base/'details'/(rec['id']+'.csv');csv_path.parent.mkdir(exist_ok=True)
            with csv_path.open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.DictWriter(f,fieldnames=['id','dataset','width','layer','time_s','reference','reference_root','reference_quality','reference_pcs','view','predictions','n','exact','root','quality','abstain','ambiguous','oov']);writer.writeheader()
                for width,rows in data['branches'].items():
                    result['branches'][width]={};result['temporal'][width]={}
                    for layer,events in layers.items():
                        stats,detail=collect(rows,rec['times'],events,rec['dataset']);result['branches'][width][layer]=stats
                        result['temporal'][width][layer]=temporal(rows,events)
                        for row in detail:
                            row.update(id=rec['id'],dataset=rec['dataset'],width=width,layer=layer)
                            row['reference_pcs']=json.dumps(row['reference_pcs']);row['predictions']=json.dumps(row['predictions'],ensure_ascii=False);writer.writerow(row)
                    # Native full24Hz predictions, independently of reference sampling.
                    compressed=base/'dense'/(rec['id']+'_'+width+'.jsonl.gz');compressed.parent.mkdir(exist_ok=True)
                    with gzip.open(compressed,'wt',encoding='utf-8') as g:
                        for row in rows:g.write(json.dumps(dict(time_s=row['time_s'],**{v:choices(row,v) for v in ['A','B','U_context','B_frame']}),ensure_ascii=False)+'\n')
            # Keep a compact proof that UI defaults resolve exactly to backend B.
            audit=base/'ui_audit';audit.mkdir(exist_ok=True)
            if index==0:(audit/'sample.json').write_text(json.dumps(data['branches']['0.2'][::max(1,len(data['branches']['0.2'])//30)]),encoding='utf-8')
            del data
        except Exception as exc:
            result.update(status='error',error=repr(exc),traceback=traceback.format_exc())
        result['cumulative_wall_s']=time.perf_counter()-began
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        progress=dict(mode=mode,completed=index+1,total=len(records),record=rec['id'],status=result['status'],wall_s=result['cumulative_wall_s'])
        (base/'progress.json').write_text(json.dumps(progress),encoding='utf-8');print(json.dumps(progress),flush=True)
    (base/'complete.json').write_text(json.dumps(dict(finished_at=time.time(),wall_s=time.perf_counter()-began,records=len(records),mode=mode)),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['github','patched'],required=True);parser.add_argument('--limit',type=int)
    args=parser.parse_args();execute(args.mode,args.limit)
