#  [main_window.py]

import os
import sys
import shutil
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QPushButton, QStackedWidget, QLabel, QFrame, QApplication,
    QProgressBar, QGraphicsDropShadowEffect, QScrollArea
)
from PySide6.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QLinearGradient

# --- Logic & Path Imports ---
from core.paths import USER_DATA, BASE_PATH  
from core.Everything_else.manifest_manager import ManifestManager
from core.Everything_else.encryption_engine import GhostEngine

# --- Style Imports ---
from .style_config import T, COLOR_BG, COLOR_ACCENT, COLOR_FG

# --- Page Imports ---
from .my_drive_page import MyDrivePage
from .chat_page import ChatPage
from .vault_page import VaultPage
from .project_page import ProjectsPage
from .inventory_page import InventoryPage
from .profile_page import ProfilePage
from .sync_page import SyncPage
from .ollie_page import OlliePage
from .games_page import GamesPage
from .health_page import HealthPage
from .coding_page import CodingPage
from .agents_page import AgentsPage

class GhostDriveMainWindow(QMainWindow):
    def __init__(self, username, passphrase, fernet):
        super().__init__()
        self.username = username
        self.passphrase = passphrase
        self.fernet = fernet
        self._drag_pos = QPoint()

        app = QApplication.instance()
        self.ghost_id = getattr(app, "ghost_id", "ID_NOT_FOUND")
        
        self.engine = GhostEngine(self.fernet) 
        self.manifest = ManifestManager(self.engine, self.username)

        # --- FRAMELESS CONFIG ---
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMinimumSize(1150, 780)

        # Main Layout
        self.main_container = QWidget()
        self.setCentralWidget(self.main_container)
        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0) 

        # Root Widget
        self.root_widget = QFrame()
        self.root_widget.setObjectName("RootWidget")
        self.main_layout.addWidget(self.root_widget)

        self.root_layout = QHBoxLayout(self.root_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # --- SIDEBAR ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(260)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)

        # Logo Section
        self.logo_area = QFrame()
        self.logo_area.setFixedHeight(80)
        logo_lay = QVBoxLayout(self.logo_area)
        self.logo_label = QLabel("GHOSTDRIVE")
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet("font-size: 20px; font-weight: 900; color: #58a6ff; letter-spacing: 6px; margin-top: 10px;")
        logo_lay.addWidget(self.logo_label)
        self.sidebar_layout.addWidget(self.logo_area)

        # Navigation
        self.nav_container = QFrame()
        self.nav_layout = QVBoxLayout(self.nav_container)
        self.nav_layout.setContentsMargins(15, 10, 15, 10)
        self.nav_layout.setSpacing(4)

        # --- UPDATED NAV MAP ---
        self.nav_map = {
            "FILE VAULT": "My Drive",
            "PASSWORDS": "Password Vault",
            "PROJECTS": "Projects",
            "CODING": "Coding",
            "DATA": "Inventory",
            "HEALTH": "Health",
            "AI COUNCIL": "Chat",
            "AGENTS": "Agent",
            "MEETINGS": "Meeting",
            "ARCADE": "Games",
            "SIGNATURE": "Profile",
            "UPLINK": "Sync"
        }

        # --- SCROLLABLE NAVIGATION ---
        self.nav_scroll = QScrollArea()
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setFrameShape(QFrame.NoFrame)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # Keep it invisible
        self.nav_scroll.setStyleSheet("background: transparent;")

        self.nav_container = QFrame()
        self.nav_layout = QVBoxLayout(self.nav_container)
        self.nav_layout.setContentsMargins(15, 10, 15, 10)
        self.nav_layout.setSpacing(4)

        self.nav_buttons = {}
        for name in self.nav_map.keys():
            btn = QPushButton(name)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setFixedHeight(42) # <--- Slightly Slimmer
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(self.handle_nav_click)
            self.nav_layout.addWidget(btn)
            self.nav_buttons[name] = btn

        self.nav_layout.addStretch()
        self.nav_scroll.setWidget(self.nav_container)
        
        self.sidebar_layout.addWidget(self.nav_scroll)

        # --- COOLER USER TILE (THE TERMINAL) ---
        self.user_tile = QFrame()
        self.user_tile.setObjectName("UserTile")
        self.user_tile.setFixedHeight(130)
        tile_lay = QVBoxLayout(self.user_tile)
        tile_lay.setContentsMargins(20, 15, 20, 15)
        tile_lay.setSpacing(8)

        # Ident Header
        ident_row = QHBoxLayout()
        status_dot = QLabel("●")
        status_dot.setStyleSheet("color: #238636; font-size: 10px; margin-right: 2px;")
        
        ident_label = QLabel(f"IDENTITY: <span style='color: white;'>{self.username.upper()}</span>")
        ident_label.setStyleSheet("color: #8b949e; font-weight: 800; font-size: 10px; letter-spacing: 1px;")
        
        ident_row.addWidget(status_dot)
        ident_row.addWidget(ident_label)
        ident_row.addStretch()
        tile_lay.addLayout(ident_row)

        # Storage Readout
        self.storage_info = QLabel("CAPACITY: ANALYZING...")
        self.storage_info.setStyleSheet("color: #8b949e; font-size: 9px; font-family: 'Consolas';")
        tile_lay.addWidget(self.storage_info)

        # Progress Bar
        self.storage_bar = QProgressBar()
        self.storage_bar.setObjectName("StorageBar")
        self.storage_bar.setFixedHeight(3)
        self.storage_bar.setTextVisible(False)
        tile_lay.addWidget(self.storage_bar)
        
        # System Footer
        sys_footer = QLabel("ENCRYPTION ENGINE: ACTIVE")
        sys_footer.setStyleSheet("color: rgba(88, 166, 255, 0.4); font-size: 8px; font-weight: bold;")
        tile_lay.addWidget(sys_footer)

        self.sidebar_layout.addWidget(self.user_tile)
        
        # --- CONTENT AREA ---
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self.header = QFrame()
        self.header.setObjectName("Header") 
        self.header.setFixedHeight(60)
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(35, 0, 15, 0)
        
        self.header_title = QLabel("FILE VAULT")
        self.header_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #c9d1d9; letter-spacing: 1px;")
        h_lay.addWidget(self.header_title)
        h_lay.addStretch()

        self.min_btn = QPushButton("—")
        self.min_btn.setObjectName("Ctrl")
        self.min_btn.setFixedSize(30, 30)
        self.min_btn.clicked.connect(self.showMinimized)
        h_lay.addWidget(self.min_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("CtrlClose")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close)
        h_lay.addWidget(self.close_btn)

        # --- PAGES ---
        self.stack = QStackedWidget()
        self.pages = {
            "My Drive": MyDrivePage(self.engine, self.manifest),
            "Chat": ChatPage(username, passphrase, fernet, engine=self.engine, manifest=self.manifest),
            "Coding": CodingPage(username, passphrase, fernet, engine=self.engine, manifest=self.manifest),
            "Agent": AgentsPage(username, passphrase, fernet, engine=self.engine, manifest=self.manifest),
            "Meeting": OlliePage(username, passphrase, fernet, engine=self.engine, manifest=self.manifest), 
            "Profile": ProfilePage(username, fernet),
            "Password Vault": VaultPage(username, passphrase, fernet),
            "Projects": ProjectsPage(username, passphrase, fernet),
            "Inventory": InventoryPage(username, passphrase, fernet),
            "Health": HealthPage(username, fernet),
            "Games": GamesPage(username, fernet),
            "Sync": SyncPage(username, fernet, self.ghost_id, getattr(app, "private_key", None))
        }

        for page in self.pages.values(): 
            self.stack.addWidget(page)

        self.content_layout.addWidget(self.header)
        self.content_layout.addWidget(self.stack)
        self.root_layout.addWidget(self.sidebar)
        self.root_layout.addWidget(self.content_area)

        self.apply_tactical_styles()
        self.nav_buttons["FILE VAULT"].setChecked(True)
        self.center_window()
        self.update_storage_stats()

    def apply_tactical_styles(self):
        ACCENT = T['ACCENT_SOLID']
        BG_DARK = T['BG_DEEP']
        SIDEBAR_BG = "#080b10"
        
        self.setStyleSheet(f"""
            QFrame#RootWidget {{ background-color: {BG_DARK}; border: 1px solid {T['BORDER']}; border-radius: 8px; }}
            QFrame#Sidebar {{ background-color: {SIDEBAR_BG}; border-right: 1px solid #161b22; }}
            QFrame#Header {{ background-color: {BG_DARK}; border-bottom: 1px solid #161b22; }}
            QFrame#UserTile {{ background-color: rgba(255,255,255,0.02); border-top: 1px solid #161b22; }}

            QPushButton#NavButton {{ 
                background: transparent; color: #8b949e; border: none; border-radius: 4px;
                text-align: left; padding-left: 15px; font-weight: 700; font-size: 11px; letter-spacing: 1px;
            }}
            QPushButton#NavButton:hover {{ background: rgba(88, 166, 255, 0.05); color: {ACCENT}; }}
            QPushButton#NavButton:checked {{ 
                color: white; background: {ACCENT}; font-weight: 900; border-left: 4px solid #ffffff; 
            }}

            QPushButton#Ctrl {{ background: transparent; color: #8b949e; border: none; font-size: 12px; }}
            QPushButton#CtrlClose {{ background: transparent; color: #8b949e; border: none; font-size: 12px; }}
            QPushButton#Ctrl:hover {{ color: white; background: #30363d; border-radius: 4px; }}
            QPushButton#CtrlClose:hover {{ color: white; background: #da3633; border-radius: 4px; }}

            QProgressBar#StorageBar {{ background-color: #161b22; border: none; border-radius: 1px; }}
            QProgressBar#StorageBar::chunk {{ background-color: {ACCENT}; }}
        """)

    def update_storage_stats(self):
        try:
            total, used, free = shutil.disk_usage(BASE_PATH)
            percent_used = int((used / total) * 100)
            free_gb = free / (1024**3)
            self.storage_bar.setValue(percent_used)
            self.storage_info.setText(f"CAPACITY: {free_gb:.1f} GB SECURE")
        except:
            self.storage_info.setText("CAPACITY: ERROR")

    def handle_nav_click(self):
        sender = self.sender()
        if not sender: return
        for btn in self.nav_buttons.values(): btn.setChecked(False)
        sender.setChecked(True)
        display_text = sender.text().strip()
        logical_key = self.nav_map.get(display_text)
        if logical_key in self.pages:
            self.stack.setCurrentWidget(self.pages[logical_key])
            self.header_title.setText(display_text)

    def center_window(self):
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.header.underMouse():
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.header.underMouse():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()