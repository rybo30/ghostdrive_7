# -*- mode: python ; coding: utf-8 -*-
import os
import platform
import llama_cpp

is_mac = platform.system() == 'Darwin'
is_windows = platform.system() == 'Windows'
should_strip = not is_windows

ghost_ico = os.path.join('core', 'Everything_else', 'ghost.ico')
ghost_icns = os.path.join('core', 'Everything_else', 'ghost.icns')

icon_datas = []
if os.path.exists(ghost_ico):
    icon_datas.append((ghost_ico, os.path.join('core', 'Everything_else')))
if os.path.exists(ghost_icns):
    icon_datas.append((ghost_icns, os.path.join('core', 'Everything_else')))

# Automatically bundle the full llama_cpp package directory including its native lib binaries
llama_cpp_dir = os.path.dirname(llama_cpp.__file__)
icon_datas.append((llama_cpp_dir, 'llama_cpp'))

a = Analysis(
    ['core/Everything_else/agents/daemon.py'],
    pathex=[
        '.', 
        'core', 
        'core/Everything_else', 
        'core/Everything_else/agents', 
        'core/Everything_else/agents/tools'
    ],
    binaries=[],
    datas=icon_datas,
    hiddenimports=[
        'core.Everything_else.agents.agent_manifest',
        'core.Everything_else.agents.decrypt_agent',
        'core.Everything_else.agents.deploy_agent',
        'core.Everything_else.agents.load_agent',
        'core.Everything_else.agents.ram_manager',
        'core.Everything_else.agents.save_agent_config',
        'core.Everything_else.agents.telegram_bot',
        'core.Everything_else.agents.tool_runner',
        'core.Everything_else.agents.tools.document_manager_tool',
        'core.Everything_else.agents.tools.document_reader_tool',
        'core.Everything_else.agents.tools.market_articles_tool',
        'core.Everything_else.agents.tools.market_data_tool',
        'core.Everything_else.agents.tools.media_digest_tool',
        'core.Everything_else.agents.tools.project_manager_tool',
        'core.Everything_else.agents.tools.rss_feed_tool',
        'core.Everything_else.agents.tools.scheduled_ping_tool',
        'core.Everything_else.agents.tools.schedule_ping_tool',
        'core.Everything_else.agents.tools.sports_news_tool',
        'core.Everything_else.agents.tools.system_health_tool',
        'core.Everything_else.agents.tools.weather_tool',
        'core.Everything_else.agents.tools.web_reader_tool',
        'core.Everything_else.agents.tools.web_search_tool',
        'llama_cpp',
        'cryptography',
        'psutil',
        'requests',
        'yaml',
        'sqlite3',
        'json',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 
        'tkinter.test', 
        'unit_test', 
        'pyqtgraph', 
        'torch.tests', 
        'numpy.tests'
    ],
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
    strip=should_strip,
    upx=False,
    console=False,
    icon=ghost_ico if (not is_mac and os.path.exists(ghost_ico)) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=should_strip,
    upx=False,
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