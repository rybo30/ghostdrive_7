# -*- mode: python ; coding: utf-8 -*-
import os
import platform
from PyInstaller.utils.hooks import collect_all

is_mac = platform.system() == 'Darwin'

# Collect dynamic binaries & data for installed packages
llama_datas, llama_binaries, llama_hiddenimports = collect_all('llama_cpp')
pyqtgraph_datas, pyqtgraph_binaries, pyqtgraph_hiddenimports = collect_all('pyqtgraph')

# Icon detection logic
ghost_ico = os.path.join('core', 'Everything_else', 'ghost.ico')
ghost_icns = os.path.join('core', 'Everything_else', 'ghost.icns')

a = Analysis(
    ['main.py'],
    pathex=['.', 'core', 'core/Everything_else'],
    binaries=llama_binaries + pyqtgraph_binaries,
    datas=llama_datas + pyqtgraph_datas,
    hiddenimports=[
        # Core AI & System
        'llama_cpp',
        'numpy',
        'cryptography',
        'psutil',
        'requests',
        'pypdf',
        'diskcache',
        'jinja2',
        'yaml',
        'bs4',
        
        # GUI
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'pyqtgraph',
        
        # Internal GhostDrive modules
        'core',
        'core.paths',
        'Everything_else',
        'filecrypt',
        'jynx_operator_ui',
        'health_page',
        'health_manager',
        'health_engine',
        'core.Everything_else.agents.daemon',
        'core.Everything_else.agents.ram_manager',
        'core.Everything_else.agents.telegram_bot',
        'core.Everything_else.agents.tool_runner',
    ] + llama_hiddenimports + pyqtgraph_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', '_tkinter', 'unit_test'],
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
    strip=False,
    upx=False,
    console=True,  # ENABLED: Spawns terminal window for logs/errors
    icon=ghost_ico if (not is_mac and os.path.exists(ghost_ico)) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
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