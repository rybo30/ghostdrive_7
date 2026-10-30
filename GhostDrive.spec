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
        'core.identity',
        'core.matchmaker',
        'core.network_manager',
        'core.network_protocols',
        'core.paths',
        'core.peers_manager',
        'core.platform_utils',
        'core.system_protocols',
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
        'core.Everything_else.agents.agent_manifest',
        'core.Everything_else.agents.daemon',
        'core.Everything_else.agents.decrypt_agent',
        'core.Everything_else.agents.deploy_agent',
        'core.Everything_else.agents.load_agent',
        'core.Everything_else.agents.ram_manager',
        'core.Everything_else.agents.save_agent_config',
        'core.Everything_else.agents.telegram_bot',
        'core.Everything_else.agents.tool_runner',
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
    excludes=['matplotlib', 'tkinter.test', 'unit_test', 'torch.tests', 'numpy.tests'], 
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
    strip=True,
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