# Portable, isolated CPU runtime; no system Python, hub cache or FFmpeg required.
from pathlib import Path
import hashlib
import shutil
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

ROOT = Path(SPECPATH)
weights = ROOT / 'models/htdemucs_6s.safetensors'
if not weights.is_file():
    cache = ROOT / '.cache/audio-models/huggingface/hub/models--adefossez--HTDemucs-6s/snapshots'
    weights = next(iter(sorted(cache.glob('*/5c90dfd2.safetensors'))), weights)
assert weights.is_file(), 'Local htdemucs_6s weights required'
assert hashlib.sha256(weights.read_bytes()).hexdigest() == 'd2a1745f0744721f6b8ca5bf469b67c651ea5ed1b52998cab033b2158609d411'
# PyInstaller preserves the source basename. Normalize the hub cache filename.
staged_weights = ROOT / '.cache/separator_build_assets/htdemucs_6s.safetensors'
staged_weights.parent.mkdir(parents=True, exist_ok=True)
if not staged_weights.exists() or hashlib.sha256(staged_weights.read_bytes()).hexdigest() != hashlib.sha256(weights.read_bytes()).hexdigest():
    shutil.copy2(weights, staged_weights)
datas = [(str(staged_weights), 'models')]
datas += collect_data_files('demucs')
datas += copy_metadata('demucs')
datas += copy_metadata('torch')
a = Analysis([str(ROOT/'engine/separation_worker.py')], pathex=[str(ROOT/'engine')],
    datas=datas, binaries=[],
    hiddenimports=['demucs.htdemucs','demucs.hf','safetensors.torch','soundfile'],
    excludes=['tkinter','pytest','IPython','matplotlib','pandas','tensorboard','tensorflow'],
    hooksconfig={}, runtime_hooks=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='GuitarSeparator',
    console=True, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='GuitarSeparator')
