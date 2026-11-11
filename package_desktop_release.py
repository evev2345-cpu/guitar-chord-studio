"""Package portable binaries while excluding all user analyses and QA uploads."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parent


def main():
    source=ROOT/'dist/GuitarChordStudio'
    target=ROOT/'dist/GuitarChordStudio_v2.0.1_Windows.zip'
    required=['GuitarChordStudio.exe','workers/GuitarSeparator/GuitarSeparator.exe',
              'workers/GuitarSeparator/_internal/models/htdemucs_6s.safetensors',
              '_internal/chord_studio_v2/server_v2.py','_internal/engine/run_local_separation.py']
    for name in required:
        if not (source/name).is_file():raise ValueError('Missing portable component: '+name)
    metadata=dict(version='2.0.1',date='2026-11-11',separation='offline bundled CPU worker',
        files={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in required})
    (source/'release.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    files=[p for p in source.rglob('*') if p.is_file() and
           not {'runs','runs_desktop','fretboard_data','__pycache__'}.intersection(p.relative_to(source).parts)
           and p.suffix not in {'.log','.pyc'}]
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,'GuitarChordStudio/'+p.relative_to(source).as_posix())
    with zipfile.ZipFile(target) as z:
        for name,sha in metadata['files'].items():
            if hashlib.sha256(z.read('GuitarChordStudio/'+name)).hexdigest()!=sha:raise ValueError('Packaged asset mismatch')
        if any('/runs/' in name for name in z.namelist()):raise ValueError('User analyses included')
    summary=dict(archive=str(target),bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                 file_count=len(files),user_analyses_included=False)
    (ROOT/'.cache/separation_fix_20261111/package.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
