# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None
ROOT = Path.cwd()

datas = [
    (str(ROOT / 'chord_studio_v2' / 'static'), 'chord_studio_v2/static'),
    (str(ROOT / 'chord_studio_v2' / 'server_v2.py'), 'chord_studio_v2'),
    (str(ROOT / 'engine'), 'engine'),
    (str(ROOT / 'models'), 'models'),
    (str(ROOT / 'bin'), 'bin'),
    (str(ROOT / 'app_icon.ico'), '.'),
    (str(ROOT / 'app_icon.png'), '.'),
]
datas += collect_data_files('basic_pitch')
datas += collect_data_files('mediapipe')
binaries = collect_dynamic_libs('mediapipe')

hiddenimports = [
    'webview',
    'clr_loader',
    'pythonnet',
    'scipy.special.cython_special',
    'scipy.spatial.transform._rotation_groups',
    'scipy.io.wavfile',
    'cv2',
    'mediapipe',
    'numpy',
    'onnxruntime',
    'soundfile',
    'librosa',
    'basic_pitch',
    'basic_pitch.inference',
    'basic_pitch.constants',
    'basic_pitch.note_creation',
    'matplotlib',
    'matplotlib.pyplot',
    'mediapipe.tasks.python.vision',
]
hiddenimports += collect_submodules('mediapipe')

a = Analysis(
    ['desktop_chord_studio.py'],
    pathex=[str(ROOT), str(ROOT / 'engine'), str(ROOT / 'chord_studio_v2')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'IPython', 'PySide6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GuitarChordStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / 'app_icon.ico'),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GuitarChordStudio',
)
