# -*- mode: python ; coding: utf-8 -*-
import os
import platform

is_mac = platform.system() == 'Darwin'

ghost_ico = os.path.join('core', 'Everything_else', 'ghost.ico')
ghost_icns = os.path.join('core', 'Everything_else', 'ghost.icns')

icon_datas = []
if os.path.exists(ghost_ico):
    icon_datas.append((ghost_ico, os.path.join('core', 'Everything_else')))
if os.path.exists(ghost_icns):
    icon_datas.append((ghost_icns, os.path.join('core', 'Everything_else')))

a = Analysis(
    ['main.py'],
    pathex=['.', 'core', 'core/Everything_else'], 
    binaries=[],
    datas=icon_datas, 
    hiddenimports=[
        'llama_cpp',
        'sounddevice',
        'whisper',
        'numpy',
        'torch',
        'tqdm',
        'cryptography',
        'psutil',
        'requests',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter.test', 'unit_test'], 
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GhostDrive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strips debug symbols to keep package size lean
    upx=False, 
    console=True,
    icon=ghost_ico if (not is_mac and os.path.exists(ghost_ico)) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    name='GhostDrive',
)

if is_mac:
    app = BUNDLE(
        coll,
        name='GhostDrive.app',
        icon=ghost_icns if os.path.exists(ghost_icns) else None,
        bundle_identifier='com.ghostdrive.app',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'False',
        },
    )