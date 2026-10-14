# ui/agents_page.py

import os
import sys
import uuid
import socket
import psutil
import json 
import subprocess
import importlib.util
import traceback
import fnmatch
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QRadioButton, QCheckBox, QFileDialog,
    QScrollArea, QFrame, QGridLayout, QComboBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal


from core.paths import (
    BASE_PATH, HOST_HIDDEN_DIR, AGENT_CONFIGS_DIR, AGENT_RUNTIME_DIR,
    EVERYTHING_ELSE, USB_FLEET_DIR, MODELS_DIR, USER_DATA,
    ensure_host_directories, get_target_os_key, get_agent_runtime_dir
)

from Everything_else.agents.deploy_agent import deploy_agent, get_runtime_executable_name

# Insert the agents directory into sys.path before importing agent modules
agents_dir = os.path.join(EVERYTHING_ELSE, "agents")
if agents_dir not in sys.path:
    sys.path.insert(0, agents_dir)

from .style_config import (
    T, COLOR_BG, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT_DIM,
    FONT_MAIN, STYLE_SCROLLBAR, STYLE_BUTTON, STYLE_INPUT, ghost_alert
)

from Everything_else.agents.save_agent_config import build_agent_payload, save_agent_config
from Everything_else.agents.load_agent import load_agent
from Everything_else.agents.agent_manifest import AgentManifest


def get_host_models_dir() -> str:
    """Returns the host models directory path dynamically."""
    return os.path.join(HOST_HIDDEN_DIR, "models")


def load_all_agent_configs(target_dir=USB_FLEET_DIR) -> list[dict]:
    """Helper to scan and decrypt all fleet configs using AgentManifest and load_agent."""
    manifest = AgentManifest(target_dir)
    registry = manifest.scan_fleet()
    configs = []
    for agent_id in registry:
        try:
            cfg = load_agent(agent_id, fleet_dir=target_dir)
            configs.append(cfg)
        except Exception as e:
            print(f"Failed to load config for agent '{agent_id}': {e}", file=sys.stderr)
    return configs


class ModelCopyWorker(QThread):
    progress = Signal(int)       # Percentage (0-100)
    finished = Signal(str)       # Destination path
    failed = Signal(str)         # Error message

    def __init__(self, src_path, filename):
        super().__init__()
        self.src_path = src_path
        self.filename = filename

    def run(self):
        try:
            ensure_host_directories()
            host_models_dir = get_host_models_dir()
            os.makedirs(host_models_dir, exist_ok=True)
            dest_path = os.path.join(host_models_dir, self.filename)

            if os.path.exists(dest_path):
                self.finished.emit(dest_path)
                return

            total_size = os.path.getsize(self.src_path)
            copied = 0
            buffer_size = 8 * 1024 * 1024  # 8MB chunk size

            with open(self.src_path, 'rb') as fsrc, open(dest_path, 'wb') as fdst:
                while True:
                    buf = fsrc.read(buffer_size)
                    if not buf:
                        break
                    fdst.write(buf)
                    copied += len(buf)
                    percent = int((copied / total_size) * 100)
                    self.progress.emit(percent)

            self.finished.emit(dest_path)
        except Exception as e:
            self.failed.emit(str(e))


class SectionPanel(QFrame):
    """Sleek tactical container panel replacing standard QGroupBox."""
    def __init__(self, title_text: str):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {T['BG_PANEL']};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 18, 20, 20)
        self.main_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        accent_bar = QFrame()
        accent_bar.setFixedWidth(4)
        accent_bar.setFixedHeight(14)
        accent_bar.setStyleSheet(f"background-color: {T['PROTOCOL_GOLD']}; border-radius: 2px; border: none;")
        
        header_lbl = QLabel(title_text.upper())
        header_lbl.setStyleSheet(f"""
            color: {T['TEXT_MAIN']};
            font-weight: 800;
            font-size: 11px;
            letter-spacing: 1.5px;
            border: none;
            background: transparent;
        """)

        header_layout.addWidget(accent_bar)
        header_layout.addWidget(header_lbl)
        header_layout.addStretch()

        self.main_layout.addLayout(header_layout)

    def getContentLayout(self):
        return self.main_layout


class AgentRow(QFrame):
    """Widget representing a single registered Agent as a flat horizontal row."""
    def __init__(self, agent_data: dict, parent_page):
        super().__init__()
        self.agent_data = agent_data
        self.parent_page = parent_page
        self.agent_id = agent_data.get("agent_id", "")
        self.target_host = agent_data.get("deployed_host", "Unknown Host")
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {T['BG_CARD']};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background-color: {T['BG_HOVER']};
                border-color: {COLOR_ACCENT};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(30)

        def make_column(header_text: str, value_widget: QWidget) -> QVBoxLayout:
            col_layout = QVBoxLayout()
            col_layout.setSpacing(4)
            
            hdr_lbl = QLabel(header_text.upper())
            hdr_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-weight: 800; font-size: 9px; letter-spacing: 1px; border: none; background: transparent;")
            
            col_layout.addWidget(hdr_lbl)
            col_layout.addWidget(value_widget)
            return col_layout

        # 1. AGENT NAME
        self.name_lbl = QLabel(agent_data.get("agent_name", "Unnamed Agent"))
        self.name_lbl.setWordWrap(True)
        self.name_lbl.setStyleSheet(f"color: {T['TEXT_MAIN']}; font-weight:bold; font-size: 13px; border: none; background: transparent;")
        layout.addLayout(make_column("Agent Name", self.name_lbl))

        # 2. STATUS
        self.status_badge = QLabel("● CHECKING...")
        self.status_badge.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        layout.addLayout(make_column("Status", self.status_badge))

        # 3. MODEL TYPE
        model_path = agent_data.get("model_path", "")
        model_name = os.path.basename(model_path) if model_path else "Default (GGUF)"
        self.model_lbl = QLabel(model_name)
        self.model_lbl.setWordWrap(True)
        self.model_lbl.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        layout.addLayout(make_column("Model", self.model_lbl))

        # 4. HOST MACHINE
        self.host_lbl = QLabel(self.target_host)
        self.host_lbl.setWordWrap(True)
        self.host_lbl.setStyleSheet(f"color: {T['TEXT_MAIN']}; font-size: 12px; border: none; background: transparent;")
        layout.addLayout(make_column("Host Machine", self.host_lbl))

        # 5. ACTIVE TOOLS
        tools_cnt = len(agent_data.get("allowed_tools", []))
        self.tools_lbl = QLabel(f"{tools_cnt} Enabled")
        self.tools_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 12px; border: none; background: transparent;")
        layout.addLayout(make_column("Tools", self.tools_lbl))

        layout.addStretch()

        # 6. ACTIONS
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.toggle_btn = QPushButton("RUN")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {T['PROTOCOL_GOLD']};
                border: 1px solid {T['PROTOCOL_GOLD']};
                font-weight: 800;
                font-size: 10px;
                padding: 6px 14px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {T['PROTOCOL_GOLD']};
                color: #000000;
            }}
        """)
        self.toggle_btn.clicked.connect(self.toggle_agent)

        self.delete_btn = QPushButton("REMOVE")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {T['DANGER']};
                border: 1px solid {T['DANGER']};
                font-weight: 800;
                font-size: 10px;
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {T['DANGER']};
                color: #ffffff;
            }}
        """)
        self.delete_btn.clicked.connect(self.delete_agent)

        btn_layout.addWidget(self.toggle_btn)
        btn_layout.addWidget(self.delete_btn)
        
        layout.addLayout(make_column("Actions", QWidget()))
        actions_col = layout.itemAt(layout.count() - 1).layout()
        actions_col.removeItem(actions_col.itemAt(1))
        actions_col.addLayout(btn_layout)

        self.refresh_status()

    def set_active_ui(self):
        self.status_badge.setText("● ACTIVE")
        self.status_badge.setStyleSheet(f"color: {T['PROTOCOL_GOLD']}; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        self.toggle_btn.setText("STOP")
        self.toggle_btn.setEnabled(True)

    def set_inactive_ui(self):
        self.status_badge.setText("● INACTIVE")
        self.status_badge.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        self.toggle_btn.setText("RUN")
        self.toggle_btn.setEnabled(True)

    def set_copying_ui(self, percent: int):
        self.status_badge.setText(f"● COPYING MODEL ({percent}%)")
        self.status_badge.setStyleSheet("color: #ff9800; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        self.toggle_btn.setEnabled(False)

    def refresh_status(self):
        # Look for matching config files on the USB fleet directory without pathlib
        pattern = f"*{self.agent_id}*"
        if os.path.exists(USB_FLEET_DIR):
            matches = [
                os.path.join(USB_FLEET_DIR, f) 
                for f in os.listdir(USB_FLEET_DIR) 
                if fnmatch.fnmatch(f, pattern)
            ]
        else:
            matches = []

        if not matches:
            self.set_inactive_ui()
            return

        is_running = False
        pid = self.parent_page.get_active_pid(self.agent_id)
        
        if pid and psutil.pid_exists(pid):
            is_running = True
        else:
            for proc in psutil.process_iter(['cmdline']):
                try:
                    cmdline = proc.info.get('cmdline') or []
                    cmd_str = " ".join(cmdline)
                    if "--daemon" in cmdline and (f"agent_{self.agent_id}.json" in cmd_str or f"agent_{self.agent_id}.enc" in cmd_str):
                        is_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        if is_running:
            self.set_active_ui()
        else:
            self.set_inactive_ui()

    def toggle_agent(self):
        self.parent_page.toggle_agent_execution(
            self.agent_id, 
            progress_callback=self.set_copying_ui
        )
        self.refresh_status()

    def delete_agent(self):
        self.parent_page.delete_agent_config(self.agent_id)


class AgentsPage(QWidget):
    def __init__(self, username, passphrase, fernet, engine=None, manifest=None):
        super().__init__()
        self.username = username
        self.passphrase = passphrase
        self.fernet = fernet
        self.engine = engine
        self.manifest = manifest
        
        self.active_processes = {}
        self.tool_checkboxes = {}

        self.init_ui()
        self.refresh_fleet_grid()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_fleet_statuses)
        self.status_timer.start(8000)

    def init_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_BG};
                color: {T['TEXT_MAIN']};
                font-family: '{FONT_MAIN}', sans-serif;
                font-size: 12px;
            }}
            {STYLE_SCROLLBAR}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 35, 40, 40)
        main_layout.setSpacing(24)

        # --- TOP HEADER ---
        title_box = QHBoxLayout()
        title_box.setSpacing(12)
    
        gold_tag = QFrame()
        gold_tag.setFixedWidth(6)
        gold_tag.setFixedHeight(24)
        gold_tag.setStyleSheet(f"background-color: {T['PROTOCOL_GOLD']}; border-radius: 3px;")
    
        title = QLabel("AGENTS & FLEET AUTOMATION")
        title.setStyleSheet(f"color: {T['TEXT_MAIN']}; font-weight: 800; font-size: 18px; letter-spacing: 1.5px;")
    
        title_box.addWidget(gold_tag)
        title_box.addWidget(title)
        title_box.addStretch()
    
        main_layout.addLayout(title_box)

        # --- SCROLL CONTAINER ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
    
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setSpacing(24)
        layout.setContentsMargins(0, 0, 10, 0)

        # Standardized style for field labels across all sections
        label_style = f"color: {COLOR_TEXT_DIM}; font-weight: 700; font-size: 11px; letter-spacing: 1px; border: none;"

        # --- SECTION 1: GLOBAL FLEET DASHBOARD ---
        fleet_panel = SectionPanel("MASTER AGENT FLEET DASHBOARD (GLOBAL)")
        self.fleet_layout = fleet_panel.getContentLayout()
    
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent; border: none;")
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(0, 8, 0, 0)
        self.cards_grid.setSpacing(12)
    
        self.fleet_layout.addWidget(self.cards_container)
        layout.addWidget(fleet_panel)

        # --- SECTION 2: DEPLOY NEW AGENT ---
        config_panel = SectionPanel("DEPLOY NEW AGENT TO HOST MACHINE")
        cfg_layout = config_panel.getContentLayout()

        grid_cfg = QGridLayout()
        grid_cfg.setContentsMargins(0, 10, 0, 0)
        grid_cfg.setSpacing(12)

        # Row 0: Agent Name & Telegram Token
        lbl_name = QLabel("AGENT NAME")
        lbl_name.setStyleSheet(label_style)
        grid_cfg.addWidget(lbl_name, 0, 0)

        lbl_token = QLabel("TELEGRAM UPLINK BOT TOKEN")
        lbl_token.setStyleSheet(label_style)
        grid_cfg.addWidget(lbl_token, 0, 1)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Rex, Tony, etc.")
        self.name_input.setStyleSheet(STYLE_INPUT)
        grid_cfg.addWidget(self.name_input, 1, 0)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("123456789:ABCdefGHIjklMNOpqrsTUVwxyZ")
        self.token_input.setStyleSheet(STYLE_INPUT)
        grid_cfg.addWidget(self.token_input, 1, 1)

        # Row 2: Main Job / Prompt
        lbl_prompt = QLabel("WHAT IS THEIR MAIN JOB?")
        lbl_prompt.setStyleSheet(label_style)
        grid_cfg.addWidget(lbl_prompt, 2, 0, 1, 2)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("You are an autonomous AI agent...")
        self.prompt_input.setMaximumHeight(80)
        self.prompt_input.setStyleSheet(STYLE_INPUT)
        grid_cfg.addWidget(self.prompt_input, 3, 0, 1, 2)

        # Row 4: GGUF Model Path
        lbl_model = QLabel("LOCAL GGUF MODEL PATH")
        lbl_model.setStyleSheet(label_style)
        grid_cfg.addWidget(lbl_model, 4, 0, 1, 2)

        model_row = QHBoxLayout()
        model_row.setSpacing(12)
    
        self.model_path_input = QLineEdit()
        self.model_path_input.setStyleSheet(STYLE_INPUT)
    
        model_browse_btn = QPushButton("CHOOSE MODEL")
        model_browse_btn.setCursor(Qt.PointingHandCursor)
        model_browse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['BG_CARD']};
                color: {T['TEXT_MAIN']};
                border: 1px solid {COLOR_BORDER};
                font-weight: 700;
                font-size: 11px;
                padding: 10px 18px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {T['BG_HOVER']};
                border-color: {T['PROTOCOL_GOLD']};
                color: {T['PROTOCOL_GOLD']};
            }}
        """)
        model_browse_btn.clicked.connect(self.browse_model)
        model_row.addWidget(self.model_path_input)
        model_row.addWidget(model_browse_btn)

        grid_cfg.addLayout(model_row, 5, 0, 1, 2)
        cfg_layout.addLayout(grid_cfg)
        layout.addWidget(config_panel)

        # --- SECTION 3: USER QUESTIONNAIRE ---
        quest_panel = SectionPanel("ABOUT YOU (OPTIONAL)")
        quest_layout = quest_panel.getContentLayout()

        grid_quest = QGridLayout()
        grid_quest.setContentsMargins(0, 10, 0, 0)
        grid_quest.setSpacing(12)

        # Row 0: Preferred Name & Profession
        lbl_quest_name = QLabel("PREFERRED NAME")
        lbl_quest_name.setStyleSheet(label_style)
        grid_quest.addWidget(lbl_quest_name, 0, 0)

        lbl_occupation = QLabel("OCCUPATION / ROLE")
        lbl_occupation.setStyleSheet(label_style)
        grid_quest.addWidget(lbl_occupation, 0, 1)

        self.quest_name = QLineEdit()
        self.quest_name.setPlaceholderText("e.g. Alex")
        self.quest_name.setStyleSheet(STYLE_INPUT)
        grid_quest.addWidget(self.quest_name, 1, 0)

        self.quest_occupation = QLineEdit()
        self.quest_occupation.setPlaceholderText("e.g. Software Engineer, Founder, Student")
        self.quest_occupation.setStyleSheet(STYLE_INPUT)
        grid_quest.addWidget(self.quest_occupation, 1, 1)

        # Row 2: Goals & Tech Stack / Environment
        lbl_goals = QLabel("ACTIVE GOALS")
        lbl_goals.setStyleSheet(label_style)
        grid_quest.addWidget(lbl_goals, 2, 0)

        lbl_tools = QLabel("DAILY TOOLS & TECH STACK")
        lbl_tools.setStyleSheet(label_style)
        grid_quest.addWidget(lbl_tools, 2, 1)

        self.quest_goals = QLineEdit()
        self.quest_goals.setPlaceholderText("e.g. Launching a desktop app, staying organized")
        self.quest_goals.setStyleSheet(STYLE_INPUT)
        grid_quest.addWidget(self.quest_goals, 3, 0)

        self.quest_tools = QLineEdit()
        self.quest_tools.setPlaceholderText("e.g. Python, macOS, PySide6, Docker")
        self.quest_tools.setStyleSheet(STYLE_INPUT)
        grid_quest.addWidget(self.quest_tools, 3, 1)

        # Row 4: Hobbies & Passions
        lbl_interests = QLabel("HOBBIES & INTERESTS")
        lbl_interests.setStyleSheet(label_style)
        grid_quest.addWidget(lbl_interests, 4, 0, 1, 2)

        self.quest_interests = QLineEdit()
        self.quest_interests.setPlaceholderText("e.g. Baking, retro gaming, basketball, 3D printing")
        self.quest_interests.setStyleSheet(STYLE_INPUT)
        grid_quest.addWidget(self.quest_interests, 5, 0, 1, 2)

        # Row 6: Custom Context
        lbl_context = QLabel("ADDITIONAL AI NOTES")
        lbl_context.setStyleSheet(label_style)
        grid_quest.addWidget(lbl_context, 6, 0, 1, 2)

        self.quest_context = QLineEdit()
        self.quest_context.setPlaceholderText("e.g. Keep answers concise, skip fluff")
        self.quest_context.setStyleSheet(STYLE_INPUT)
        grid_quest.addWidget(self.quest_context, 7, 0, 1, 2)

        quest_layout.addLayout(grid_quest)
        layout.addWidget(quest_panel)

        # --- SAVE BUTTON ---
        self.save_btn = QPushButton("SAVE AGENT TO FLEET")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(STYLE_BUTTON)
        self.save_btn.clicked.connect(self.save_new_agent)
        layout.addWidget(self.save_btn)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def refresh_tools(self):
        """No-op stub to retain compatibility with UI initialization calls."""
        pass


    def browse_model(self):
        initial_dir = MODELS_DIR if os.path.exists(MODELS_DIR) else BASE_PATH
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "SELECT GGUF BINARY", 
            initial_dir, 
            "GGUF Models (*.gguf)"
        )
        if file_path:
            self.model_path_input.setText(file_path)


    def get_user_profile_from_ui(self) -> dict:
        """Extracts questionnaire values from UI inputs."""
        return {
            "preferred_name": self.quest_name.text().strip(),
            "occupation": self.quest_occupation.text().strip(),
            "active_goals": self.quest_goals.text().strip(),
            "daily_tools": self.quest_tools.text().strip(),
            "hobbies_interests": self.quest_interests.text().strip(),
            "additional_notes": self.quest_context.text().strip()
        }

    def save_new_agent(self):
        try:
            # Automatically include all available tools in the tools directory
            tools_dir = os.path.join(EVERYTHING_ELSE, "agents", "tools")
            enabled_tools = []
            if os.path.exists(tools_dir):
                for file in sorted(os.listdir(tools_dir)):
                    if file.endswith("_tool.py") and not file.startswith("__"):
                        enabled_tools.append(file[:-3])
        
            mail_user = self.mail_user_input.text() if hasattr(self, "mail_user_input") else None
            mail_pass = self.mail_pass_input.text() if hasattr(self, "mail_pass_input") else None
            mail_server = self.mail_provider_select.currentData() if hasattr(self, "mail_provider_select") else None

            # Collect profile inputs from the UI
            user_profile_data = self.get_user_profile_from_ui()

            config_data, enc_path, key_path = build_agent_payload(
                agent_name=self.name_input.text(),
                model_path=self.model_path_input.text(),
                system_prompt=self.prompt_input.toPlainText(),
                telegram_token=self.token_input.text(),
                scheduled_ping=self.get_schedule_config_from_ui(),
                user_profile=user_profile_data,  # <--- PASSING PROFILE TO PAYLOAD
                allowed_tools=enabled_tools,
                mail_user=mail_user,
                mail_pass=mail_pass,
                mail_server=mail_server,
                target_dir=USB_FLEET_DIR
            )

            ghost_alert(self, "SAVED TO FLEET", f"Agent '{config_data['agent_name']}' encrypted (.enc + .key) and saved with user profile.")

            # Reset UI controls
            self.name_input.clear()
            self.prompt_input.clear()
            self.token_input.clear()
            self.model_path_input.clear()
            self.quest_name.clear()
            self.quest_occupation.clear()
            self.quest_goals.clear()
            self.quest_tools.clear()
            self.quest_interests.clear()
            self.quest_context.clear()

            if hasattr(self, "mail_user_input"):
                self.mail_user_input.clear()
                self.mail_pass_input.clear()

            self.refresh_fleet_grid()

        except FileNotFoundError as fnf_err:
            ghost_alert(self, "DEPLOYMENT WARNING", str(fnf_err))
        except ValueError as val_err:
            ghost_alert(self, "CREDENTIALS REQUIRED", str(val_err))
        except Exception as e:
            print("\n=== [SAVE AGENT ERROR] ===", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            ghost_alert(self, "SYSTEM ERROR", f"Failed to save agent config: {str(e)}")



    def refresh_fleet_grid(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.card_widgets = []
        configs = load_all_agent_configs(target_dir=USB_FLEET_DIR)

        if self.manifest and self.engine:
            try:
                entries = self.manifest.get_entries_by_category("agent_config")
                loaded_ids = {cfg.get("agent_id") for cfg in configs if "agent_id" in cfg}
        
                for entry in entries:
                    ghost_id = entry.get("ghost_id") or entry.get("id")
                    if ghost_id:
                        decrypted_bytes = self.engine.decrypt_file_to_memory(ghost_id)
                        cfg = json.loads(decrypted_bytes.decode("utf-8"))
                        if cfg.get("agent_id") not in loaded_ids:
                            configs.append(cfg)
            except Exception as e:
                print(f"Error loading agent configs from manifest: {e}", file=sys.stderr)

        if not configs:
            empty_lbl = QLabel("No active agents registered in master fleet. Configure one below!")
            empty_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-style: italic; font-size: 12px; padding: 15px; border: none;")
            self.cards_grid.addWidget(empty_lbl, 0, 0)
            return

        for idx, cfg in enumerate(configs):
            row_widget = AgentRow(cfg, self)
            self.cards_grid.addWidget(row_widget, idx, 0)
            self.card_widgets.append(row_widget)


    def toggle_agent_execution(self, agent_id: str, progress_callback=None):
        proc = self.active_processes.get(agent_id)

        if proc and proc.poll() is None:
            proc.terminate()
            del self.active_processes[agent_id]
            return

        try:
            os_key = get_target_os_key()
            host_runtime_dir = get_agent_runtime_dir(os_key)
            os.makedirs(host_runtime_dir, exist_ok=True)

            # 1. Transport agent artifacts to OS host runtime folder
            host_config_path = deploy_agent(
                agent_or_id=agent_id,
                target_dir=host_runtime_dir,
                source_dir=USB_FLEET_DIR,
                progress_callback=progress_callback,
                os_key=os_key
            )

            # 2. Determine OS execution command
            if getattr(sys, 'frozen', False):
                exe_name = get_runtime_executable_name(os_key)
                host_executable = os.path.join(host_runtime_dir, exe_name)

                if not os.path.exists(host_executable):
                    raise FileNotFoundError(
                        f"Executable missing at '{host_executable}' for platform '{os_key}'."
                    )

                cmd = [
                    host_executable,
                    "--daemon",
                    "--config", host_config_path
                ]
            else:
                daemon_script = os.path.join(host_runtime_dir, "daemon.py")
                cmd = [
                    sys.executable,
                    daemon_script,
                    "--daemon",
                    "--config", host_config_path
                ]

            # 3. Launch host binary directly with cwd set to host runtime dir
            self.active_processes[agent_id] = subprocess.Popen(
                cmd,
                env=os.environ.copy(),
                cwd=host_runtime_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os_key == "w" else 0
            )

        except Exception as e:
            print(f"[!] Launch failed for agent '{agent_id}': {e}", file=sys.stderr)
            ghost_alert(self, "Launch Error", f"Failed to deploy or run agent: {e}")


    def refresh_fleet_statuses(self):
        if hasattr(self, 'card_widgets'):
            for card in self.card_widgets:
                card.refresh_status()

    def get_active_pid(self, agent_id: str):
        proc = self.active_processes.get(agent_id)
        if proc and proc.poll() is None:
            return proc.pid
        return None

    def delete_agent_config(self, agent_id: str):
        config_filename_json = f"agent_{agent_id}.json"
        config_filename_enc = f"agent_{agent_id}.enc"

        # 1. Terminate directly tracked active process
        proc = self.active_processes.get(agent_id)
        if proc:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            del self.active_processes[agent_id]

        # 2. Kill matching system background daemon processes
        for p in psutil.process_iter(['cmdline']):
            try:
                cmdline = p.info.get('cmdline') or []
                cmd_str = " ".join(cmdline)
                if "--daemon" in cmdline and (config_filename_json in cmd_str or config_filename_enc in cmd_str):
                    p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # 3. Purge host & USB config files via AgentManifest
        manifest = AgentManifest(USB_FLEET_DIR)
        paths = manifest.get_agent_paths(agent_id)
        for p in (paths.get("enc_path"), paths.get("key_path"), paths.get("json_path")):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception as e:
                    print(f"Failed to remove file {p}: {e}", file=sys.stderr)

        # 4. Purge matching entries from Vault Manifest
        if getattr(self, "manifest", None):
            try:
                entries = self.manifest.get_entries_by_category("agent_config")
                for entry in entries:
                    ghost_id = entry.get("ghost_id") or entry.get("id")
                    
                    is_match = False
                    if entry.get("name") in (config_filename_json, config_filename_enc):
                        is_match = True
                    elif ghost_id and getattr(self, "engine", None):
                        try:
                            decrypted_bytes = self.engine.decrypt_file_to_memory(ghost_id)
                            cfg = json.loads(decrypted_bytes.decode("utf-8"))
                            if cfg.get("agent_id") == agent_id:
                                is_match = True
                        except Exception:
                            pass

                    if is_match and ghost_id:
                        payload_path = os.path.join(USER_DATA, ghost_id)
                        if os.path.exists(payload_path):
                            os.remove(payload_path)
                        
                        self.manifest.remove_entry(ghost_id)
                        break
            except Exception as e:
                print(f"Error purging agent from vault manifest: {e}", file=sys.stderr)

        # 5. Refresh UI Grid
        self.refresh_fleet_grid()

    

    def toggle_schedule_inputs(self, enabled: bool):
        if hasattr(self, "sched_inputs_widget"):
            self.sched_inputs_widget.setEnabled(enabled)

    def get_schedule_config_from_ui(self) -> dict:
        topics = []
        if getattr(self, "cb_stock", None) and self.cb_stock.isChecked():
            topics.append("stock_market")
        if getattr(self, "cb_weather", None) and self.cb_weather.isChecked():
            topics.append("weather")
        if getattr(self, "cb_sports", None) and self.cb_sports.isChecked():
            topics.append("sports_news")

        enabled = self.sched_enabled_cb.isChecked() if hasattr(self, "sched_enabled_cb") else False
        custom_query = self.agent_sched_custom.text().strip() if hasattr(self, "agent_sched_custom") else ""
        target_time = self.agent_sched_time.text().strip() if hasattr(self, "agent_sched_time") else "08:00"
        interval_hours = 12 if (hasattr(self, "rb_12h") and self.rb_12h.isChecked()) else 24

        return {
            "enabled": enabled,
            "topics": topics,
            "custom_query": custom_query,
            "target_time": target_time or "08:00",
            "interval_hours": interval_hours,
            "total_pings": -1
        }

    def populate_schedule_ui_from_config(self, agent_config: dict):
        sched = agent_config.get("scheduled_ping", {})
    
        is_enabled = sched.get("enabled", False)
        if hasattr(self, "sched_enabled_cb"):
            self.sched_enabled_cb.setChecked(is_enabled)
        if hasattr(self, "sched_inputs_widget"):
            self.sched_inputs_widget.setEnabled(is_enabled)

        topics = sched.get("topics", [])
        if hasattr(self, "cb_stock"):
            self.cb_stock.setChecked("stock_market" in topics)
        if hasattr(self, "cb_weather"):
            self.cb_weather.setChecked("weather" in topics)
        if hasattr(self, "cb_sports"):
            self.cb_sports.setChecked("sports_news" in topics)

        if hasattr(self, "agent_sched_custom"):
            self.agent_sched_custom.setText(sched.get("custom_query", ""))
        if hasattr(self, "agent_sched_time"):
            self.agent_sched_time.setText(sched.get("target_time", "08:00"))

        if sched.get("interval_hours", 24) == 12:
            if hasattr(self, "rb_12h"):
                self.rb_12h.setChecked(True)
        else:
            if hasattr(self, "rb_24h"):
                self.rb_24h.setChecked(True)