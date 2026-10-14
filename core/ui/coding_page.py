# [coding_page.py]

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QLabel, QFrame, QSplitter
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QTextCursor

# Import your styles
from core.Everything_else.manifest_manager import ManifestManager
from core.Everything_else.coding_worker import CodingWorker
from .style_config import (
    T, COLOR_ACCENT, COLOR_BG, COLOR_BORDER, 
    STYLE_BUTTON, STYLE_SCROLLBAR
)

class CodingPage(QWidget):
    def __init__(self, username, passphrase, fernet, **kwargs):
        super().__init__()
        self.username = username
        
        # Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 25, 30, 30)
        self.layout.setSpacing(20)

        # --- HEADER: THE HUD ---
        header_lay = QHBoxLayout()
        
        # Branded Title
        self.title = QLabel("CODING ASSISTANT")
        self.title.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-weight: 700; 
            font-size: 22px; 
            letter-spacing: 1px; 
            border: none;
            font-family: 'Segoe UI', sans-serif;
        """)
        
        # System Status (Now Blue/Cyan instead of Green)
        self.status_tag = QLabel("SYSTEM READY")
        self.status_tag.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-family: 'Consolas'; 
            font-size: 11px; 
            font-weight: bold; 
            border: 1px solid {COLOR_ACCENT}; 
            padding: 4px 12px; 
            border-radius: 2px;
            background: rgba(0, 210, 255, 0.05);
        """)
        
        header_lay.addWidget(self.title)
        header_lay.addStretch()
        header_lay.addWidget(self.status_tag)
        self.layout.addLayout(header_lay)

        # --- THE WORKSPACE ---
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 transparent, stop:0.5 {COLOR_BORDER}, stop:1 transparent); 
                height: 2px; 
            }}
        """)

        # --- INPUT HUB ---
        self.input_container = QFrame()
        input_lay = QVBoxLayout(self.input_container)
        input_lay.setContentsMargins(0, 0, 0, 15)

        # Source Code Editor
        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText("Paste Your Original Code...")
        self.apply_code_style(self.code_input)
        
        # Modification Prompt
        self.blurb_input = QTextEdit()
        self.blurb_input.setFixedHeight(85)
        self.blurb_input.setPlaceholderText(">> Describe the changes you want to make...")
        self.blurb_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0d1117;
                border: 1px solid {COLOR_BORDER};
                border-left: 4px solid {COLOR_ACCENT};
                border-radius: 4px;
                color: {T['TEXT_MAIN']};
                padding: 12px;
                font-family: 'Consolas';
                font-size: 13px;
            }}
        """)

        input_lay.addWidget(QLabel("SOURCE CODE", styleSheet="font-size: 10px; letter-spacing: 2px; color: #58a6ff; font-weight: bold;"))
        input_lay.addWidget(self.code_input)
        input_lay.addWidget(self.blurb_input)

        # Action Buttons
        btn_lay = QHBoxLayout()
        self.clear_btn = QPushButton("RESET")
        self.clear_btn.setFixedWidth(120)
        self.clear_btn.setStyleSheet(STYLE_BUTTON + "QPushButton { background: transparent; border: 1px solid #30363d; }")
        self.clear_btn.clicked.connect(self.clear_all)

        self.analyze_btn = QPushButton("ANALYZE")
        self.analyze_btn.setFixedHeight(40)
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_ACCENT};
                color: #000;
                font-weight: 900;
                letter-spacing: 1px;
                border-radius: 4px;
                padding: 0 25px;
            }}
            QPushButton:hover {{ background: #fff; }}
            QPushButton:disabled {{ background: #161b22; color: #484f58; }}
        """)
        self.analyze_btn.clicked.connect(self.trigger_analysis)

        btn_lay.addWidget(self.clear_btn)
        btn_lay.addStretch()
        btn_lay.addWidget(self.analyze_btn)
        input_lay.addLayout(btn_lay)

        # --- OUTPUT HUB ---
        self.output_container = QFrame()
        output_lay = QVBoxLayout(self.output_container)
        output_lay.setContentsMargins(0, 15, 0, 0)

        self.code_output = QTextEdit()
        self.code_output.setReadOnly(True)
        self.apply_code_style(self.code_output, is_output=True)

        self.copy_btn = QPushButton("COPY")
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_ACCENT};
                border: 1px solid {COLOR_ACCENT};
                border-radius: 2px;
                padding: 4px 12px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(0, 210, 255, 0.1); }}
        """)
        self.copy_btn.clicked.connect(self.copy_output)

        out_head = QHBoxLayout()
        out_head.addWidget(QLabel("OUTPUT", styleSheet="font-size: 10px; letter-spacing: 2px; color: #58a6ff; font-weight: bold;"))
        out_head.addStretch()
        out_head.addWidget(self.copy_btn)

        output_lay.addLayout(out_head)
        output_lay.addWidget(self.code_output)

        self.splitter.addWidget(self.input_container)
        self.splitter.addWidget(self.output_container)
        self.layout.addWidget(self.splitter)

    def apply_code_style(self, widget, is_output=False):
        bg = "#05070a" if is_output else "#0d1117"
        border_col = COLOR_ACCENT if is_output else COLOR_BORDER
        widget.setStyleSheet(f"""
            QTextEdit {{
                background-color: {bg};
                border: 1px solid {border_col};
                border-radius: 8px;
                color: {"#58a6ff" if is_output else "#c9d1d9"};
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 13px;
                padding: 15px;
            }}
        """ + STYLE_SCROLLBAR)

    def clear_all(self):
        self.code_input.clear()
        self.blurb_input.clear()
        self.code_output.clear()
        self.status_tag.setText("SYSTEM READY")

    def copy_output(self):
        text = self.code_output.toPlainText()
        if text:
            os.system(f"echo {text}| clip")
            self.copy_btn.setText("COPIED")
            QTimer.singleShot(2000, lambda: self.copy_btn.setText("COPY"))

    def trigger_analysis(self):
        code = self.code_input.toPlainText().strip()
        blurb = self.blurb_input.toPlainText().strip()
        if not code: return

        self.code_output.clear()
        self.analyze_btn.setEnabled(False)
        self.status_tag.setText("ANALYZING LOGIC...")
        self.status_tag.setStyleSheet(self.status_tag.styleSheet().replace(COLOR_ACCENT, T['PROTOCOL_GOLD']))

        self.thread = CodingWorker(code, blurb, model_id="jynx_expert_coding") 
        self.thread.chunk_received.connect(self.on_chunk_received)
        self.thread.finished.connect(self.on_analysis_finished)
        self.thread.error.connect(self.on_analysis_error)
        self.thread.start()

    @Slot(str)
    def on_chunk_received(self, text):
        self.code_output.moveCursor(QTextCursor.End)
        self.code_output.insertPlainText(text)
        self.code_output.ensureCursorVisible()

    def on_analysis_finished(self):
        self.analyze_btn.setEnabled(True)
        self.status_tag.setText("ANALYSIS COMPLETE")
        self.status_tag.setStyleSheet(self.status_tag.styleSheet().replace(T['PROTOCOL_GOLD'], COLOR_ACCENT))

    def on_analysis_error(self, err_msg):
        self.analyze_btn.setEnabled(True)
        self.status_tag.setText("CORE FAILURE")
        self.code_output.setPlainText(f"// ERROR_LOG:\n{err_msg}")