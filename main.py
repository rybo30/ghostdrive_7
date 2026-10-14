# main.py

import sys
import os
import argparse
import ctypes # Added for Windows API access
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

# ===============================================================
# [1] DYNAMIC ROOT DETECTION
# ===============================================================
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(sys.executable), ".."))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===============================================================
# [2] PATH INJECTION
# ===============================================================
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "core"))
sys.path.insert(0, os.path.join(BASE_DIR, "core", "Everything_else"))

# ===============================================================
# [3] IMPORT CORE PATHS AFTER INJECTION
# ===============================================================
try:
    from core.paths import BASE_PATH, CORE_DIR, EVERYTHING_ELSE, USER_DATA
except ImportError:
    import paths as core_paths
    BASE_PATH = core_paths.BASE_PATH
    CORE_DIR = core_paths.CORE_DIR
    EVERYTHING_ELSE = core_paths.EVERYTHING_ELSE
    USER_DATA = core_paths.USER_DATA

# Updated icon paths
PNG_ICON = os.path.join(EVERYTHING_ELSE, "ghost.png")
ICO_ICON = os.path.join(EVERYTHING_ELSE, "ghost.ico")
ICON_PATH = PNG_ICON if os.path.exists(PNG_ICON) else ICO_ICON

def print_system_info():
    try:
        from core import print_system_summary
        print_system_summary()
    except ImportError:
        print("🖥️ GhostDrive Starting...")

main_window = None

def launch_main(username, passphrase, fernet):
    global main_window
    from ui.main_window import GhostDriveMainWindow
    main_window = GhostDriveMainWindow(username, passphrase, fernet)
    if os.path.exists(ICON_PATH):
        main_window.setWindowIcon(QIcon(ICON_PATH))
    main_window.show()

def main():
    # Parse CLI flags to check for daemon execution mode
    parser = argparse.ArgumentParser(description="GhostDrive Launcher", add_help=False)
    parser.add_argument("--daemon", "--agent-daemon", action="store_true", help="Launch background AI Agent Daemon")
    parser.add_argument("--config", type=str, help="Path to specific agent JSON configuration file")
    args, _ = parser.parse_known_args()

    # --- AUTO-MINIMIZE TERMINAL ---
    # Only runs on Windows when compiled as an EXE to keep the background clean
    if getattr(sys, 'frozen', False) and sys.platform == "win32":
        try:
            kernel32 = ctypes.WinDLL('kernel32')
            user32 = ctypes.WinDLL('user32')
            hWnd = kernel32.GetConsoleWindow()
            if hWnd != 0:
                user32.ShowWindow(hWnd, 6) # 6 = SW_MINIMIZE
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("GhostDrive")
    
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    # ===============================================================
    # [4] DAEMON LAUNCH BRANCH (Single Binary Dual-Personality)
    # ===============================================================
    if args.daemon:
        from core.Everything_else.agents.daemon import AgentDaemonWindow
        from core.paths import AGENT_CONFIGS_DIR
        
        # Fallback priority: explicit CLI arg -> active_agent.enc -> active_agent.json
        if args.config:
            config_path = args.config
        else:
            enc_fallback = os.path.join(AGENT_CONFIGS_DIR, "active_agent.enc")
            json_fallback = os.path.join(AGENT_CONFIGS_DIR, "active_agent.json")
            config_path = enc_fallback if os.path.exists(enc_fallback) else json_fallback

        daemon_win = AgentDaemonWindow(config_path=config_path)
        if os.path.exists(ICON_PATH):
            daemon_win.setWindowIcon(QIcon(ICON_PATH))
        daemon_win.show()
        sys.exit(app.exec())

    # ===============================================================
    # [5] STANDARD DESKTOP GUI LAUNCH BRANCH
    # ===============================================================
    if not getattr(sys, 'frozen', False):
        print_system_info()
    
    from ui.login_window import LoginWindow
    login = LoginWindow(on_login_success=launch_main)
    login.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()