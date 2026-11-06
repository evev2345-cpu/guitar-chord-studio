"""Attach source-bound vision observations; original audio layers remain intact."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from vision_context import add_layer


def attach(directory,run_directory):
    directory=Path(directory);run_directory=Path(run_directory)
    manifest=json.loads((run_directory/'manifest.json').read_text(encoding='utf-8'))
    source_id=hashlib.sha256((directory/'media.mp4').read_bytes()).hexdigest()
    if source_id!=manifest['source_id']:raise ValueError('Visual run belongs to a different uploaded video')
    observations=[json.loads(line) for line in (run_directory/'observations.jsonl').read_text(encoding='utf-8').splitlines()]
    result=json.loads((directory/'result.json').read_text(encoding='utf-8'))
    backup=directory/'result_before_vision_v5.json'
    if not backup.exists():shutil.copyfile(directory/'result.json',backup)
    add_layer(result,observations,source_id=source_id,fps=manifest['fps'])
    temp=directory/'vision_result.tmp';temp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');temp.replace(directory/'result.json')
    shutil.copyfile(run_directory/'overlay.json',directory/'vision_overlay.json')
    return result['vision_config']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job-directory',type=Path,required=True);p.add_argument('--vision-run',type=Path,required=True);a=p.parse_args()
    metadata=attach(a.job_directory,a.vision_run)
    jobfile=a.job_directory/'job.json';job=json.loads(jobfile.read_text(encoding='utf-8'));job['vision_url']='/api/jobs/'+job['id']+'/vision';job['vision_status']='experimental_location_only';jobfile.write_text(json.dumps(job,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(metadata,ensure_ascii=False))
