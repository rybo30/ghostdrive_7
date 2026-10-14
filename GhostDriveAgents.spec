# -*- mode: python ; coding: utf-8 -*-
import os
import platform
from PyInstaller.utils.hooks import collect_all

is_mac = platform.system() == 'Darwin'

# Collect dynamic binaries & data for heavy/dynamic libraries
llama_datas, llama_binaries, llama_hiddenimports = collect_all('llama_cpp')
pyqtgraph_datas, pyqtgraph_binaries, pyqtgraph_hiddenimports = collect_all('pyqtgraph')
bs4_datas, bs4_binaries, bs4_hiddenimports = collect_all('bs4')

# Icon detection
ghost_ico = os.path.join('core', 'Everything_else', 'ghost.ico')
ghost_icns = os.path.join('core', 'Everything_else', 'ghost.icns')

# Map local icon files to destination inside _internal folder
icon_datas = []
if os.path.exists(ghost_ico):
    icon_datas.append((ghost_ico, os.path.join('core', 'Everything_else')))
if os.path.exists(ghost_icns):
    icon_datas.append((ghost_icns, os.path.join('core', 'Everything_else')))

a = Analysis(
    ['core/Everything_else/agents/daemon.py'],
    pathex=['.', 'core', 'core/Everything_else', 'core/Everything_else/agents'],
    binaries=llama_binaries + pyqtgraph_binaries + bs4_binaries,
    datas=llama_datas + pyqtgraph_datas + bs4_datas + icon_datas,
    hiddenimports=[
        # System & Security
        'cryptography',
        'psutil',
        'requests',
        'pypdf',
        'diskcache',
        'jinja2',
        'yaml',
        'sqlite3',
        
        # XML & Web Parsers
        'xml',
        'xml.etree',
        'xml.etree.ElementTree',
        'html.parser',
        
        # Inference & Math
        'llama_cpp',
        'numpy',
        
        # GUI & HUD
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'pyqtgraph',
        
        # Internal Agent Modules
        'core',
        'core.paths',
        'Everything_else',
        'daemon',
        'decrypt_agent',
        'deploy_agent',
        'ram_manager',
        'telegram_bot',
        'tool_runner',
    ] + llama_hiddenimports + pyqtgraph_hiddenimports + bs4_hiddenimports,
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
    name='GhostDriveAgents',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name='GhostDriveAgents',
)

if is_mac:
    app = BUNDLE(
        coll,
        name='GhostDriveAgents.app',
        icon=ghost_icns if os.path.exists(ghost_icns) else None,
        bundle_identifier='com.ghostdrive.agents',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'False',
        },
    )