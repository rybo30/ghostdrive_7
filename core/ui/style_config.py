# [style_config.py]

import os
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame, QLineEdit, QTextEdit, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QPoint

# --- THEME SELECTION ---
CURRENT_THEME = "GHOST_DARK"


STYLE_PLAY_BY_PLAY = (
    "color: {color}; "
    "font-family: 'Segoe UI', sans-serif; "
    "font-size: 13px; "
    "font-weight: 500; "
    "line-height: 1.4; "
    "letter-spacing: 0.5px; "
    "border: none; "
    "padding: 8px 12px; "
    "background: rgba(255, 255, 255, 0.04); " 
    "border-radius: 8px;"
)


THEMES = {
    "GHOST_DARK": {
        "BG_DEEP": "#0d1117",
        "BG_PANEL": "#161b22",
        "BG_CARD": "rgba(33, 38, 45, 0.4)",
        "BG_HOVER": "rgba(88, 166, 255, 0.08)",
        "ACCENT": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #58a6ff, stop:1 #1f6feb)",
        "ACCENT_SOLID": "#58a6ff",
        "ACCENT_GLOW": "rgba(88, 166, 255, 0.12)",
        "TEXT_MAIN": "#c9d1d9",
        "TEXT_DIM": "#8b949e",
        "BORDER": "rgba(48, 54, 61, 0.6)",
        "SUCCESS": "#238636",
        "DANGER": "#da3633",
    }
}

T = THEMES[CURRENT_THEME]
T['BG_GLASS'] = "rgba(255, 255, 255, 0.03)"
T['PROTOCOL_GOLD'] = "#ffb000"
T['PROTOCOL_BG'] = "rgba(13, 17, 23, 0.95)"
T['HUD_LINE'] = "rgba(88, 166, 255, 0.3)"

# --- GLOBAL CONSTANTS (Restoring what was lost) ---
COLOR_BG = T['BG_DEEP']
COLOR_FG = T['TEXT_MAIN']
COLOR_ACCENT = T['ACCENT_SOLID']
COLOR_BUTTON = T['BG_PANEL']
COLOR_HIGHLIGHT = T['BG_HOVER']
COLOR_BORDER = T['BORDER']
COLOR_PROTOCOL = T['ACCENT_SOLID'] 
COLOR_PAGE_BG = T['BG_PANEL']
FONT_MAIN = "Segoe UI" if os.name == "nt" else "Inter"
FONT_FAMILY = FONT_MAIN
FONT_SIZE = 14
COLOR_CARD_DARK = "#0d1117"
COLOR_CARD_MED = "#1c2833"
COLOR_TEXT_DIM = T['TEXT_DIM']
COLOR_MANUAL_BORDER = T['BORDER']

# --- RESTORED STYLE STRINGS ---
STYLE_SECTION_TITLE = f"color: {COLOR_ACCENT}; font-size: 14px; font-weight: 800; letter-spacing: 2px; border: none;"
STYLE_HUD_VAL = f"color: {COLOR_ACCENT}; font-size: 18px; font-weight: bold; font-family: 'Consolas'; border: none;"
STYLE_HUD_LBL = f"color: {COLOR_TEXT_DIM}; font-size: 10px; border: none; font-weight: bold;"
STYLE_LABEL = f"color: {COLOR_FG}; font-family: '{FONT_MAIN}'; font-size: 14px;"

STYLE_HEURISTIC_INPUT = f"""
    QLineEdit {{
        background-color: rgba(13, 17, 23, 0.6);
        color: {COLOR_FG};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: 12px;
        font-size: 13px;
    }}
"""

STYLE_CARD_MANUAL = f"QFrame {{ background-color: {COLOR_CARD_DARK}; border: 1px solid {COLOR_MANUAL_BORDER}; border-radius: 12px; }}"
STYLE_CARD_HEURISTIC = f"QFrame {{ background-color: {COLOR_CARD_MED}; border: 1px solid #34495e; border-radius: 12px; }}"

STYLE_INPUT = f"""
    QLineEdit, QTextEdit {{
        background-color: {T['BG_DEEP']};
        color: {T['TEXT_MAIN']};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 10px;
        font-size: 13px;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border-color: {T['PROTOCOL_GOLD']};
    }}
"""

STYLE_BUTTON = f"""
    QPushButton {{
        background: {T['ACCENT']};
        color: white;
        border-radius: 18px;
        font-weight: 800;
        padding: 12px;
        outline: none;
    }}
    QPushButton:hover {{ background: {T['ACCENT_SOLID']}; }}
    QPushButton#SecondaryBtn {{
        background: transparent;
        color: {T['TEXT_DIM']};
        border: 1px solid {COLOR_BORDER};
    }}
"""



STYLE_SCROLLBAR = f"""
/* Vertical Scrollbar */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_ACCENT};
    min-height: 30px;
    border-radius: 3px;
}}

/* Horizontal Scrollbar - THIS IS WHAT YOU WERE MISSING */
QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 6px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_ACCENT};
    min-width: 30px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover, QScrollBar::handle:vertical:hover {{
    background: #79b8ff;
}}

/* Hide buttons and track background for both */
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    border: none;
    background: none;
    height: 0px;
    width: 0px;
}}
"""

STYLE_MGMT_BTN = f"""
    QPushButton {{
        background: transparent;
        color: white;
        border: 3px solid white;
        border-radius: 8px;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 10px;
    }}
    QPushButton:hover#EditBtn {{
        background: {T['ACCENT_SOLID']};
        border-color: {T['ACCENT_SOLID']};
    }}
    QPushButton:hover#DeleteBtn {{
        background: {T['DANGER']};
        border-color: {T['DANGER']};
    }}
"""



# --- DIALOG CLASSES ---

class TacticalDialog(QDialog):
    def __init__(self, parent=None, title="SYSTEM COMMAND", label="INPUT:", placeholder="...", is_password=False, is_multiline=False):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(450)

        self._drag_pos = QPoint()
        
        GOLD = T['PROTOCOL_GOLD']
        BG = T['PROTOCOL_BG'] 
        LINE = T['HUD_LINE']
        
        # 1. REMOVE the setStyleSheet from 'self' to avoid the double-border/background ghosting
        # self.setStyleSheet(f"color: {GOLD}; font-family: 'Consolas';") 

        # 2. Main Dialog Layout needs 0 margins so the QFrame is the only visible border
        self.dialog_layout = QVBoxLayout(self)
        self.dialog_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame(self)
        self.container.setObjectName("ProtocolBox")
        
        # 3. Apply all styles strictly to the container and its children
        self.container.setStyleSheet(f"""
            QFrame#ProtocolBox {{ 
                background-color: {BG}; 
                border: 2px solid {GOLD}; 
                border-radius: 12px; 
            }}
            QLabel {{ 
                color: {GOLD}; 
                background: transparent; 
                border: none; 
                font-family: 'Consolas';
            }}
            QLineEdit, QTextEdit {{ 
                background: #000000; 
                color: {GOLD}; 
                border: 1px solid {LINE}; 
                border-radius: 4px; 
                padding: 10px; 
                font-family: 'Consolas';
            }}
            QPushButton {{ 
                background: rgba(255, 176, 0, 0.1); 
                border: 1px solid {GOLD}; 
                color: {GOLD}; 
                padding: 8px; 
                font-weight: bold; 
                border-radius: 4px; 
                font-family: 'Consolas';
            }}
            QPushButton:hover {{ 
                background: rgba(255, 176, 0, 0.25); 
            }}
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 20, 20, 20) # Inner spacing
        
        header = QLabel(title.upper())
        header.setStyleSheet("font-weight: 900; letter-spacing: 3px; font-size: 11px;")
        layout.addWidget(header)
        
        line_frame = QFrame()
        line_frame.setFixedHeight(1)
        line_frame.setStyleSheet(f"background-color: {GOLD};") 
        layout.addWidget(line_frame)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; margin-top: 10px;")
        layout.addWidget(lbl)

        if is_multiline:
            self.input_field = QTextEdit()
            self.input_field.setMinimumHeight(100)
        else:
            self.input_field = QLineEdit()
            if is_password: self.input_field.setEchoMode(QLineEdit.Password)
        
        self.input_field.setPlaceholderText(placeholder)
        layout.addWidget(self.input_field)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.confirm_btn = QPushButton("CONFIRM")
        self.cancel_btn = QPushButton("ABORT")
        
        btn_layout.addWidget(self.confirm_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.confirm_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        # Add the container to the actual dialog layout
        self.dialog_layout.addWidget(self.container)


    def get_value(self):
        if isinstance(self.input_field, QTextEdit): return self.input_field.toPlainText().strip()
        return self.input_field.text().strip()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

# --- HELPERS ---
def ghost_alert(parent, title, message):
    dialog = TacticalDialog(parent, title=title, label=message)
    dialog.input_field.hide() 
    if any(x in title.upper() for x in ["DELETE", "DESTROY", "ERASE", "PURGE", "KILL"]):
        dialog.confirm_btn.setText("TERMINATE")
        dialog.confirm_btn.setStyleSheet(dialog.confirm_btn.styleSheet().replace(T['PROTOCOL_GOLD'], "#ff4444"))
    else:
        dialog.confirm_btn.setText("CONFIRM")
    dialog.confirm_btn.setFocus()
    return dialog.exec() == QDialog.Accepted

def ghost_prompt(parent, title, label, placeholder="...", password=False, multiline=False):
    dialog = TacticalDialog(parent, title, label, placeholder, is_password=password, is_multiline=multiline)
    if dialog.exec() == QDialog.Accepted: return dialog.get_value(), True
    return "", False

def get_master_stylesheet():
    return f"""
    * {{ font-family: '{FONT_MAIN}', sans-serif; color: {COLOR_FG}; outline: none; }}
    QMainWindow, .QWidget {{ background-color: {COLOR_BG}; }}
    QFrame#Sidebar {{ background-color: {COLOR_BUTTON}; border-right: 1px solid {COLOR_BORDER}; }}
    QLabel#LogoLabel {{ color: {COLOR_ACCENT}; font-size: 18px; font-weight: 900; letter-spacing: 2px; background: transparent; padding: 30px 10px 15px 20px; }}
    QPushButton#NavButton {{ background: transparent; color: {T['TEXT_DIM']}; border: none; border-radius: 8px; text-align: left; padding: 12px 20px; margin: 2px 12px; }}
    QPushButton#NavButton:hover {{ background-color: {COLOR_HIGHLIGHT}; }}
    QPushButton#NavButton:checked {{ background-color: {T['ACCENT_GLOW']}; color: {COLOR_ACCENT}; font-weight: bold; }}
    QProgressBar#StorageBar {{ border: none; background-color: rgba(255, 255, 255, 0.05); height: 4px; border-radius: 2px; }}
    QProgressBar#StorageBar::chunk {{ background-color: {COLOR_ACCENT}; border-radius: 2px; }}  
    {STYLE_SCROLLBAR}
"""

def get_main_stylesheet(theme_dict=None): return get_master_stylesheet()

def get_icon(name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "..", "Everything_else", f"{name}_icon.png")
    return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()