import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QScrollArea, QGridLayout, QLineEdit
)
from PySide6.QtCore import Qt
from .style_config import COLOR_FG, COLOR_ACCENT, T, STYLE_BUTTON, STYLE_INPUT, STYLE_SCROLLBAR
from core.Everything_else.game_engine import GameEngine

class GameCard(QFrame):
    def __init__(self, game_id, title, description, license_info, engine, is_proprietary=False):
        super().__init__()
        self.game_id = game_id
        self.title_text = title.lower() 
        self.engine = engine
        
        self.setFixedHeight(180) 
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {T['BG_PANEL']};
                border: 1px solid {T['BORDER']};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {COLOR_ACCENT};
                background-color: {T['BG_CARD']};
            }}
        """)
        
        # Main Layout with tighter margins to prevent text cutoff
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8) 
        
        # Header Row: Title + Badge
        header = QHBoxLayout()
        header.setSpacing(10)
        
        title_lbl = QLabel(title.upper())
        # Added 'line-height' feel via padding and ensuring no border interference
        title_lbl.setStyleSheet(f"""
            color: {COLOR_FG}; 
            font-size: 14px; 
            font-weight: bold; 
            border: none; 
            background: transparent;
        """)
        header.addWidget(title_lbl)
        
        if is_proprietary:
            badge = QLabel("ORIGINAL")
            badge.setStyleSheet(f"""
                color: #FFA500; 
                font-size: 8px; 
                font-weight: bold; 
                border: 1px solid #FFA500; 
                border-radius: 4px; 
                padding: 2px 5px;
                background: transparent;
            """)
            header.addWidget(badge)
            
        header.addStretch()
        layout.addLayout(header)

        # Description
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        # Increased bottom margin via style to push license down
        desc_lbl.setStyleSheet(f"""
            color: #8b949e; 
            font-size: 11px; 
            border: none; 
            background: transparent;
            margin-bottom: 5px;
        """)
        layout.addWidget(desc_lbl)
        
        layout.addStretch() # This pushes the button and license to the bottom

        # License Info
        license_lbl = QLabel(f"LIC: {license_info}")
        license_lbl.setStyleSheet(f"""
            color: rgba(88, 166, 255, 0.3); 
            font-size: 9px; 
            border: none; 
            background: transparent;
        """)
        layout.addWidget(license_lbl)

        # Execute Button Style Fix
        self.play_btn = QPushButton("EXECUTE")
        self.play_btn.setCursor(Qt.PointingHandCursor)
        # Using a specialized style string for the arcade buttons to ensure alignment
        arcade_btn_style = f"""
            QPushButton {{
                background: {T['ACCENT']};
                color: white;
                border-radius: 16px;
                font-weight: 800;
                font-size: 11px;
                padding: 8px;
            }}
            QPushButton:hover {{ background: {T['ACCENT_SOLID']}; }}
        """
        self.play_btn.setStyleSheet(arcade_btn_style)
        self.play_btn.setFixedHeight(32)
        self.play_btn.clicked.connect(lambda: self.engine.launch_game(self.game_id))
        layout.addWidget(self.play_btn)

class GamesPage(QWidget):
    def __init__(self, username, fernet):
        super().__init__()
        self.engine = GameEngine()
        self.cards = [] 
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20) # More space between search bar and grid
        
        # Header + Search Row
        top_row = QHBoxLayout()
        header = QLabel("ENTERTAINMENT SUBSYSTEM (Windows-only)")
        header.setStyleSheet(f"color: {COLOR_FG}; font-size: 18px; font-weight: 900; letter-spacing: 2px;")
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("SEARCH GAMES...")
        self.search_bar.setFixedWidth(280)
        self.search_bar.setStyleSheet(STYLE_INPUT)
        self.search_bar.textChanged.connect(self.filter_games)
        
        top_row.addWidget(header)
        top_row.addStretch()
        top_row.addWidget(self.search_bar)
        layout.addLayout(top_row)
        
        # Scroll Area with Parser-safe Stylesheet
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }} {STYLE_SCROLLBAR}")
        
        content = QWidget()
        content.setObjectName("ArcadeContent")
        content.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(content)
        self.grid.setSpacing(25) # Increased spacing between cards
        self.grid.setContentsMargins(0, 0, 15, 0)
        
        game_list = [
            ("bvz", "Boomers vs. Zoomers", "Tactical generational conflict simulation. Manage assets and avoid total ruin.", "GHOSTDRIVE PROPRIETARY", True),
            ("stk", "Super Tux Kart", "A 3D open-source arcade racer featuring a variety of characters and tracks.", "GNU GPL v3", False),
            ("blockout", "BlockOut II", "The classic 3D Tetris adaptation. Manipulate falling blocks in a three-dimensional pit to clear layers.", "GNU GPL v2", False),
        ]

        for i, (gid, title, desc, lic, prop) in enumerate(game_list):
            card = GameCard(gid, title, desc, lic, self.engine, prop)
            self.cards.append(card)
            self.grid.addWidget(card, i // 2, i % 2)

        self.grid.setRowStretch(99, 1) 

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def filter_games(self, text):
        search_text = text.lower()
        for card in self.cards:
            card.setVisible(search_text in card.title_text)