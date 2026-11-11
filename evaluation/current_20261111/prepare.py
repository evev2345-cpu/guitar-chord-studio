"""Prepare a new run without modifying production code or the chosen Git commit."""
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--guitarset-root',type=Path,required=True)
    p.add_argument('--idmt-root',type=Path,required=True,help='Directory containing guitar/*.wav')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--commit',default='5c5396bc2c3ac8a667cd0fb42db66e09340742cd')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    raw=subprocess.check_output(['git','archive','--format=zip',a.commit,'engine','chord_studio_v2/server_v2.py','chord_studio_v2/static','desktop_chord_studio.py','README.md'],cwd=ROOT)
    (out/'github_source.zip').write_bytes(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(out/'github_source')
    # Only runtime assets are linked. No working-tree engine enters the Git snapshot.
    for name in ['bin','models','.venv-audio-model','.venv-audio-separation']:
        target=ROOT/name;dest=out/'github_source'/name
        if platform.system()=='Windows':
            subprocess.run(['powershell','-NoProfile','-Command',"New-Item -ItemType Junction -Path '"+str(dest).replace("'","''")+"' -Target '"+str(target).replace("'","''")+"' | Out-Null"],check=True)
        else:dest.symlink_to(target,target_is_directory=True)
    seed=json.loads((Path(__file__).parent/'dataset_manifest.json').read_text());records=[]
    for r in seed['records']:
        base=a.guitarset_root if r['dataset']=='guitarset' else a.idmt_root
        row=dict(r,audio=str((base/r['audio_relative']).resolve()),annotation=str((base/r['annotation_relative']).resolve()))
        for field in ['audio','annotation']:
            if sha(row[field])!=row[field+'_sha256']:raise ValueError('Input hash mismatch: '+row[field])
        records.append(row)
    files=list((ROOT/'engine').glob('*.py'))+[ROOT/'chord_studio_v2/server_v2.py',ROOT/'chord_studio_v2/static/app.js',ROOT/'desktop_chord_studio.py']
    for source in files:
        target=out/'working_source'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    manifest=dict(created=datetime.datetime.now(datetime.timezone.utc).isoformat(),git_remote_commit=a.commit,
        local_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_hashes={s.relative_to(ROOT).as_posix():sha(s) for s in files},records=records,
        workers=1,no_training=True,no_parameter_search=True)
    (out/'working_tree.patch').write_bytes(subprocess.check_output(['git','diff','--binary','HEAD'],cwd=ROOT))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(Path(__file__).parent/'PROTOCOL.json',out/'protocol.json')
    print(out)


if __name__=='__main__':main()
