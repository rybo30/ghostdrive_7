# -*- mode: python ; coding: utf-8 -*-
import os
import platform
from PyInstaller.utils.hooks import collect_all

# Detect platform
is_mac = platform.system() == 'Darwin'

# [1] Collect all dynamic hooks, binaries, and data for heavy engines
llama_datas, llama_binaries, llama_hiddenimports = collect_all('llama_cpp')
sd_datas, sd_binaries, sd_hiddenimports = collect_all('sounddevice')
whisper_datas, whisper_binaries, whisper_hiddenimports = collect_all('whisper')

# Icon detection & packaging into datas so they reside cleanly inside _internal
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
    binaries=llama_binaries + sd_binaries + whisper_binaries,
    datas=llama_datas + sd_datas + whisper_datas + icon_datas, 
    hiddenimports=[
        # --- Core Root Modules ---
        'core.identity',
        'core.matchmaker',
        'core.network_manager',
        'core.network_protocols',
        'core.paths',
        'core.peers_manager',
        'core.platform_utils',
        'core.system_protocols',
        
        # --- UI Pages & Windows ---
        'core.ui.agents_page',
        'core.ui.chat_page',
        'core.ui.coding_page',
        'core.ui.games_page',
        'core.ui.health_page',
        'core.ui.inventory_page',
        'core.ui.login_window',
        'core.ui.main_window',
        'core.ui.my_drive_page',
        'core.ui.ollie_page',
        'core.ui.profile_page',
        'core.ui.project_page',
        'core.ui.style_config',
        'core.ui.sync_page',
        'core.ui.vault_page',
        
        # --- Everything Else (Engines & Managers) ---
        'core.Everything_else.ai_council',
        'core.Everything_else.bvz_game',
        'core.Everything_else.chat_manager',
        'core.Everything_else.coding_worker',
        'core.Everything_else.command_checker',
        'core.Everything_else.encryption_engine',
        'core.Everything_else.filecrypt',
        'core.Everything_else.final_cleanup',
        'core.Everything_else.game_engine',
        'core.Everything_else.ghostvault',
        'core.Everything_else.health_engine',
        'core.Everything_else.health_manager',
        'core.Everything_else.history_manager',
        'core.Everything_else.inventory_manager',
        'core.Everything_else.jynx_operator_ui',
        'core.Everything_else.login_helpers',
        'core.Everything_else.manifest_manager',
        'core.Everything_else.market_data',
        'core.Everything_else.meeting_engine',
        'core.Everything_else.model_registry',
        'core.Everything_else.project_engine',
        'core.Everything_else.project_manager',
        'core.Everything_else.prompt_builder',
        'core.Everything_else.prompt_utils',
        'core.Everything_else.silent_bootstrapper',
        
        # --- Agents Subsystem ---
        'core.Everything_else.agents.agent_manifest',
        'core.Everything_else.agents.daemon',
        'core.Everything_else.agents.decrypt_agent',
        'core.Everything_else.agents.deploy_agent',
        'core.Everything_else.agents.load_agent',
        'core.Everything_else.agents.ram_manager',
        'core.Everything_else.agents.save_agent_config',
        'core.Everything_else.agents.telegram_bot',
        'core.Everything_else.agents.tool_runner',
        
        # --- Agent Tools Subsystem ---
        'core.Everything_else.agents.tools.document_manager_tool',
        'core.Everything_else.agents.tools.document_reader_tool',
        'core.Everything_else.agents.tools.market_articles_tool',
        'core.Everything_else.agents.tools.market_data_tool',
        'core.Everything_else.agents.tools.media_digest_tool',
        'core.Everything_else.agents.tools.project_manager_tool',
        'core.Everything_else.agents.tools.rss_feed_tool',
        'core.Everything_else.agents.tools.schedule_ping_tool',
        'core.Everything_else.agents.tools.sports_news_tool',
        'core.Everything_else.agents.tools.system_health_tool',
        'core.Everything_else.agents.tools.weather_tool',
        'core.Everything_else.agents.tools.web_reader_tool',
        'core.Everything_else.agents.tools.web_search_tool',
        
        # --- External Libraries & Dependencies ---
        'llama_cpp',
        'sounddevice',
        'whisper',
        'numpy',
        'torch',
        'tqdm',
        'cryptography',
        'psutil',
        'requests',
        'calendar',          
        'datetime',          
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'tkinter',           
        '_tkinter',          
        'secrets',           
    ] + llama_hiddenimports + sd_hiddenimports + whisper_hiddenimports,
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
    exclude_binaries=True, # Enforces onedir folder structure
    name='GhostDrive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, 
    upx_exclude=[],
    console=True,          # Visible terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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