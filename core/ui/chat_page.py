# [chat_page.py] 

import sys, os, gc, importlib
import re
import random
import string
import pypdf

from .style_config import (
    T, FONT_FAMILY, FONT_SIZE, TacticalDialog,
    STYLE_BUTTON, STYLE_INPUT, STYLE_LABEL,
    COLOR_BG, COLOR_FG, COLOR_ACCENT, COLOR_BUTTON, 
    COLOR_HIGHLIGHT, COLOR_BORDER, COLOR_PROTOCOL, COLOR_PAGE_BG
)


# --- System Imports ---
from core.paths import MODELS_DIR
from core.Everything_else.command_checker import check_for_commands
from core.Everything_else.jynx_operator_ui import execute_command, get_random_prompt, soul_vent, soul_vent_summon
from core.Everything_else.model_registry import load_model_from_config, get_model_config, get_all_model_configs, get_visual_description, unload_previous_model, sync_unregistered_models
from core.Everything_else.ai_council import run_council_streaming
from core.Everything_else.chat_manager import ChatLogManager
from core.Everything_else.encryption_engine import GhostEngine
from core.Everything_else.manifest_manager import ManifestManager


# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QStackedWidget,
    QHBoxLayout, QComboBox, QMessageBox, QInputDialog, QFileDialog, QLabel, QApplication,
    QDialog, QDialogButtonBox, QFrame, QListWidget, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QEvent, QTimer, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup, QUrl
from PySide6.QtGui import QTextCursor, QTextOption, QFont, QPixmap, QKeyEvent, QColor

# --- Optional WebEngine Import Handling ---
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False


# =====================================================================
# HuggingFace
# =====================================================================

class HuggingFaceHubDialog(QDialog):
    def __init__(self, parent=None, initial_url=None):
        super().__init__(parent)
        self.setWindowTitle("HuggingFace Core")
        self.setMinimumSize(1024, 768)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint) # Clean frameless look
        self.setStyleSheet(f"background-color: {COLOR_BG}; border: 1px solid {COLOR_BORDER};")

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- Sleek Top Header Bar ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(5, 5, 5, 5)

        title_label = QLabel("HUGGINGFACE")
        title_label.setStyleSheet(f"""
            color: {T.get('PROTOCOL_GOLD', '#FFB000')}; 
            font-family: 'Consolas', monospace; 
            font-size: 13px; 
            font-weight: bold; 
            letter-spacing: 1px;
        """)

        # Navigation controls
        self.back_btn = QPushButton("◄")
        self.forward_btn = QPushButton("►")
        self.reload_btn = QPushButton("↻")
        
        nav_style = f"""
            QPushButton {{
                background: {COLOR_BUTTON};
                color: {COLOR_FG};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                border: 1px solid {COLOR_ACCENT};
                color: {COLOR_ACCENT};
            }}
        """
        for btn in (self.back_btn, self.forward_btn, self.reload_btn):
            btn.setStyleSheet(nav_style)
            btn.setFixedWidth(30)

        # Single Exit / Close Button (Replaces the confusing Confirm/Abort buttons)
        close_btn = QPushButton("✕ EXIT")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 85, 85, 0.1);
                color: #FF5555;
                border: 1px solid #FF5555;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                font-weight: bold;
                padding: 5px 15px;
            }}
            QPushButton:hover {{
                background-color: #FF5555;
                color: black;
            }}
        """)
        close_btn.clicked.connect(self.accept)

        top_bar.addWidget(title_label)
        top_bar.addSpacing(15)
        top_bar.addWidget(self.back_btn)
        top_bar.addWidget(self.forward_btn)
        top_bar.addWidget(self.reload_btn)
        top_bar.addStretch()
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)

        # --- Browser Engine ---
        self.browser = QWebEngineView()
        self.browser.setStyleSheet("border: none;")
        
        # Connect navigation buttons
        self.back_btn.clicked.connect(self.browser.back)
        self.forward_btn.clicked.connect(self.browser.forward)
        self.reload_btn.clicked.connect(self.browser.reload)

        # Profile & Download handler
        profile = self.browser.page().profile()
        profile.downloadRequested.connect(self.handle_download_request)

        # Initial URL Target
        target_url = initial_url or "https://huggingface.co/models?pipeline_tag=text-generation&library=gguf&sort=trending"
        self.browser.setUrl(QUrl(target_url))
        
        layout.addWidget(self.browser)

    def handle_download_request(self, download_item):
        """Intercepts the web browser download and forces it into the local app models folder."""
        target_dir = MODELS_DIR 
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        suggested_filename = download_item.suggestedFileName()
        full_download_path = os.path.join(target_dir, suggested_filename)
        
        download_item.setDownloadDirectory(target_dir)
        download_item.setDownloadFileName(suggested_filename)
        download_item.accept()
        
        print(f"📥 Downloading Core Model to: {full_download_path}")
        
        total_bytes = download_item.totalBytes()
        
        download_item.receivedBytesChanged.connect(
            lambda: self.update_download_status(suggested_filename, download_item.receivedBytes(), total_bytes)
        )
        
        download_item.stateChanged.connect(
            lambda state: self.handle_download_state_change(suggested_filename, state)
        )

    def update_download_status(self, filename, bytes_received, bytes_total):
        """Tracks background progress matrix."""
        if bytes_total > 0:
            percent = (bytes_received / bytes_total) * 100
            sys.stdout.write(f"\rSyncing {filename}: {percent:.1f}%")
            sys.stdout.flush()

    def handle_download_state_change(self, filename, state):
        """Alerts when the state transitions to finished or interrupted."""
        if state == 2:  # Completed
            print(f"\n\n✅ SUCCESS: {filename} fully downloaded and integrated.")
            sync_unregistered_models()
            if hasattr(self.parent(), 'refresh_model_dropdown'):
                self.parent().refresh_model_dropdown()
                
        elif state == 3:  # Interrupted / Cancelled
            print(f"\n\n❌ ERROR: Download interrupted for {filename}.")


# =====================================================================
# Workers
# =====================================================================
class StreamWorker(QObject):
    token_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, llm_fn, prompt, max_tokens=2048, temperature=0.7, image_path=None):
        super().__init__()
        self.llm_fn = llm_fn
        self.prompt = prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.image_path = image_path 

    def run(self):
        try:
            if not self.llm_fn:
                raise Exception("LLM Engine not initialized.")
            
            # FIXED: Consumes clean raw strings directly passed from model_registry factory
            for chunk in self.llm_fn(
                self.prompt, 
                max_tokens=self.max_tokens, 
                temperature=self.temperature,
                image_path=self.image_path,
                stream_override=True 
            ):
                if chunk:
                    self.token_received.emit(str(chunk))
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class CouncilStreamWorker(QObject):
    token_received = Signal(object)
    finished = Signal()
    error = Signal(str)

    def __init__(self, user_prompt, image_path=None, username="Operator", fernet=None, chat_history=None):
        super().__init__()
        self.user_prompt = user_prompt
        self.image_path = image_path
        self.username = username 
        self.fernet = fernet 
        self.chat_history = chat_history if chat_history is not None else []

    def run(self):
        try:
            # FIXED: Threaded workers now pass stateful history objects directly down into council bounds
            for event in run_council_streaming(
                self.user_prompt, 
                image_path=self.image_path, 
                username=self.username, 
                fernet=self.fernet,
                chat_history=self.chat_history
            ):
                self.token_received.emit(event)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

# =====================================================================
# Dialog Components
# =====================================================================

class ProtocolDialog(TacticalDialog):
    def __init__(self, parent=None, title="PROTOCOL", label="INPUT:", items=None, readonly_text=None, is_password=False):
        super().__init__(parent, title=title, label=label, is_password=is_password)
        
        if items:
            self.input_field.hide()
            self.selector = QListWidget()
            self.selector.addItems(items)
            self.selector.setStyleSheet(f"""
                QListWidget {{
                    background: #000000;
                    color: {T['PROTOCOL_GOLD']};
                    border: 1px solid {T['HUD_LINE']};
                    border-radius: 4px;
                    font-family: 'Consolas';
                }}
            """)
            self.container.layout().insertWidget(3, self.selector)
            
        elif readonly_text:
            self.input_field.hide()
            self.view = QTextEdit()
            self.view.setPlainText(readonly_text)
            self.view.setReadOnly(True)
            self.view.setStyleSheet(self.container.styleSheet() + "background: #000000;")
            self.container.layout().insertWidget(3, self.view)

    def get_value(self):
        if hasattr(self, 'selector'):
            item = self.selector.currentItem()
            return item.text() if item else ""
        return super().get_value()

def ghost_prompt(parent, title, label):
    dialog = ProtocolDialog(parent, title=title, label=label)
    if dialog.exec() == QDialog.Accepted:
        return dialog.get_value(), True
    return "", False


# =====================================================================
# Main ChatPage
# =====================================================================
class ChatPage(QWidget):
    def __init__(self, username, passphrase, fernet, debug=False, engine=None, manifest=None):
        super().__init__()
        self.username = username
        self.passphrase = passphrase
        self.fernet = fernet
        self.debug = debug

        sync_unregistered_models()

        self.engine = engine if engine else GhostEngine(self.fernet)
        self.manifest = manifest if manifest else ManifestManager(self.engine, self.username)
        self.chat_manager = ChatLogManager(self.engine, self.manifest)

        self.current_session_id = None  
        self.current_ai_response = ""
        self.chat_history_data = []
        self.council_accumulation = ""

        self.llm = None
        self.current_image_path = None 
        self.model_config = get_model_config("jynx_summarizer")
        
        self.max_tokens = self.model_config.get("max_tokens", 2048)
        self.temperature = self.model_config.get("temperature", 0.7)
        
        self._active_thread = None
        self._active_worker = None

        # PDF
        self.active_document_context = ""
        self.active_document_name = ""

        self.setAcceptDrops(True) 
        self.init_ui()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.process_attachment(files[0])

    def init_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # --- SIDEBAR ---
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(280)
        self.sidebar.setObjectName("Sidebar")
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(20, 30, 20, 20)
        
        id_label = QLabel("CHATLOGS")
        id_label.setObjectName("SidebarHeaderLabel")
        sidebar_layout.addWidget(id_label)
        
        sidebar_layout.addSpacing(20)

        self.new_chat_btn = QPushButton("+ NEW SESSION")
        self.new_chat_btn.setObjectName("ChatActionBtn") 
        self.new_chat_btn.setFixedHeight(50)
        sidebar_layout.addWidget(self.new_chat_btn)

        sidebar_layout.addSpacing(20)

        hist_label = QLabel("ENCRYPTED ARCHIVES")
        hist_label.setStyleSheet(f"color: {T.get('TEXT_DIM', '#666')}; font-weight: bold; font-size: 9px; letter-spacing: 1px;")
        sidebar_layout.addWidget(hist_label)

        self.history_list = QListWidget()
        self.history_list.setObjectName("HistoryList")
        sidebar_layout.addWidget(self.history_list)

        self.new_chat_btn.clicked.connect(self.start_new_session)
        self.history_list.itemClicked.connect(self.on_log_selected)

        self.refresh_history_list()
        self.layout.addWidget(self.sidebar)

        # --- MAIN CHAT CONTAINER ---
        self.chat_container = QWidget()
        self.main_chat_layout = QVBoxLayout(self.chat_container)
        self.main_chat_layout.setContentsMargins(30, 15, 30, 25)
        
        header = QHBoxLayout()
        
        self.toggle_sidebar_btn = QPushButton("☰")
        self.toggle_sidebar_btn.setFixedSize(40, 40)
        self.toggle_sidebar_btn.setObjectName("MenuToggleBtn")
        self.toggle_sidebar_btn.clicked.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        
        self.model_selector = QComboBox()
        self.model_selector.setFixedWidth(220)
        self.model_selector.setFixedHeight(40)
        self.model_selector.currentIndexChanged.connect(self.handle_model_selector_change)

        self.refresh_model_dropdown()

        self.protocol_button = QPushButton("PROTOCOL")
        self.protocol_button.setObjectName("HeaderProtocolBtn")
        self.protocol_button.setFixedSize(100, 40)
        self.protocol_button.clicked.connect(self.manual_protocol_trigger)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")        
        
        header.addWidget(self.toggle_sidebar_btn)
        header.addSpacing(15)
        header.addWidget(self.status_label)
        header.addStretch()
        header.addWidget(self.protocol_button)
        header.addSpacing(10)
        header.addWidget(self.model_selector)
        self.main_chat_layout.addLayout(header)

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard) 
        self.chat_area.setFocusPolicy(Qt.ClickFocus)
        self.chat_area.setObjectName("ChatDisplay")
        self.main_chat_layout.addWidget(self.chat_area)

        self.image_preview = QLabel()
        self.image_preview.setFixedHeight(110)
        self.image_preview.setObjectName("ImagePreview")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.hide()
        self.main_chat_layout.addWidget(self.image_preview)

        # 1. CREATE THE HORIZONTAL ROW CONTAINER FOR INPUT ELEMENTS
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 5, 0, 0)
        input_layout.setSpacing(8)

        # 2. INSTANTIATE THE MATCHING SIZED FILE TRIGGER BUTTON
        self.attach_btn = QPushButton("+", self)
        self.attach_btn.setObjectName("SovereignAttachBtn")
        self.attach_btn.setFixedWidth(50)     # Slightly wider to prevent it from looking skinny
        self.attach_btn.setFixedHeight(100)   # Matches the text box height exactly
        self.attach_btn.setCursor(Qt.PointingHandCursor)
        self.attach_btn.setToolTip("Inject Document/Image Asset into Core Layer")
        
        gold_accent = T.get('PROTOCOL_GOLD', '#FFB000')
        dim_text = T.get('TEXT_DIM', '#777777')
        self.attach_btn.setStyleSheet(f"""
            QPushButton#SovereignAttachBtn {{
                background: transparent;
                color: {dim_text};
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 18px; /* Slightly larger text to balance out the larger block */
                font-weight: bold;
            }}
            QPushButton#SovereignAttachBtn:hover {{
                color: {gold_accent};
                border: 1px solid {gold_accent};
                background: rgba(255, 176, 0, 0.02);
            }}
        """)
        self.attach_btn.clicked.connect(self.trigger_manual_file_selection)

        # 3. INSTANTIATE THE INPUT TEXT EDIT FIELD
        self.input_line = QTextEdit()
        self.input_line.installEventFilter(self)
        self.input_line.setPlaceholderText("Ready when you are, Chief!")
        self.input_line.setFixedHeight(100)
        self.input_line.setObjectName("ChatInput")

        # 4. CHRONOLOGICALLY PACK THEM AND INJECT ROW INTO MAIN LAYOUT
        input_layout.addWidget(self.attach_btn, 0, Qt.AlignVCenter) # Aligns perfectly inline with the entry field
        input_layout.addWidget(self.input_line, 1)
        self.main_chat_layout.addLayout(input_layout)

        self.layout.addWidget(self.chat_container)
        self.apply_dynamic_theme()

    def apply_dynamic_theme(self):
        gold = T.get('PROTOCOL_GOLD', '#FFB000')
        tech_blue = "#00A3FF" 
        bg_card = T.get('BG_CARD', '#121212')
        border_col = T.get('BORDER', '#2A2A2A')
        text_main = T.get('TEXT_MAIN', '#E0E0E0')
        accent = T.get('ACCENT', '#00FF00')
        
        main_style = f"""
            QWidget#Sidebar {{
                background-color: #0A0C0E;
                border-right: 1px solid {border_col};
            }}
            QLabel#SidebarHeaderLabel {{
                color: {tech_blue}; 
                font-weight: 900; 
                font-size: 10px; 
                letter-spacing: 2px;
            }}
            QListWidget#HistoryList {{
                border: none;
                background: transparent;
                color: {T.get('TEXT_DIM', '#888')};
                font-family: 'Consolas';
                font-size: 13px;
                outline: none;
            }}
            QListWidget#HistoryList::item {{
                padding: 12px;
                border-radius: 5px;
                margin-bottom: 5px;
            }}
            QListWidget#HistoryList::item:hover {{
                background: rgba(0, 163, 255, 0.05);
            }}
            QTextEdit#ChatDisplay {{
                background-color: transparent;
                border: none;
                color: {text_main};
                font-size: 16px;
                line-height: 1.6;
            }}
            QTextEdit#ChatInput {{
                background-color: {bg_card};
                border: 1px solid {border_col};
                border-radius: 12px;
                color: {text_main};
                padding: 15px;
                font-size: 15px;
            }}
            QTextEdit#ChatInput:focus {{
                border: 1px solid {tech_blue};
            }}
            QComboBox {{
                background: {bg_card};
                color: {tech_blue};
                border: 1px solid {border_col};
                border-radius: 6px;
                padding-left: 10px;
                font-weight: bold;
            }}
            QPushButton#MenuToggleBtn {{
                background-color: transparent;
                color: {tech_blue};
                border: 1px solid {border_col};
                border-radius: 8px;
                font-weight: bold;
                font-size: 18px;
            }}
            QPushButton#MenuToggleBtn:hover {{
                border: 1px solid {tech_blue};
                background: rgba(0, 163, 255, 0.05);
            }}
            QPushButton#HeaderProtocolBtn {{
                background-color: rgba(255, 176, 0, 0.05);
                color: {gold};
                border: 1px solid {gold};
                border-radius: 6px;
                font-size: 10px;
                font-weight: 900;
                letter-spacing: 1px;
            }}
            QPushButton#HeaderProtocolBtn:hover {{
                background-color: {gold};
                color: black;
            }}
            QPushButton#ChatActionBtn {{
                background-color: rgba(0, 163, 255, 0.03);
                color: {tech_blue};
                border: 1px solid {tech_blue};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 900;
                letter-spacing: 1.5px;
            }}
            QPushButton#ChatActionBtn:hover {{
                background-color: {tech_blue};
                color: black;
            }}
            QLabel#StatusLabel {{
                color: {accent};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
        """
        self.setStyleSheet(main_style)
        self.chat_area.setStyleSheet(f"background: transparent; color: {text_main}; border: none;")
        self.input_line.setStyleSheet(f"background: {bg_card}; color: {text_main}; border: 1px solid {border_col}; border-radius: 12px;")


#####################################################
# AI Model Selection & Management
#####################################################

    def check_default_model_status(self):
        """Checks if models directory contains any usable GGUF files."""
        if not os.path.exists(MODELS_DIR):
            os.makedirs(MODELS_DIR, exist_ok=True)
        
        gguf_files = [f for f in os.listdir(MODELS_DIR) if f.endswith(".gguf")]
    
        if not gguf_files:
            # Prompt user to get the recommended default model
            QTimer.singleShot(500, self.prompt_default_model_download)

    def prompt_default_model_download(self):
        msg = (
            "No default GGUF model detected in local directory.\n\n"
            "Would you like to open the embedded HuggingFace Hub to download "
            "the recommended Mistral 7B / GGUF model?"
        )
        reply = QMessageBox.information(
            self, 
            "GHOSTDRIVE // INITIAL SETUP", 
            msg, 
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply == QMessageBox.Ok:
            # Launch HF Hub with a pre-filtered search URL for Mistral 7B GGUF
            self.trigger_huggingface_hub_ui_targeted("https://huggingface.co/models?pipeline_tag=text-generation&library=gguf&search=mistral+7b")

    def handle_model_selector_change(self, index):
        selected_data = self.model_selector.itemData(index)
        if selected_data == "add_model_action":
            # Instantly bounce back to placeholder so + Add Model can be clicked again
            self.model_selector.setCurrentIndex(0)
            self.trigger_huggingface_hub_ui()

    def refresh_model_dropdown(self):
        self.model_selector.blockSignals(True)
        current_key = self.model_selector.itemData(self.model_selector.currentIndex())
        self.model_selector.clear()
        
        # 1. PLACEHOLDER AT INDEX 0
        self.model_selector.addItem("Choose Your Model", "select_model_placeholder")
        
        # 2. + ADD MODEL AT INDEX 1
        self.model_selector.addItem("+ Add Model", "add_model_action")
        self.model_selector.insertSeparator(self.model_selector.count())
        
        # --- Check if Mistral 7B model exists before offering Multi-Model Reasoning ---
        mistral_path = os.path.join(MODELS_DIR, "mistral-7b-instruct-v0.2.Q4_K_M.gguf")
        has_mistral = os.path.exists(mistral_path)
        
        if has_mistral:
            self.model_selector.addItem("Multi-Model Reasoning", "multi_model_reasoning")
        
        expert_items = []
        user_items = []
        
        core_system_exclusions = [
            "models", "jynx_default", "jynx_summarizer", "jynx_judge", 
            "password_suggester", "jynx_vision", "ollie_whisper"
        ]
        
        try:
            all_models = get_all_model_configs() or {}
            for config_key, details in all_models.items():
                if config_key in core_system_exclusions:
                    continue
                display_name = details.get("name", config_key)
                
                if config_key.startswith("jynx_expert_"):
                    if has_mistral:
                        expert_items.append((display_name, config_key))
                else:
                    user_items.append((display_name, config_key))
                    
            expert_items.sort(key=lambda x: x[0])
            user_items.sort(key=lambda x: x[0])
            
            for display_name, config_key in expert_items:
                self.model_selector.addItem(display_name, config_key)
                
            if user_items:
                self.model_selector.insertSeparator(self.model_selector.count())
                for display_name, config_key in user_items:
                    self.model_selector.addItem(f"📦 {display_name}", config_key)
                    
        except Exception as e:
            print(f"Error dynamically populating model dropdown from registry: {e}")

        # Preserve previously selected active model if valid, else keep placeholder at index 0
        if current_key and current_key not in ("add_model_action", "select_model_placeholder"):
            index = self.model_selector.findData(current_key)
            if index >= 0:
                self.model_selector.setCurrentIndex(index)
            else:
                self.model_selector.setCurrentIndex(0)
        else:
            self.model_selector.setCurrentIndex(0)
            
        self.model_selector.blockSignals(False)

    def trigger_huggingface_hub_ui(self):
        dialog = HuggingFaceHubDialog(self)
        dialog.exec()
        self.refresh_model_dropdown()

    def trigger_huggingface_hub_ui_targeted(self, target_url):
        """Launches the HF marketplace pre-navigated to a specific search or model URL."""
        dialog = HuggingFaceHubDialog(self, initial_url=target_url)
        dialog.exec()
        self.refresh_model_dropdown()



# =====================================================================
# Core Execution Engine Integration
# =====================================================================
    def handle_reason(self):
        """Unified entrypoint handling both Single Expert and Council layout structures safely."""
        prompt = self.input_line.toPlainText().strip()
        image_path = self.current_image_path

        if not prompt and not image_path: 
            return
        
        # 1. Update UI View Canvas
        self.append_message("You", prompt if prompt else "[FILE ATTACHED]")
        if image_path: 
            self.append_image_to_chat(image_path)
        
        self.input_line.clear()
        self.clear_attachment()
        
        # Capture raw item baseline info before background loop allocations
        current_item = self.history_list.currentItem()
        session_name = current_item.text() if current_item else ((prompt[:25] + '...') if len(prompt) > 25 else "New Chat")

        # 2. Update Internal Memory Context Arrays
        self.chat_history_data.append({"role": "You", "content": prompt})

        selected_key = self.model_selector.currentData()
        selected_mode_text = self.model_selector.currentText()

        # 3. Allocating Worker Architectures Safely
        if selected_key == "multi_model_reasoning":
            self._summary_started = False 
            self.status_label.setText("● COUNCIL REASONING")
            self.council_accumulation = ""
            
            self._active_thread = QThread()
            # FIXED: Safely passing rolling state history copies down cleanly into core tracking layers
            self._active_worker = CouncilStreamWorker(
                prompt, 
                image_path=image_path, 
                username=self.username, 
                fernet=self.fernet,
                chat_history=list(self.chat_history_data)
            )
            self._active_worker.token_received.connect(self._handle_council_event)
            self._active_worker.finished.connect(self._finalize_ai_response)
        
        else:
            model_id = selected_key if selected_key else "jynx_summarizer"
            self.current_model_name = selected_mode_text  # <-- Save current model name
            self.status_label.setText(f"● {selected_mode_text.upper()} ACTIVE")
            self.chat_area.insertHtml(f"<br><br><b style='color:{T.get('PROTOCOL_GOLD', '#FFB000')};'>{selected_mode_text.upper()}:</b><br>")
            
            llm_fn, config = load_model_from_config(model_id)
            m_tokens = config.get("max_tokens", 2048)
            m_temp = config.get("temperature", 0.5)
            
            self.current_ai_response = ""
            self._active_thread = QThread()
            # FIXED: Explicit keyword arguments mapped safely to standard parameters
            self._active_worker = StreamWorker(
                llm_fn=llm_fn, 
                prompt=prompt, 
                max_tokens=m_tokens, 
                temperature=m_temp, 
                image_path=image_path
            )
            self._active_worker.token_received.connect(self._append_streamed_token)
            self._active_worker.finished.connect(self._finalize_ai_response)

        # 4. Thread Safety Management Loops
        self._active_worker.moveToThread(self._active_thread)
        self._active_worker.error.connect(lambda e: self.append_message("SYSTEM", f"ERROR: {e}"))
        self._active_worker.finished.connect(self._active_thread.quit)
        self._active_worker.finished.connect(self._active_worker.deleteLater)
        self._active_thread.finished.connect(self._active_thread.deleteLater)
        self._active_thread.started.connect(self._active_worker.run)
        
        self._active_worker.finished.connect(lambda: self.status_label.setText("● AI ENGINE ONLINE"))
        self._active_thread.start()

    def _handle_council_event(self, event):
        etype = event[0]
        self.chat_area.moveCursor(QTextCursor.End)
    
        if etype == "summary":
            if not getattr(self, "_summary_started", False):
                header = f"<br><br><b style='color:{T['PROTOCOL_GOLD']};'>TARGET:</b><br>"
                self.chat_area.insertHtml(header)
                self.council_accumulation += header 
                self._summary_started = True
        
            raw_token = str(event[1]).replace("***SUMMARY***", "").replace("***EXPERTS***", "")
            if raw_token: 
                self.chat_area.insertPlainText(raw_token)
                self.council_accumulation += raw_token

        elif etype == "expert_start":
            self._summary_started = False 
            expert_name = str(event[1]).upper()
            header = f"<br><br><b style='color:{COLOR_ACCENT};'>{expert_name}:</b><br>"
            self.chat_area.insertHtml(header)
            self.council_accumulation += header 
        
        elif etype == "expert_token":
            if len(event) >= 3:
                token = str(event[2])
                self.chat_area.insertPlainText(token)
                self.council_accumulation += token

        elif etype == "verdict_start":
            header = f"<br><br><b style='color:{T['PROTOCOL_GOLD']};'>FINAL VERDICT:</b><br>"
            self.chat_area.insertHtml(header)
            self.council_accumulation += header 

        elif etype == "verdict_token":
            token = str(event[1])
            self.chat_area.insertPlainText(token)
            self.council_accumulation += token

    def _finalize_ai_response(self):
        """Finalizes the session text generation loop and commits updates to local storage."""
        if hasattr(self, 'status_label'):
            self.status_label.setText("")
            
        final_text = ""
        is_council = False

        if hasattr(self, 'council_accumulation') and self.council_accumulation:
            final_text = self.council_accumulation.strip()
            self.council_accumulation = "" # Reset cache
            is_council = True  # <--- Mark as Council response
        elif hasattr(self, 'current_ai_response') and self.current_ai_response:
            final_text = self.current_ai_response.strip()
            self.current_ai_response = ""

        if final_text:
            # Assign 'COUNCIL' if council mode, otherwise use the active model's display name
            if is_council:
                role_type = "COUNCIL"
            else:
                role_type = getattr(self, 'current_model_name', 'assistant')
            
            self.chat_history_data.append({
                "role": role_type,
                "content": final_text,
                "timestamp": os.time() if hasattr(os, 'time') else __import__('time').time()
            })

            # 4. SECURE AUTO-SAVE COMMIT PIPELINE
            try:
                # Fallback Title generation based on the initial prompt if a real one isn't set yet
                session_title = "Secure Analysis Session"
                if len(self.chat_history_data) >= 1:
                    first_msg = self.chat_history_data[0].get("content", "")
                    session_title = first_msg[:30].strip() + "..." if len(first_msg) > 30 else first_msg

                # Write changes back through your ChatLogManager to handle encryption mechanics
                new_session_id = self.chat_manager.save_chatlog(
                    history=self.chat_history_data,
                    name=session_title,
                    log_id=self.current_session_id
                )
                
                # If this was a brand-new chat block, retain the generated persistent log ID tracking reference
                if not self.current_session_id:
                    self.current_session_id = new_session_id

                # Ensure the root manifest commits the asset metadata table changes to disk
                if hasattr(self.manifest, 'save'):
                    self.manifest.save()

                # Refresh your visual archive list sidebar module immediately to reflect state changes
                self.refresh_history_list()

            except Exception as save_err:
                print(f"[STORAGE ERROR] Cryptographic write operation failed: {save_err}")

        # Clean up worker memory states completely
        if self._active_thread:
            self._active_thread.quit()
            self._active_thread.wait()
            self._active_thread = None
        self._active_worker = None

    def _commit_current_history(self):
        """Internal helper to write the verified history stack to the secure vault file."""
        current_item = self.history_list.currentItem()
        
        # If no item is selected but we have an active session running, fallback gracefully
        if current_item:
            session_name = current_item.text()
        else:
            session_name = "Active Session"
            if self.chat_history_data:
                first_msg = self.chat_history_data[0].get("content", "")
                # Clean out any HTML headers to grab plain tracking text
                clean_txt = re.sub('<[^<]+?>', '', first_msg).strip()
                session_name = (clean_txt[:22] + '...') if len(clean_txt) > 22 else (clean_txt if clean_txt else "Active Session")
        
        new_id = self.chat_manager.save_chatlog(
            self.chat_history_data, 
            log_id=self.current_session_id,
            name=session_name
        )
        
        # INSTANT RETENTION ALIGNMENT: Lock state immediately before any UI click events can happen
        self.current_session_id = new_id
        
        # If the item was tagged as a volatile placeholder session, anchor it down permanently
        if current_item and current_item.data(Qt.UserRole) == "new_session":
            current_item.setData(Qt.UserRole, new_id)
            # Retain current string context while syncing data maps
            current_item.setText(session_name)
            self.status_label.setText(f"● SESSION: {session_name.upper()}")
            
        # Re-verify layout alignments inside the list registry framework
        self.refresh_history_list()
        
        # Keep the visual highlight focused exactly on the active log item after refreshing
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            if item.data(Qt.UserRole) == new_id:
                self.history_list.blockSignals(True)
                self.history_list.setCurrentItem(item)
                self.history_list.blockSignals(False)
                break

    def _append_streamed_token(self, token):
        self.current_ai_response += token
        self.chat_area.insertPlainText(token)
        self.chat_area.moveCursor(QTextCursor.End)

    def on_log_selected(self, item):
        ghost_id = item.data(Qt.UserRole)
        self.chat_area.clear()

        if ghost_id == "new_session":
            self.chat_history_data = []
            self.current_session_id = None
            self.status_label.setText(f"● SESSION: {item.text().upper()}")
            return

        history = self.chat_manager.load_chatlog(ghost_id)
        if history is not None:
            self.chat_history_data = history
            self.current_session_id = ghost_id
            
            for msg in history:
                role = msg.get('role', 'AI')
                content = msg.get('content', '')
                
                if role == "You":
                    formatted_user = content.replace('\n', '<br>')
                    self.append_message("You", formatted_user)
                elif role == "COUNCIL" or content.strip().startswith("<br>") or content.strip().startswith("<b>TARGET:"):
                    # Preserve line breaks by converting newlines to <br> while preserving HTML headers
                    formatted_council = content.replace('\n', '<br>')
                    self.chat_area.insertHtml(formatted_council)
                else:
                    clean_content = content.replace('\n', '<br>')
                    if clean_content.startswith("<br>"):
                        self.chat_area.insertHtml(f"<br><br><b style='color:{COLOR_ACCENT};'>{role}:</b>{clean_content}")
                    else:
                        self.chat_area.insertHtml(f"<br><br><b style='color:{COLOR_ACCENT};'>{role}:</b> <br>{clean_content}")
            
            self.chat_area.moveCursor(QTextCursor.End)

    def start_new_session(self):
        name, ok = ghost_prompt(self, "INITIALIZE SESSION", "ENTER SESSION IDENTITY:")
        if ok and name.strip():
            session_name = name.strip()
            self.chat_area.clear()
            self.current_session_id = None
            self.chat_history_data = []
            
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(session_name)
            item.setData(Qt.UserRole, "new_session") 
            self.history_list.insertItem(0, item)
            self.history_list.setCurrentItem(item)

            self.status_label.setText(f"● SESSION: {session_name.upper()}")
            self.input_line.setFocus()

    def refresh_history_list(self):
        self.history_list.blockSignals(True)
        self.history_list.clear()
        logs = self.chat_manager.get_all_logs() or []
        for log in logs:
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(log['name'])
            item.setData(Qt.UserRole, log['id'])
            self.history_list.addItem(item)
        self.history_list.blockSignals(False)

    def contextMenuEvent(self, event):
        if self.history_list.underMouse():
            item = self.history_list.itemAt(self.history_list.mapFrom(self, event.pos()))
            if not item: return

            ghost_id = item.data(Qt.UserRole)
            if ghost_id == "new_session": return 

            from PySide6.QtWidgets import QMenu
            from PySide6.QtGui import QAction

            menu = QMenu(self)
            menu.setStyleSheet(f"background-color: #1A1A1A; color: {T.get('TEXT_MAIN', '#E0E0E0')}; border: 1px solid #333;")

            rename_action = QAction("RENAME", self)
            delete_action = QAction("DELETE", self)

            rename_action.triggered.connect(lambda: self.rename_session_ui(item))
            delete_action.triggered.connect(lambda: self.delete_session_ui(item))

            menu.addAction(rename_action)
            menu.addAction(delete_action)
            menu.exec(event.globalPos())

    def rename_session_ui(self, item):
        ghost_id = item.data(Qt.UserRole)
        new_name, ok = ghost_prompt(self, "RENAME SESSION", "ENTER NEW IDENTITY:")
        if ok and new_name.strip():
            new_name = new_name.strip()
            if self.chat_manager.rename_chatlog(ghost_id, new_name):
                item.setText(new_name)
                if self.current_session_id == ghost_id:
                    self.status_label.setText(f"● SESSION: {new_name.upper()}")

    def delete_session_ui(self, item):
        ghost_id = item.data(Qt.UserRole)
        session_name = item.text()

        dialog = TacticalDialog(self, title="DATA TERMINATION", label="")
        if hasattr(dialog, 'input_field'):
            dialog.input_field.hide()
    
        for child in dialog.container.findChildren(QLabel):
            if child.text() == "CRITICAL WARNING":
                child.hide()

        msg = QLabel(f"DELETE SESSION: {session_name}?\n\nThis action is final and cannot be undone.")
        msg.setStyleSheet(f"color: {T['PROTOCOL_GOLD']}; font-family: 'Consolas'; font-size: 14px; padding: 30px 10px;")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
    
        dialog.container.layout().insertWidget(3, msg)
        dialog.setFixedWidth(400)

        if dialog.exec() == QDialog.Accepted:
            if self.chat_manager.remove_chatlog(ghost_id):
                if self.current_session_id == ghost_id:
                    self.chat_area.clear()
                    self.current_session_id = None
                    self.chat_history_data = []
                    self.status_label.setText("● SESSION DELETED")
                self.refresh_history_list()

    def eventFilter(self, obj, event):
        if obj == self.input_line:
            # Tell the input box to ignore drag/drop events so they fall through 
            # to the native MainWindow overrides we just configured!
            if event.type() in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop):
                event.ignore()
                return False

            elif event.type() == QEvent.KeyPress:
                key_event = QKeyEvent(event) 
                if key_event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    if key_event.modifiers() & Qt.ShiftModifier:
                        return False
                    else:
                        self.handle_reason()
                        return True 
                        
        return super().eventFilter(obj, event)


    def process_attachment(self, path):
        normalized_path = os.path.normpath(path)
        ext = normalized_path.lower().split('.')[-1] if '.' in normalized_path else ''
        
        # Reset any previous document state when a new file comes in
        self.active_document_context = ""
        self.active_document_name = ""
        
        if ext in ('png', 'jpg', 'jpeg', 'webp', 'bmp'):
            self.current_image_path = normalized_path
            pixmap = QPixmap(normalized_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaledToHeight(90, Qt.SmoothTransformation)
                self.image_preview.setPixmap(scaled_pixmap)
                self.image_preview.show()
            else:
                self.image_preview.setText(f"⚠️ [IMAGE CORRUPT]: {os.path.basename(normalized_path)}")
                self.image_preview.show()
        else:
            self.current_image_path = None # Non-images don't route to the visual vision model path
            
            # Check if the document is a PDF for parsing context
            if ext == 'pdf':
                try:
                    text_content = []
                    with open(normalized_path, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        for page_num, page in enumerate(reader.pages):
                            page_text = page.extract_text()
                            if page_text:
                                text_content.append(f"--- PAGE {page_num + 1} ---\n{page_text}")
                    
                    if text_content:
                        self.active_document_context = "\n\n".join(text_content)
                        self.active_document_name = os.path.basename(normalized_path)
                        preview_label = f"📄 [SECURE INTEL LOADED]: {self.active_document_name} ({len(self.active_document_context)} chars)"
                    else:
                        preview_label = f"⚠️ [EMPTY/SCANNED PDF]: {os.path.basename(normalized_path)}"
                except Exception as e:
                    preview_label = f"❌ [PDF PARSE ERROR]: {str(e)}"
            else:
                # Fallback for other non-image attachments
                preview_label = f"📄 [ATTACHED CORE DOCUMENT]: {os.path.basename(normalized_path)}"

            # Show a clean protocol-themed file placeholder block in the preview row
            gold_color = T.get('PROTOCOL_GOLD', '#FFB000')
            self.image_preview.setText(preview_label)
            self.image_preview.setStyleSheet(f"""
                QLabel#ImagePreview {{
                    color: {gold_color};
                    font-family: 'Consolas';
                    font-size: 13px;
                    border: 1px dashed {T.get('BORDER', '#2A2A2A')};
                    background-color: rgba(255, 176, 0, 0.02);
                    padding: 10px;
                }}
            """)
            self.image_preview.show()
            
            # Automatically drop the absolute path string reference into the context prompt area 
            # so the user or the underlying file system wrapper can read it instantly
            current_text = self.input_line.toPlainText().strip()
            if current_text:
                self.input_line.setPlainText(f"{current_text}\n\n[File Reference: {normalized_path}]")
            else:
                self.input_line.setPlainText(f"[File Reference: {normalized_path}]")
                
        self.apply_dynamic_theme()

    def clear_attachment(self):
        self.current_image_path = None
        self.image_preview.hide()
        # Reset stylesheet context back to default image handling dimensions
        self.image_preview.setStyleSheet("QLabel#ImagePreview { background: transparent; }")
        self.apply_dynamic_theme()

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if path: self.process_attachment(path)

    def append_message(self, sender, text):
        color = COLOR_ACCENT if sender != "You" else COLOR_FG
        html = f"<br><br><span style='color:{color}; font-weight: bold;'>{sender.upper()}:</span><span style='color:{COLOR_FG};'> {text}</span>"
        self.chat_area.insertHtml(html)
        self.chat_area.moveCursor(QTextCursor.End)

    def append_image_to_chat(self, image_path):
        if not image_path: return
        html = f"<br><div style='margin-left: 20px;'><img src='{image_path}' width='300'></div><br>"
        self.chat_area.insertHtml(html)
        self.chat_area.moveCursor(QTextCursor.End)


    def trigger_manual_file_selection(self):
        """Triggers local storage dialogue routing straight to matching file pipelines."""
        file_filter = "Sovereign Core Assets (*.pdf *.png *.jpg *.jpeg *.webp *.bmp)"
        chosen_file, _ = QFileDialog.getOpenFileName(
            self,
            "SELECT INTEL ATTACHMENT CORE",
            "",
            file_filter
        )
        if chosen_file:
            self.process_attachment(chosen_file)


    def manual_protocol_trigger(self):
        d = ProtocolDialog(self, title="GHOSTDRIVE // PROTOCOL", label="SEQUENCE ID:")
        if d.exec() != QDialog.Accepted: return
        protocol = d.get_value().strip()

        if protocol == "soul_vent":
            d1 = ProtocolDialog(self, title="SOUL VENT // INITIALIZE", label="JOURNAL ID:")
            if d1.exec() != QDialog.Accepted: return
            fname = d1.get_value()
            pmp = get_random_prompt()
            d2 = ProtocolDialog(self, title="SOUL VENT // DATA ENTRY", label="ENCRYPT MESSAGE:", placeholder=f"{pmp}...", is_multiline=True)
            if d2.exec() != QDialog.Accepted: return
            d3 = ProtocolDialog(self, title="SOUL VENT // KEY SIGNATURE", label="AES KEY:", is_password=True)
            if d3.exec() != QDialog.Accepted: return
            try:
                soul_vent(fname, d2.get_value(), d3.get_value(), chosen_prompt=pmp)
                self.append_message("Soul Vent", "DATA ENCRYPTED AND STORED.")
            except Exception as e: self.append_message("Error", str(e))

        elif protocol == "soul_vent_summon":
            d_key = ProtocolDialog(self, title="SUMMON // KEY AUTH", label="AES KEY:", is_password=True)
            if d_key.exec() == QDialog.Accepted:
                try:
                    fnames, dmap = soul_vent_summon(d_key.get_value())
                    sel_dialog = ProtocolDialog(self, title="SUMMON // ENTRY SELECT", label="CHOOSE ENCRYPTED DATA:", items=fnames)
                    if sel_dialog.exec() == QDialog.Accepted:
                        sel = sel_dialog.get_value()
                        if sel:
                            view = ProtocolDialog(self, title=f"ENTRY // {sel}", label="DECRYPTED CONTENT:", readonly_text=dmap[sel])
                            view.exec()
                except Exception as e: self.append_message("Error", f"DECRYPTION FAILED: {str(e)}")
        else:
            try:
                response = execute_command(protocol)
                self.append_message("SYSTEM", response)
            except Exception as e: self.append_message("SYSTEM", f"PROTOCOL ERROR: {str(e)}")