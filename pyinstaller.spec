# -*- mode: python ; coding: utf-8 -*-
"""
Minimal PyInstaller spec: GUI entry main.py + bundled resources/ for release (onedir).
Run from project root: pyinstaller pyinstaller.spec  (or .\\build.ps1)
"""
# Analysis, PYZ, EXE, COLLECT are provided in the namespace when PyInstaller runs this file.
import os
import torchgen
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Only exclude frameworks we do NOT ship. DO NOT exclude any torch submodule
# or `torchgen`: torch.utils._python_dispatch imports torchgen at runtime,
# and torch.nn.Module depends on that dispatch module (verified via runtime
# ModuleNotFoundError when torchgen was excluded).
_UNUSED_FRAMEWORK_EXCLUDES = [
    'tensorflow', 'jax', 'jaxlib', 'sklearn',
    'IPython', 'jupyter', 'notebook', 'pytest',
    'torch.utils.tensorboard',
]

# torch.utils._python_dispatch does `import torchgen` at runtime. torchgen has
# an empty __init__.py and many subfiles require PyYAML (not a torch runtime
# dep), so collect_submodules can silently drop them. To guarantee the top-
# level `import torchgen` succeeds in the frozen exe, copy the whole package
# directory as data — this also pulls in YAML templates used by dispatch code.
_TORCHGEN_DIR = os.path.dirname(torchgen.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources', 'resources'),
        (_TORCHGEN_DIR, 'torchgen'),
    ],
    hiddenimports=[
        'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
        'torchgen',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_UNUSED_FRAMEWORK_EXCLUDES,
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
    name='HouseholdLoadForecast',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name='HouseholdLoadForecast',
)

# Copy user-facing docs to the top of the onedir tree (next to the exe) so
# end users see them immediately after unzipping, not buried under _internal.
import shutil as _shutil
_DIST_ROOT = os.path.join(DISTPATH, 'HouseholdLoadForecast')
for _doc in ('USER_GUIDE.md', 'README.md'):
    _src = os.path.join(os.path.dirname(os.path.abspath(SPEC)), _doc)
    if os.path.isfile(_src) and os.path.isdir(_DIST_ROOT):
        _shutil.copy2(_src, os.path.join(_DIST_ROOT, _doc))
