# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AI Gateway Windows EXE
Run: pyinstaller build.spec --clean --noconfirm
"""

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# ── 1. Our own src package – must be listed explicitly ───────────────────────
src_modules = [
    'src',
    'src.core',
    'src.core.proxy',
    'src.core.server',
    'src.gui',
    'src.gui.app',
    'src.gui.main_frame',
    'src.gui.controller',
    'src.gui.theme',
    'src.gui.widgets',
    'src.gui.panels',
    'src.gui.panels.dashboard',
    'src.gui.panels.channels',
    'src.gui.panels.tokens',
    'src.gui.panels.settings',
    'src.models',
    'src.models.config',
]

# ── 2. Collect ALL submodules from tricky packages ───────────────────────────
hiddenimports = (
    src_modules
    + collect_submodules('uvicorn')
    + collect_submodules('starlette')
    + collect_submodules('fastapi')
    + collect_submodules('anyio')
    + collect_submodules('httpx')
    + [
        # h11
        'h11',
        'h11._connection',
        'h11._events',
        'h11._headers',
        'h11._readers',
        'h11._writers',
        'h11._util',
        # Pydantic v2
        'pydantic',
        'pydantic_core',
        'pydantic_settings',
        'pydantic_settings.main',
        # wxPython
        'wx',
        'wx.lib',
        'wx.lib.scrolledpanel',
        'wx.lib.agw',
        'wx.lib.agw.hyperlink',
        # asyncio (Windows proactor)
        'asyncio',
        'asyncio.windows_events',
        'asyncio.windows_utils',
        'asyncio.proactor_events',
        # Misc
        'logging.config',
        'logging.handlers',
        'email.mime.text',
        'email.mime.multipart',
        'typing_extensions',
        'sniffio',
        'exceptiongroup',
        'certifi',
        'idna',
        'charset_normalizer',
        'multipart',
        'click',
    ]
)

# ── 3. Data files ─────────────────────────────────────────────────────────────
datas = []
for pkg in ('uvicorn', 'fastapi'):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

# ── 4. Analysis ───────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=['.'],       # project root on sys.path so 'src' package is found
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'PIL',
        'scipy', 'pandas', 'pytest', 'IPython', 'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AIGateway',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='resources/icon.ico',
)
