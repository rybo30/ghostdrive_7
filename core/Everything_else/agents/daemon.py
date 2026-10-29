# daemon.py

import sys
import os
import platform
import argparse
import logging
import psutil
import subprocess
import time
from datetime import datetime
import traceback
import threading
import shutil
import stat
import json
import sqlite3
from pathlib import Path

# --- BOOTSTRAP PROJECT ROOT TO SYS.PATH ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.paths import (
    AGENT_RUNTIME_DIR,
    HOST_HIDDEN_DIR,
    get_target_os_key,
    get_agent_runtime_dir
)

# Early File Logging Setup
RUNTIME_DIR_PATH = Path(get_agent_runtime_dir()).resolve()
RUNTIME_DIR_PATH.mkdir(parents=True, exist_ok=True)
BOOT_LOG_PATH = RUNTIME_DIR_PATH / "daemon_boot.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BOOT_LOG_PATH, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logging.info("=" * 60)
logging.info(f"BOOTSTRAPPING MULTI-AGENT DAEMON [PID: {os.getpid()}]")
logging.info(f"Python Executable: {sys.executable}")
logging.info(f"Script/Binary: {__file__}")
logging.info("=" * 60)

try:
    from PySide6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QPushButton, QTextEdit, QProgressBar, QFrame, QCheckBox, QMessageBox
    )
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QTextCursor
except Exception as gui_import_err:
    logging.critical(f"Failed to import PySide6 components: {gui_import_err}\n{traceback.format_exc()}")

try:
    from core.Everything_else.agents.decrypt_agent import decrypt_agent_config
    from core.Everything_else.agents.ram_manager import RAMManager
    from core.Everything_else.agents.telegram_bot import TelegramBotGateway
    from core.Everything_else.agents.tool_runner import AgentToolRunner
    from core.Everything_else.agents.deploy_agent import get_runtime_executable_name
except ImportError as import_err:
    logging.warning(f"Core relative import failed ({import_err}). Attempting fallback imports...")
    try:
        from decrypt_agent import decrypt_agent_config
        from ram_manager import RAMManager
        from telegram_bot import TelegramBotGateway
        from tool_runner import AgentToolRunner
        from deploy_agent import get_runtime_executable_name
    except Exception as fallback_err:
        logging.critical(f"Fatal import failure in agent modules: {fallback_err}\n{traceback.format_exc()}")


def get_bundled_resource_path(relative_path: str) -> str:
    """Resolves absolute path to bundled resources, supporting PyInstaller's _internal directory."""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(PROJECT_ROOT)
    
    return str((base_path / relative_path).resolve())


def wipe_directory_contents(target_dir: str):
    """
    Synchronously and recursively purges all files and subdirectories 
    in target_dir, removing read-only flags on Windows before deletion.
    """
    if not os.path.exists(target_dir):
        return

    def _remove_readonly(func, path, exc_info):
        """Error handler to remove read-only/system flags if permission blocks deletion."""
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    for item in os.listdir(target_dir):
        item_path = os.path.join(target_dir, item)
        try:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, onerror=_remove_readonly)
            else:
                os.chmod(item_path, stat.S_IWRITE)
                os.remove(item_path)
        except Exception as e:
            logging.error(f"[KILL SWITCH] Failed to delete {item_path}: {e}")

    try:
        os.rmdir(target_dir)
    except Exception:
        pass


class SignalledHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:
            pass


class MultiAgentDaemonHUD(QWidget):
    log_signal = Signal(str)
    status_signal = Signal(str, str)

    def __init__(self, **kwargs):
        super().__init__()
        logging.info("Initializing GhostDrive Multi-Agent HUD...")
        
        self.agent_configs = {}
        self.gateways = {}
        self.execution_lock = threading.Lock()

        # 1. Discover and load all valid agent payloads in runtime directory
        self.discover_and_load_agents()

        # 2. Build UI
        self.init_ui()
        self.setup_logging()

        self.is_expanded = False

        # 3. Initialize Shared Processing Infrastructure
        self.init_multi_agent_gateways()

        # 4. Independent daemon thread loop
        self._scheduler_thread = threading.Thread(target=self._background_scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    def discover_and_load_agents(self):
        """Scans the runtime folder for all matching .enc and .key pairs."""
        runtime_dir = Path(get_agent_runtime_dir()).resolve()
        logging.info(f"Scanning runtime directory for encrypted agent payloads: {runtime_dir}")

        enc_files = list(runtime_dir.glob("*.enc"))
        if not enc_files:
            logging.warning(f"No .enc payload files found in {runtime_dir}")
            return

        for enc_file in enc_files:
            key_file = enc_file.with_suffix(".key")
            if not key_file.exists():
                matching_keys = [k for k in runtime_dir.glob("*.key") if k.stem.lower() == enc_file.stem.lower()]
                if matching_keys:
                    key_file = matching_keys[0]
                else:
                    logging.warning(f"Skipping {enc_file.name}: No corresponding .key file found.")
                    continue

            try:
                config = decrypt_agent_config(str(enc_file), key_path=str(key_file))
                agent_id = config.get("agent_id") or enc_file.stem
                self.agent_configs[agent_id] = config
                logging.info(f"[LOADED AGENT] '{config.get('agent_name', agent_id)}' (ID: {agent_id})")
            except Exception as e:
                logging.error(f"Failed to decrypt agent payload {enc_file.name}: {e}")

        logging.info(f"Successfully decrypted and loaded {len(self.agent_configs)} agent payloads into RAM.")

    def init_ui(self):
        count = len(self.agent_configs)
        status_subtext = f"{count} Assistant{'s' if count != 1 else ''} Online" if count else "Standing By"
        
        self.setWindowTitle("GhostDrive")

        icon_file = "ghost.icns" if platform.system() == "Darwin" else "ghost.ico"
        icon_path = get_bundled_resource_path(os.path.join("core", "Everything_else", icon_file))
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet("""
            QWidget { 
                background-color: #121417; 
                color: #E5E7EB; 
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", "Inter", sans-serif; 
            }
            QFrame#card { 
                background-color: #1A1D24; 
                border: 1px solid #2A2F3A; 
                border-radius: 14px; 
            }
            QLabel { 
                border: none; 
                background: transparent; 
            }
            QProgressBar { 
                border: none; 
                border-radius: 4px; 
                text-align: center; 
                background-color: #262B36; 
                color: #FFD700; 
                font-size: 11px; 
                font-weight: bold; 
            }
            QProgressBar::chunk { 
                background-color: #3B82F6; 
                border-radius: 4px; 
            }
            QTextEdit { 
                background-color: #0F1115; 
                border: 1px solid #232731; 
                color: #D1D5DB; 
                font-size: 12px; 
                border-radius: 10px; 
                padding: 10px; 
                line-height: 1.4;
            }
            QPushButton { 
                background-color: #262B36; 
                color: #F3F4F6; 
                border: 1px solid #374151; 
                border-radius: 8px; 
                font-weight: 600; 
                font-size: 12px; 
                padding: 6px 14px; 
            }
            QPushButton:hover { 
                background-color: #323846; 
                border-color: #4B5563; 
            }
            QPushButton#toggle_btn {
                background-color: #1E232D;
                color: #9CA3AF;
                border: 1px solid #2A2F3A;
            }
            QPushButton#toggle_btn:hover {
                color: #F3F4F6;
                background-color: #262B36;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        self.header_panel = QFrame()
        self.header_panel.setObjectName("card")
        header_layout = QVBoxLayout(self.header_panel)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(12)

        top_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        
        main_title = QLabel("GhostDrive")
        main_title.setStyleSheet("color: #FFFFFF; font-weight: 700; font-size: 15px; letter-spacing: -0.2px; background: transparent;")
        
        sub_title = QLabel(status_subtext)
        sub_title.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 500; background: transparent;")
        
        title_box.addWidget(main_title)
        title_box.addWidget(sub_title)

        self.status_indicator = QLabel("● Ready")
        self.status_indicator.setStyleSheet("color: #10B981; font-weight: 600; font-size: 12px; background: transparent;")

        top_row.addLayout(title_box)
        top_row.addStretch()
        top_row.addWidget(self.status_indicator)
        header_layout.addLayout(top_row)

        telemetry_layout = QHBoxLayout()
        telemetry_layout.setSpacing(12)

        ram_box = QVBoxLayout()
        ram_box.setSpacing(4)
        ram_lbl = QLabel("Memory")
        ram_lbl.setStyleSheet("color: #6B7280; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; background: transparent;")
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setFixedHeight(12)
        ram_box.addWidget(ram_lbl)
        ram_box.addWidget(self.ram_bar)

        cpu_box = QVBoxLayout()
        cpu_box.setSpacing(4)
        cpu_lbl = QLabel("Activity")
        cpu_lbl.setStyleSheet("color: #6B7280; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; background: transparent;")
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFixedHeight(12)
        cpu_box.addWidget(cpu_lbl)
        cpu_box.addWidget(self.cpu_bar)

        telemetry_layout.addLayout(ram_box)
        telemetry_layout.addLayout(cpu_box)
        header_layout.addLayout(telemetry_layout)

        self.main_layout.addWidget(self.header_panel)

        self.terminal_panel = QFrame()
        self.terminal_panel.setObjectName("card")
        term_layout = QVBoxLayout(self.terminal_panel)
        term_layout.setContentsMargins(14, 12, 14, 12)
        term_layout.setSpacing(8)

        term_hdr = QLabel("Activity Feed")
        term_hdr.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 600; background: transparent;")
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        term_layout.addWidget(term_hdr)
        term_layout.addWidget(self.log_view)

        self.main_layout.addWidget(self.terminal_panel)
        self.terminal_panel.setVisible(False)

        footer_layout = QHBoxLayout()
        self.hud_toggle = QPushButton("Show Activity")
        self.hud_toggle.setObjectName("toggle_btn")
        self.hud_toggle.setCheckable(True)
        self.hud_toggle.toggled.connect(self.toggle_hud_mode)

        self.min_btn = QPushButton("Minimize")
        self.min_btn.clicked.connect(self.showMinimized)
        
        footer_layout.addWidget(self.hud_toggle)
        footer_layout.addStretch()
        footer_layout.addWidget(self.min_btn)
        self.main_layout.addLayout(footer_layout)

        self.setFixedSize(420, 195)

        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(1000)

        self.log_signal.connect(self.append_log_message)
        self.status_signal.connect(self.set_status_badge)

    def toggle_hud_mode(self, enabled: bool):
        self.is_expanded = enabled
        self.terminal_panel.setVisible(enabled)
        self.hud_toggle.setText("Hide Activity" if enabled else "Show Activity")
        if enabled:
            self.setMinimumSize(600, 480)
            self.setMaximumSize(1000, 750)
            self.resize(640, 520)
        else:
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setFixedSize(420, 195)

    def set_status_badge(self, text: str, color_hex: str):
        status_map = {
            "IDLE": ("Ready", "#10B981"),
            "WAITING": ("Queued", "#F59E0B"),
            "PROCESSING": ("Working...", "#3B82F6"),
            "ERROR": ("Attention Needed", "#EF4444")
        }
        
        clean_text, clean_color = status_map.get(text.split(" ")[0].upper(), (text.capitalize(), color_hex))
        self.status_indicator.setText(f"● {clean_text}")
        self.status_indicator.setStyleSheet(
            f"color: {clean_color}; font-weight: 600; font-size: 12px; background: transparent;"
        )

    def init_multi_agent_gateways(self):
        if not self.agent_configs:
            logging.warning("No agent configurations active. Daemon standing by.")
            return

        self.ram_mgr = RAMManager()
        self.ram_mgr.start_monitoring()
        self.tool_runner = AgentToolRunner(ram_manager=self.ram_mgr)

        for agent_id, config in self.agent_configs.items():
            token = config.get("telegram_bot_token") or config.get("bot_token")
            agent_name = config.get("agent_name", agent_id)

            if not token:
                logging.warning(f"[{agent_name}] Missing telegram_bot_token. Gateway skipped.")
                continue

            def make_processor(agent_config):
                return lambda prompt, chat_id, user_history=None: self.process_incoming_task(
                    agent_config=agent_config,
                    prompt=prompt,
                    chat_id=chat_id,
                    user_history=user_history
                )

            db_filename = f"{agent_id}_state.db"

            gateway = TelegramBotGateway(
                bot_token=token,
                ram_manager=self.ram_mgr,
                task_processor=make_processor(config),
                db_name=db_filename,
                shutdown_callback=self.trigger_daemon_kill_switch
            )
            gateway.start()
            self.gateways[agent_id] = gateway
            logging.info(f"Telegram Gateway wired & active for agent '{agent_name}' with DB '{db_filename}'.")

    def process_incoming_task(self, agent_config: dict, prompt: str, chat_id: int, user_history: list = None) -> list:
        agent_name = agent_config.get("agent_name", "Agent")
        self.status_signal.emit(f"WAITING ({agent_name})", "#F59E0B")
        
        with self.execution_lock:
            self.status_signal.emit(f"PROCESSING ({agent_name})", "#3B82F6")
            try:
                logging.info(f"[{agent_name}] Processing prompt from Telegram chat #{chat_id}...")
                system_prompt = agent_config.get("system_prompt", "You are a helpful AI assistant.")
                model_filename = agent_config.get("model_filename") or agent_config.get("model_path")
                allowed_tools = agent_config.get("allowed_tools", [])

                responses = self.tool_runner.process_task(
                    prompt=prompt,
                    model_filename=model_filename,
                    system_prompt=system_prompt,
                    user_history=user_history,
                    allowed_tools=allowed_tools
                )
                self.status_signal.emit("IDLE", "#10B981")
                return responses
            except Exception as e:
                logging.error(f"[{agent_name}] Execution failed: {e}", exc_info=True)
                self.status_signal.emit("ERROR", "#EF4444")
                return [f"Error executing task: {str(e)}"]

    def trigger_daemon_kill_switch(self, kill_switch: bool = True):
        """Called when /kill command is received from Telegram."""
        logging.critical("[KILL SWITCH] Received self-destruct directive. Executing synchronous purge...")
        
        self.status_signal.emit("Kill Switch Activated - Purging System", "#EF4444")

        def _execute_purge_and_shutdown():
            time.sleep(1.0)  # Short delay allowing Telegram response transmission

            # Step 1: Explicitly stop all Telegram gateways and close DB locks
            for agent_id, gateway in list(self.gateways.items()):
                try:
                    gateway.stop()
                    if hasattr(gateway, 'db') and gateway.db:
                        gateway.db.close()
                        gateway.db = None
                except Exception as e:
                    logging.error(f"[KILL SWITCH] Error stopping gateway {agent_id}: {e}")

            if hasattr(self, 'ram_mgr') and self.ram_mgr:
                try:
                    self.ram_mgr.shutdown()
                except Exception:
                    pass

            # Step 2: Unbind Python file logging handlers to release daemon_boot.log
            for handler in logging.root.handlers[:]:
                try:
                    handler.close()
                    logging.root.removeHandler(handler)
                except Exception:
                    pass

            # Step 3: Hardcode target folder (~/.ghostdrive) and execute synchronous purge
            target_ghostdrive_dir = os.path.abspath(os.path.join(Path.home(), ".ghostdrive"))
            wipe_directory_contents(target_ghostdrive_dir)

            # Step 4: Issue System Shutdown directly from running process
            if kill_switch:
                if platform.system() == "Windows":
                    os.system("shutdown /s /f /t 0")
                else:
                    os.system("shutdown -h now || poweroff")

            # Step 5: Terminate daemon process
            os._exit(0)

        threading.Thread(target=_execute_purge_and_shutdown, daemon=True).start()





    def _background_scheduler_loop(self):
        """Runs continuously in the background, executing every 15 minutes cleanly between 10:15 PM and 4:00 AM."""
        logging.info("[Proactive Daemon] Background scheduling thread started with 10:15 PM - 4:00 AM 15-minute cadence.")
        
        # Ensure shared database exists for multi-agent coordination
        shared_db_path = Path.home() / ".ghostdrive" / "shared_agent_state.db"
        shared_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        def _init_shared_db():
            with sqlite3.connect(shared_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_notifications (
                        date_key TEXT NOT NULL,
                        notification_type TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        PRIMARY KEY (date_key, notification_type)
                    )
                """)
                conn.commit()
        
        _init_shared_db()

        briefing_hours = {8: "morning_briefing", 16: "closing_bell"}

        while True:
            try:
                now = datetime.now()
                current_hour = now.hour
                current_minute = now.minute
                date_str = now.strftime('%Y-%m-%d')
                
                # --- 1. CHECK FOR DYNAMIC DATABASE PINGS ---
                db_path = Path.home() / ".ghostdrive" / "scheduled_pings.db"
                if db_path.exists():
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT id, message FROM pings 
                            WHERE status = 'PENDING' AND datetime(trigger_at) <= datetime(?)
                        """, (now.strftime('%Y-%m-%d %H:%M:%S'),))
                        due_pings = cursor.fetchall()

                        for ping in due_pings:
                            ping_id = ping["id"]
                            ping_msg = ping["message"]
                            logging.info(f"[Dynamic Ping] Triggering scheduled ping ID #{ping_id}: {ping_msg}")

                            cursor.execute("UPDATE pings SET status = 'COMPLETED' WHERE id = ?", (ping_id,))
                            conn.commit()

                            for agent_id, config in self.agent_configs.items():
                                gateway = self.gateways.get(agent_id)
                                if gateway:
                                    def _run_dynamic_ping(g=gateway, cfg=config, msg=ping_msg):
                                        with self.execution_lock:
                                            chat_id = g.default_chat_id or g.get_fallback_chat_id()
                                            if not chat_id:
                                                return
                                            
                                            model_filename = cfg.get("model_filename") or cfg.get("model_path")
                                            system_prompt = cfg.get("system_prompt", "")
                                            allowed_tools = cfg.get("allowed_tools", [])

                                            responses = self.tool_runner.process_task(
                                                prompt=f"Scheduled reminder check-in: {msg}",
                                                model_filename=model_filename,
                                                system_prompt=system_prompt,
                                                allowed_tools=allowed_tools
                                            )
                                            if responses:
                                                for resp in responses:
                                                    g.send_message(chat_id, resp)

                                    threading.Thread(target=_run_dynamic_ping, daemon=True).start()
                        conn.close()
                    except Exception as db_err:
                        logging.error(f"[Dynamic Ping Error] Failed checking scheduled_pings.db: {db_err}")

                # --- 2. 10:15 PM TO 4:00 AM 15-MINUTE TESTING WINDOW ---
                # Total minutes from midnight: 10:15 PM = 1425 mins, 4:00 AM = 240 mins
                total_mins = current_hour * 60 + current_minute
                is_testing_window = (total_mins >= 1425) or (total_mins < 240)

                if is_testing_window:
                    # Calculate clean 15-min block offset starting from 10:15 PM (1425 mins)
                    adjusted_mins = total_mins if total_mins >= 1425 else total_mins + 1440
                    block_index = (adjusted_mins - 1425) // 15
                    pulse_key = f"{date_str}_15m_block_{block_index}"

                    if getattr(self, "_last_pulse_key", None) != pulse_key:
                        self._last_pulse_key = pulse_key
                        logging.info(f"[Autonomous Workshop] Testing Window Trigger -> Pulse Block: {pulse_key}")

                        for agent_id, config in self.agent_configs.items():
                            gateway = self.gateways.get(agent_id)
                            if not gateway:
                                continue

                            def _run_workshop(g=gateway, cfg=config, a_id=agent_id):
                                logging.info(f"[Workshop Worker] Starting thread for agent '{a_id}'...")
                                with self.execution_lock:
                                    chat_id = g.default_chat_id or g.get_fallback_chat_id()
                                    if not chat_id:
                                        # Fallback to last active chat ID in DB if default_chat_id is uninitialized
                                        chat_id = g.db.get_last_active_chat_id()
                                    
                                    if not chat_id:
                                        logging.warning(f"[Workshop Worker] Skipped: No chat_id found. Send a message to your Telegram bot first!")
                                        return

                                    logging.info(f"[Workshop Worker] Resolved chat #{chat_id}. Loading model & running pipeline...")
                                    history = g.db.get_recent_history(chat_id=chat_id, limit=6)
                                    profile = cfg.get("user_profile", {})
                                    active_projects = cfg.get("active_projects", [])
                                    model_filename = cfg.get("model_filename") or cfg.get("model_path")
                                    system_prompt = cfg.get("system_prompt", "")
                                    allowed_tools = cfg.get("allowed_tools", [])

                                    try:
                                        response = self.tool_runner.process_autonomous_workshop(
                                            chat_history=history,
                                            user_profile=profile,
                                            active_projects=active_projects,
                                            model_filename=model_filename,
                                            system_prompt=system_prompt,
                                            allowed_tools=allowed_tools
                                        )

                                        if response:
                                            logging.info(f"[Workshop Worker] Success! Dispatching proactive message to chat #{chat_id}")
                                            g.send_proactive_message(response, chat_id=chat_id)
                                        else:
                                            logging.warning(f"[Workshop Worker] Pipeline returned empty response.")
                                    except Exception as ex:
                                        logging.error(f"[Workshop Worker] Pipeline exception: {ex}", exc_info=True)

                            threading.Thread(target=_run_workshop, daemon=True).start()

                else:
                    # --- 3. STANDARD HOURLY / BRIEFING SCHEDULE OUTSIDE TESTING WINDOW ---
                    pulse_key = f"{date_str}_{current_hour}"
                    if getattr(self, "_last_pulse_key", None) != pulse_key:
                        self._last_pulse_key = pulse_key

                        if current_hour in briefing_hours:
                            briefing_type = briefing_hours[current_hour]
                            logging.info(f"[Briefing Engine] Evaluating {briefing_type} for hour block: {current_hour}:00")
                            # (Briefing execution logic...)

                        elif current_hour in {12, 20}:
                            logging.info(f"[Autonomous Workshop] Triggering standard background grind for hour block: {current_hour}:00")
                            # (Standard workshop execution logic...)

            except Exception as e:
                logging.error(f"[Proactive Daemon] Error in scheduler loop: {e}", exc_info=True)

            time.sleep(30)





    def setup_logging(self):
        handler = SignalledHandler(lambda msg: self.log_signal.emit(msg))
        handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', '%H:%M:%S'))
        
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

    def append_log_message(self, msg: str):
        self.log_view.append(msg)
        self.log_view.moveCursor(QTextCursor.End)

    def update_telemetry(self):
        self.cpu_bar.setValue(int(psutil.cpu_percent()))
        self.ram_bar.setValue(int(psutil.virtual_memory().percent))

    def closeEvent(self, event):
        for agent_id, gateway in self.gateways.items():
            gateway.stop()
        if hasattr(self, 'ram_mgr') and self.ram_mgr:
            self.ram_mgr.shutdown()
        event.accept()


AgentDaemonWindow = MultiAgentDaemonHUD


def enforce_host_execution():
    """
    Ensures process executes strictly from host machine storage (~/.ghostdrive/agents/runtime_[w|m|l]).
    """
    os_key = get_target_os_key()
    runtime_dir = Path(get_agent_runtime_dir(os_key)).resolve()
    current_exe = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve()

    logging.info(f"Checking Host Enforcement: Current={current_exe} | TargetRuntime={runtime_dir}")

    if runtime_dir not in current_exe.parents and current_exe.parent != runtime_dir:
        logging.info(f"[ENFORCE_HOST] External execution detected at {current_exe}. Forwarding to Host Runtime...")
        
        if getattr(sys, 'frozen', False):
            exe_name = get_runtime_executable_name(os_key)
            host_executable = runtime_dir / exe_name
        else:
            host_executable = runtime_dir / "daemon.py"

        if not host_executable.exists():
            err_msg = (
                f"[CRITICAL HOST ERROR] Host runtime binary missing at '{host_executable}'. "
                "Verify deploy_agent step completed on host machine."
            )
            logging.critical(err_msg)
            raise FileNotFoundError(err_msg)

        forward_args = sys.argv[1:]
        cmd = [str(host_executable)] + forward_args if getattr(sys, 'frozen', False) else [sys.executable, str(host_executable)] + forward_args

        logging.info(f"[ENFORCE_HOST] Spawning process: {' '.join(cmd)} (CWD: {runtime_dir})")
        
        kwargs = {"cwd": str(runtime_dir)}
        if os_key == "w":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **kwargs)
        logging.info(f"[ENFORCE_HOST] Successfully transferred process execution to PID {proc.pid}. Exiting parent process.")
        sys.exit(0)


def main():
    try:
        logging.info("Starting Multi-Agent Daemon execution loop...")
        
        # 1. Enforce Host Transfer
        enforce_host_execution()

        # 2. Launch Qt HUD Window
        app = QApplication.instance() or QApplication(sys.argv)
        daemon = MultiAgentDaemonHUD()
        daemon.show()
        logging.info("MultiAgentDaemonHUD visible. Entering Qt event loop.")
        sys.exit(app.exec())

    except Exception as e:
        err_msg = traceback.format_exc()
        logging.critical(f"FATAL BOOTSTRAP EXCEPTION IN MULTI-DAEMON:\n{err_msg}")
        
        crash_log = Path(get_agent_runtime_dir()) / "daemon_crash.log"
        with open(crash_log, "a", encoding="utf-8") as f:
            f.write(f"--- CRASH AT {Path(sys.executable).name} ---\n{err_msg}\n")

        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "GhostDrive Multi-Daemon Error", f"Fatal Exception:\n\n{str(e)}\n\nSee log file:\n{crash_log}")
        except Exception:
            pass
            
        sys.exit(1)


if __name__ == "__main__":
    main()