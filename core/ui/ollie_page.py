# [ollie_page.py]

import sys, os, glob
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QFrame, QProgressBar, QListWidget, 
    QListWidgetItem, QMenu, QSpacerItem, QSizePolicy, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QColor

# --- INTEGRATED STYLE CONFIG ---
from .style_config import (
    T, COLOR_ACCENT, COLOR_FG, COLOR_BORDER, COLOR_TEXT_DIM,
    ghost_prompt, ghost_alert, STYLE_SCROLLBAR
)
from core.paths import USER_DATA 

class OlliePage(QWidget):
    def __init__(self, username, passphrase, fernet, engine=None, manifest=None):
        super().__init__()
        self.username = username
        self.passphrase = passphrase
        self.fernet = fernet
        
        self.engine = engine
        self.manifest = manifest
        
        self.is_recording = False
        self.recording_time = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)

        self.current_audio_file = None 
        
        self.recordings_dir = os.path.join(USER_DATA, "recordings")
        os.makedirs(self.recordings_dir, exist_ok=True)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 20, 30, 30)
        self.layout.setSpacing(15)

        self.setup_header()
        self.main_content = QHBoxLayout()
        self.main_content.setSpacing(20)
        
        self.left_col = QVBoxLayout()
        self.setup_recorder_ui()
        self.setup_transcript_area()

        self.setup_progress_system()
        self.main_content.addLayout(self.left_col, stretch=3)
        
        self.setup_history_sidebar()
        self.main_content.addLayout(self.right_col, stretch=1)
        
        self.layout.addLayout(self.main_content)
        self.refresh_history()

    def setup_header(self):
        head = QVBoxLayout()
        head.setSpacing(4)
        self.title = QLabel("MEETING INTELLIGENCE")
        self.title.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-weight: 700; 
            font-size: 22px; 
            letter-spacing: 1px; 
            border: none;
            font-family: 'Segoe UI', sans-serif;
        """)
        self.subtitle = QLabel(f"ENCRYPTED OFFLINE AI SYNTHESIS • BEST FOR MEETINGS UNDER 20 MINS")
        self.subtitle.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; border: none;")
        head.addWidget(self.title)
        head.addWidget(self.subtitle)
        self.layout.addLayout(head)

    def setup_recorder_ui(self):
        self.recorder_frame = QFrame()
        self.recorder_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #090c10;  /* Dark charcoal/Black background */
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        self.recorder_frame.setFixedHeight(100)
    
        lay = QHBoxLayout(self.recorder_frame)
        lay.setContentsMargins(20, 0, 20, 0)

        # Power Toggle
        self.record_btn = QPushButton("RECORD")
        self.record_btn.setCheckable(True)
        self.record_btn.setFixedSize(120, 45)
        self.record_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn_style(False) 
        self.record_btn.clicked.connect(self.toggle_recording)
        lay.addWidget(self.record_btn)

        # Telemetry Container - Force border: none here
        tel_container = QFrame()
        tel_container.setStyleSheet("border: none; background: transparent;") 
        tel_lay = QVBoxLayout(tel_container)
        tel_lay.setSpacing(0)
        
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setStyleSheet(f"color: {COLOR_FG}; font-family: 'Segoe UI Semibold'; font-size: 22px; border: none;")
        self.timer_label.hide() # START HIDDEN
        
        self.status_label = QLabel("READY TO RECORD")
        self.status_label.setStyleSheet(f"color: {T['PROTOCOL_GOLD']}; font-size: 10px; font-weight: bold; letter-spacing: 1px; border: none;")
        self.status_label.show() # START VISIBLE

        tel_lay.addWidget(self.timer_label)
        tel_lay.addWidget(self.status_label)
        lay.addSpacing(30)
        lay.addWidget(tel_container)
        
        lay.addStretch()

        # Utility Buttons
        util_deck = QHBoxLayout()
        util_deck.setSpacing(10)
        
        util_style = f"""
            QPushButton {{ 
                background: #0d1117; color: {COLOR_TEXT_DIM}; border: 1px solid {COLOR_BORDER}; 
                border-radius: 4px; font-weight: 600; font-size: 11px; padding: 8px 15px;
            }}
            QPushButton:hover {{ color: {COLOR_ACCENT}; border: 1px solid {COLOR_ACCENT}; }}
            QPushButton:disabled {{ color: #30363d; border: 1px solid #21262d; }}
        """
        
        self.play_session_btn = QPushButton("PLAYBACK")
        self.play_session_btn.setStyleSheet(util_style)
        self.play_session_btn.setEnabled(False)
        self.play_session_btn.clicked.connect(self.play_audio_file)

        self.analyze_btn = QPushButton("ANALYZE")
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setStyleSheet(util_style.replace(COLOR_TEXT_DIM, COLOR_ACCENT))
        self.analyze_btn.clicked.connect(self.start_delayed_analysis)

        util_deck.addWidget(self.play_session_btn)
        util_deck.addWidget(self.analyze_btn)
        lay.addLayout(util_deck)
    
        self.left_col.addWidget(self.recorder_frame)

    def update_btn_style(self, active):
        if active:
            self.record_btn.setText("STOP")
            self.record_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: {T['DANGER']}; color: white; 
                    border: none; border-radius: 4px; font-weight: bold;
                }}
            """)
        else:
            self.record_btn.setText("START SESSION")
            self.record_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: {COLOR_ACCENT}; color: white; 
                    border: none; border-radius: 4px; font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #2b70e0; }}
            """)

    def setup_transcript_area(self):
        from .style_config import STYLE_SCROLLBAR
        self.results_area = QTextEdit()
        self.results_area.setReadOnly(True)
        self.results_area.setStyleSheet(f"""
            QTextEdit {{ 
                background-color: {T['BG_DEEP']}; 
                border: 1px solid {COLOR_BORDER}; 
                border-radius: 8px; 
                color: {COLOR_FG}; 
                font-family: 'Segoe UI', 'Arial'; 
                font-size: 13px;
                padding: 25px; 
            }}
            {STYLE_SCROLLBAR}
        """)
        self.left_col.addWidget(self.results_area)

    def setup_progress_system(self):
        self.progress_container = QFrame()
        self.master_bar_data = self._create_stage_bar("READY")
        self.left_col.addWidget(self.master_bar_data["container"])
        self.progress_container = self.master_bar_data["container"]
        self.progress_container.hide()

    def _create_stage_bar(self, label_text):
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(2)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 9px; font-family: 'Consolas';")
        bar = QProgressBar()
        bar.setFixedHeight(6)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"QProgressBar {{ background: #111; border: none; border-radius: 3px; }} QProgressBar::chunk {{ background: {COLOR_ACCENT}; }}")
        lay.addWidget(lbl)
        lay.addWidget(bar)
        return {"container": container, "bar": bar, "label": lbl}

    def handle_progress_update(self, val):
        self.master_bar_data["bar"].setValue(val)
        if val <= 30:
            status_text = "PHASE 1: SECURING DATA..."
        elif val <= 60:
            status_text = "PHASE 2: TRANSCRIBING..."
        else:
            status_text = "PHASE 3: AI SYNTHESIS..."
        self.master_bar_data["label"].setText(status_text)

    def setup_history_sidebar(self):
        self.right_col = QVBoxLayout()
        self.right_col.setSpacing(10)

        sidebar_head = QLabel("PAST SESSIONS")
        sidebar_head.setStyleSheet(f"""
            color: {COLOR_ACCENT}; font-weight: 800; font-size: 11px; 
            font-family: 'Segoe UI', sans-serif; letter-spacing: 2px; margin-left: 5px;
        """)
    
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter logs...")
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background: #161b22; border: 1px solid {COLOR_BORDER}; border-radius: 8px;
                color: {COLOR_FG}; padding: 8px; font-size: 12px; font-family: 'Segoe UI', sans-serif;
            }}
            QLineEdit:focus {{ border: 1px solid {COLOR_ACCENT}; }}
        """)
        self.search_bar.textChanged.connect(self.filter_history)

        # --- THE CLEAN REBUILD ---
        self.history_list = QTreeWidget()
        self.history_list.setColumnCount(2)
        self.history_list.setHeaderHidden(True)
        self.history_list.setIndentation(0)
    
        # --- THE FULL-CONTROL CONFIG ---
        self.history_list.header().setStretchLastSection(False) # Prevent the last column from stretching
        
        # 1. Title: ResizeToContents allows it to be wider than the widget (enabling scroll)
        self.history_list.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        
        # 2. Date: Fixed or ResizeToContents
        self.history_list.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        # 3. Ensure the title at least fills the sidebar if it's short
        self.history_list.header().setMinimumSectionSize(150)
    
        # Force horizontal scrollbar behavior
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_context_menu)
    
        self.history_list.setStyleSheet(f"""
            QTreeWidget {{ 
                background: #0d1117; border: 1px solid {COLOR_BORDER}; border-radius: 12px; 
                color: {COLOR_FG}; outline: none; font-family: 'Segoe UI', sans-serif;
                font-size: 12px; padding: 5px;
            }}
            /* REMOVED HOVER: We only style the :selected state */
            QTreeWidget::item {{ 
                padding: 12px; border-bottom: 1px solid #161b22;
                color: {COLOR_FG};
            }}
            QTreeWidget::item:selected {{ 
                background: #1c2128; 
                color: {COLOR_ACCENT}; 
                font-weight: 700;
                border-left: 3px solid {COLOR_ACCENT}; /* Adds a nice "active" indicator */
            }}
            /* Force no hover color */
            QTreeWidget::item:hover {{ 
                background: transparent; 
            }}
            {STYLE_SCROLLBAR}
        """)
        self.history_list.itemClicked.connect(self.load_past_session)
    
        self.refresh_btn = QPushButton("REFRESH VAULT")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.clicked.connect(self.refresh_history)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLOR_TEXT_DIM}; border: 1px solid {COLOR_BORDER}; 
                border-radius: 8px; font-size: 10px; font-weight: 700; letter-spacing: 1px;
            }}
            QPushButton:hover {{ color: {COLOR_FG}; border: 1px solid {COLOR_FG}; }}
        """)
    
        self.right_col.addWidget(sidebar_head)
        self.right_col.addWidget(self.search_bar)
        self.right_col.addWidget(self.history_list)
        self.right_col.addWidget(self.refresh_btn)

    def filter_history(self, text):
        """Filters the sidebar tree based on search text."""
        search_text = text.lower()
        for i in range(self.history_list.topLevelItemCount()):
            item = self.history_list.topLevelItem(i)
            # Check title (column 0)
            should_hide = search_text not in item.text(0).lower()
            item.setHidden(should_hide)


    def refresh_history(self):
        """Self-healing refresh: automatically prunes manifest entries with missing physical files."""
        self.history_list.clear()
        all_files = self.manifest.get_files()
        
        # Filter for report files
        reports = [f for f in all_files if f['name'].startswith("report_") and f['name'].endswith(".html.ghost")]

        from datetime import datetime
        manifest_was_pruned = False

        # --- THE AGGRESSIVE PRUNER ---
        valid_reports = []
        for r in reports:
            # Check if physical file exists
            # If engine.file_exists returns False, the file is an orphan.
            if hasattr(self.engine, 'file_exists') and not self.engine.file_exists(r['id']):
                print(f"DEBUG: Pruning orphan {r['name']} from manifest...")
                self.manifest.remove_entry(r['id'])
                manifest_was_pruned = True
                continue
            valid_reports.append(r)

        # Save the manifest if we cleaned up orphans
        if manifest_was_pruned and hasattr(self.manifest, 'save'):
            self.manifest.save()

        # --- SORT: MOST RECENT TO LEAST RECENT ---
        # Sorts the valid reports by 'created_at'. reverse=True ensures newest is first.
        # Uses .get('created_at', 0) as a fallback if a file somehow lacks a timestamp.
        valid_reports.sort(key=lambda x: x.get('created_at', 0), reverse=True)

        # --- UI RENDER (Using sorted, verified files) ---
        for r in valid_reports:
            display_name = r['name'].replace("report_", "").replace(".html.ghost", "").replace("_", " ")
            
            # Date Handling
            timestamp = r.get('created_at')
            date_str = datetime.fromtimestamp(timestamp).strftime("%m/%d/%Y") if timestamp else "--/--/----"

            item = QTreeWidgetItem([display_name, date_str])
            item.setFont(0, QFont("Segoe UI Semibold", 10))
            item.setData(0, Qt.UserRole, r['id'])
            item.setData(0, Qt.ItemDataRole.ToolTipRole, r['name'])
            
            self.history_list.addTopLevelItem(item)

    def load_past_session(self, item):
        """Decrypts the summary from the vault directly into memory for the UI."""
        file_id = item.data(0, Qt.UserRole)
        file_name = item.data(0, Qt.ItemDataRole.ToolTipRole)
        self.current_session_name = file_name.replace("report_", "").replace(".html.ghost", "")

        try:
            # 1. Decrypt HTML summary directly to memory
            raw_data = self.engine.decrypt_file_to_memory(file_id)
            html_content = raw_data.decode("utf-8")
            
            self.results_area.setHtml(html_content)
            self.status_label.setText("ENCRYPTED SESSION LOADED")

            # --- THE FIX: Re-enable the Analyze button when a session is selected ---
            self.analyze_btn.setEnabled(True) 

            # 2. Check if the matching audio exists in vault for playback
            vault_audio_name = f"{self.current_session_name}.mp3"
            all_files = self.manifest.get_files()
            audio_entry = next((f for f in all_files if f['name'] == vault_audio_name), None)
            
            if audio_entry:
                self.current_audio_file = audio_entry['name']
                self.play_session_btn.setEnabled(True)
            else:
                self.play_session_btn.setEnabled(False)

        except Exception as e:
            self.results_area.setText(f"VAULT DECRYPTION ERROR: {e}")
            self.analyze_btn.setEnabled(False)

    def show_context_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if not item: return
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background: {T['PROTOCOL_BG']}; color: {COLOR_FG}; border: 1px solid {T['HUD_LINE']}; }} QMenu::item:selected {{ background: {T['BG_HOVER']}; }}")
        rename_act = menu.addAction("RENAME")
        delete_act = menu.addAction("DELETE")
        action = menu.exec(self.history_list.mapToGlobal(pos))
        if action == rename_act: self.rename_session(item)
        elif action == delete_act: self.delete_session(item)

    def rename_session(self, item):
        old_report_path = item.data(Qt.UserRole)
        new_name, ok = ghost_prompt(self, "RECLASSIFY", "ENTER NEW SESSION ALIAS:", placeholder=item.text())
        if ok and new_name:
            new_report_path = os.path.join(self.recordings_dir, f"report_{new_name}.html")
            try:
                os.rename(old_report_path, new_report_path)
                base_old = os.path.basename(old_report_path).replace("report_", "").replace(".html", "")
                for ext in [".mp3", ".mp3.ghost", ".wav"]:
                    f_old = os.path.join(self.recordings_dir, f"{base_old}{ext}")
                    f_new = os.path.join(self.recordings_dir, f"{new_name}{ext}")
                    if os.path.exists(f_old): os.rename(f_old, f_new)
                self.refresh_history()
            except Exception as e:
                ghost_alert(self, "SYSTEM ERROR", f"RENAME FAILED: {str(e)}")

    def delete_session(self, item):
        """Force-removes an entry from the manifest even if the physical file is missing."""
        report_id = item.data(0, Qt.UserRole)
        report_name = item.data(0, Qt.ItemDataRole.ToolTipRole)
        
        confirm = ghost_alert(self, "FORCE PURGE", f"REMOVE {item.text()} FROM MANIFEST?")
        if confirm:
            try:
                # 1. Identify associated audio
                base_name = report_name.replace("report_", "").replace(".html.ghost", "")
                vault_audio_name = f"{base_name}.mp3"
                
                all_files = self.manifest.get_files()
                audio_entry = next((f for f in all_files if f['name'] == vault_audio_name), None)
                
                # 2. Remove both from manifest (regardless of if they exist on disk)[cite: 1]
                if audio_entry:
                    self.manifest.remove_entry(audio_entry['id'])
                self.manifest.remove_entry(report_id)

                # 3. Save changes[cite: 1]
                if hasattr(self.manifest, 'save'):
                    self.manifest.save() 
                
                self.results_area.clear()
                self.refresh_history()
                self.status_label.setText("MANIFEST PURGED")

            except Exception as e:
                ghost_alert(self, "PURGE FAILED", f"Critical Error: {e}")

    def toggle_recording(self):
        if self.record_btn.isChecked(): self.start_session()
        else: self.stop_session()

    def update_timer(self):
        self.recording_time += 1
        hours, remainder = divmod(self.recording_time, 3600)
        mins, secs = divmod(remainder, 60)
        time_str = f"{hours:02}:{mins:02}:{secs:02}"
        self.timer_label.setText(time_str)
        if self.recording_time % 2 == 0:
            self.timer_label.setStyleSheet(f"color: {T['DANGER']}; font-family: 'Consolas'; font-size: 14px; font-weight: bold;")
        else:
            self.timer_label.setStyleSheet(f"color: {COLOR_FG}; font-family: 'Consolas'; font-size: 14px; font-weight: bold;")


    def start_session(self):
        name, ok = ghost_prompt(self, "INITIALIZE PACKET", "SESSION NAME:", placeholder="Neural_Log")
        if not ok:
            self.record_btn.setChecked(False)
            return
            
        self.is_recording = True
        self.recording_time = 0
        
        # --- UI SWAP ---
        self.status_label.hide()     # Hide text
        self.timer_label.show()      # Show timer
        
        self.timer.start(1000)
        self.update_btn_style(True)
        self.results_area.clear()
        self.master_bar_data["bar"].setValue(0)
        self.master_bar_data["label"].setText("INITIALIZING MIC...")
        self.progress_container.show()

        from Everything_else.meeting_engine import MeetingWorker
        self.worker = MeetingWorker(
            custom_name=name,
            engine=self.engine,
            manifest=self.manifest,
            mode="record"
        )
        self.worker.status_signal.connect(self.status_label.setText)
        self.worker.progress_signal.connect(self.handle_progress_update)
        self.worker.result_signal.connect(self.finalize_meeting)
        self.worker.start()

    def start_delayed_analysis(self):
        if not hasattr(self, 'current_session_name'): return
        self.analyze_btn.setEnabled(False)
        self.progress_container.show()
        self.status_label.setText("INITIALIZING OLLIE...")
        from Everything_else.meeting_engine import MeetingWorker
        self.worker = MeetingWorker(
            custom_name=self.current_session_name,
            engine=self.engine,
            manifest=self.manifest,
            mode="analyze"
        )
        self.worker.status_signal.connect(self.status_label.setText)
        self.worker.progress_signal.connect(self.handle_progress_update)
        self.worker.result_signal.connect(self.finalize_meeting)
        self.worker.start()    

    def play_audio_file(self):
        if not self.current_audio_file: return
        files = self.manifest.get_files()
        target_file = next((f for f in files if f['name'] == self.current_audio_file), None)
        if target_file:
            try:
                import tempfile
                data = self.engine.decrypt_file_to_memory(target_file['id'])
                temp_path = os.path.join(tempfile.gettempdir(), target_file['name'])
                with open(temp_path, "wb") as f: f.write(data)
                os.startfile(temp_path) if os.name == 'nt' else subprocess.call(["open", temp_path])
            except Exception as e:
                ghost_alert(self, "PLAYBACK ERROR", f"Vault Access Denied: {e}")

    def stop_session(self):
        self.is_recording = False
        self.timer.stop()
        
        # --- UI SWAP BACK ---
        self.timer_label.hide()      # Hide timer
        self.status_label.show()     # Show text
        self.status_label.setText("SESSION TERMINATED")
        
        if hasattr(self, 'worker'): 
            self.worker.stop_recording()

    def finalize_meeting(self, result_data):
        self.timer.stop()
        self.timer_label.hide()
        self.status_label.show()
    
        self.progress_container.hide()
        self.update_btn_style(False)
        self.record_btn.setChecked(False)

        # Check if we got back full HTML (Analysis Mode) or just a signal (Record Mode)
        if result_data.startswith("<html>") or "<style>" in result_data:
            self.results_area.setHtml(result_data)
            self.status_label.setText("ANALYSIS COMPLETE")
            # Keep buttons enabled so we can re-run or play back
            self.analyze_btn.setEnabled(True)
            self.play_session_btn.setEnabled(True)
        else:
            # It's just a "RECORDING_COMPLETE" signal
            self.status_label.setText("SESSION SECURED")
            self.results_area.setHtml(
                "<h2 style='color:#ffb000;'>RECORDING SECURED</h2>"
                "<p>Select the session from the log and click 'ANALYZE' to generate the intelligence brief.</p>"
            )
            # After a fresh record, we disable these until the user selects the item in the sidebar
            self.analyze_btn.setEnabled(False)
            self.play_session_btn.setEnabled(False)
    
        # Refresh history to show the new "Pending" or "Complete" file
        self.refresh_history()
        
        # Deselect items so the user is forced to click the fresh entry to 'load' it
        self.history_list.clearSelection()