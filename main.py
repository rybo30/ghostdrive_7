# main.py

import sys
import os

# ===============================================================
# [0] THREAD LIMITS & EXCEPTION HOOKS (PERFORMANCE)
# ===============================================================
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"
os.environ["TORCH_NUM_THREADS"] = "2"

import traceback
from PySide6.QtCore import qInstallMessageHandler

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print("\n==================================================", file=sys.stderr)
    print("CRITICAL RUNTIME EXCEPTION DETECTED:", file=sys.stderr)
    print("==================================================", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
    print("==================================================\n", file=sys.stderr)

sys.excepthook = handle_exception

def qt_message_handler(mode, context, message):
    print(f"[Qt Msg]: {message}", file=sys.stderr)

qInstallMessageHandler(qt_message_handler)

import argparse
import ctypes
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
    parser = argparse.ArgumentParser(description="GhostDrive Launcher", add_help=False)
    parser.add_argument("--daemon", "--agent-daemon", action="store_true", help="Launch background AI Agent Daemon")
    parser.add_argument("--config", type=str, help="Path to specific agent JSON configuration file")
    args, _ = parser.parse_known_args()

    if getattr(sys, 'frozen', False) and sys.platform == "win32":
        try:
            kernel32 = ctypes.WinDLL('kernel32')
            user32 = ctypes.WinDLL('user32')
            hWnd = kernel32.GetConsoleWindow()
            if hWnd != 0:
                user32.ShowWindow(hWnd, 6)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("GhostDrive")
    
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    if args.daemon:
        from core.Everything_else.agents.daemon import AgentDaemonWindow
        from core.paths import AGENT_CONFIGS_DIR
        
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

    if not getattr(sys, 'frozen', False):
        print_system_info()
    
    from ui.login_window import LoginWindow
    login = LoginWindow(on_login_success=launch_main)
    login.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()