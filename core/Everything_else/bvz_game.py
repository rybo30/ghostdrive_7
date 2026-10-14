# bvz_game.py

import sys
import os
import random
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QStackedWidget, 
                             QFrame, QLineEdit)
from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen

# Integrating your custom path logic
from core.paths import GAMES_DIR
import core.ui.style_config as style

class GameButton(QPushButton):
    def __init__(self, text, color="#00ffcc", is_scam=False):
        super().__init__(text)
        self.border_color = color if not is_scam else "#ff4444"
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.update_style()

    def update_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #111;
                border: 2px solid {self.border_color};
                color: {self.border_color};
                font-family: 'Segoe UI', sans-serif;
                font-weight: bold;
                padding: 12px;
                min-width: 140px;
                border-radius: 8px;
                font-size: 11px;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {self.border_color};
                color: black;
            }}
            QPushButton:checked {{
                background-color: {self.border_color};
                color: black;
                border: 2px solid white;
            }}
        """)

class GameEngine(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(950, 750)
        
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            center = screen.availableGeometry().center()
            self.move(center - self.rect().center())
        
        self.game_data = self.load_game_data()
        
        self.container = QFrame()
        self.container.setObjectName("MainFrame")
        self.container.setStyleSheet("background-color: #0f0f12; border: 1px solid #333; border-radius: 20px;")
        
        self.stack = QStackedWidget()
        layout = QVBoxLayout(self.container)
        layout.addWidget(self.stack)
        self.setCentralWidget(self.container)
        
        self.player_type = None
        self.balance = 0
        self.ai_balance = 0 
        self.turn = 1
        self.max_turns = 12 
        
        self.init_selection_screen()

    def load_game_data(self):
        path = os.path.join(GAMES_DIR, "bvz_game_data.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {
                "boomer": {
                    "assets": {"phase_1": [{"name": "Rental Property", "max_gain": 0.2, "max_loss": -0.05, "success": 0.8}]},
                    "scams": [{"name": "Fake Lottery", "chance": 0.15, "loss": 10000}]
                },
                "zoomer": {
                    "assets": {"phase_1": [{"name": "Meme Coin Moonshot", "max_gain": 10.0, "max_loss": -0.9, "success": 0.2}]},
                    "scams": [{"name": "Gacha Game Spend", "chance": 0.3, "loss": 200}]
                }
            }

    def init_selection_screen(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        title = QLabel("BOOMERS VS. ZOOMERS")
        title.setStyleSheet("color: white; font-size: 36px; font-weight: 900; margin-top: 40px; border: none;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        
        cards = QHBoxLayout()
        cards.addWidget(self.create_card("BOOMER", "#b8860b", "Start with $1M.\nDon't let the kids take it!"))
        cards.addWidget(self.create_card("ZOOMER", "#ff00ff", "Start with $1k.\nEscape the basement!"))
        lay.addLayout(cards)
        self.stack.addWidget(page)

    def create_card(self, p_type, color, desc):
        card = QFrame()
        card.setStyleSheet(f"border: 2px solid {color}; background: #1a1a1e; border-radius: 15px; margin: 10px;")
        l = QVBoxLayout(card)
        t = QLabel(p_type); t.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold; border: none;")
        d = QLabel(desc); d.setStyleSheet("color: #bbb; font-size: 14px; border: none;")
        btn = GameButton(f"PLAY AS {p_type}", color)
        btn.setCheckable(False)
        btn.clicked.connect(lambda: self.start_game(p_type.lower()))
        l.addWidget(t); l.addStretch(); l.addWidget(d); l.addWidget(btn)
        return card

    def start_game(self, p_type):
        self.player_type = p_type
        self.ai_type = "zoomer" if p_type == "boomer" else "boomer"
        self.accent = "#b8860b" if p_type == "boomer" else "#ff00ff"
        self.ai_accent = "#ff00ff" if p_type == "boomer" else "#b8860b"
        self.balance = 1000000 if p_type == "boomer" else 1000
        self.ai_balance = 1000 if p_type == "boomer" else 1000000
        self.init_game_ui()
        self.stack.setCurrentIndex(1)

    def init_game_ui(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(40, 30, 40, 30)

        # 1. SCOREBOARD HUD
        hud = QHBoxLayout()
        self.user_score_lbl = QLabel()
        self.ai_score_lbl = QLabel()
        self.turn_lbl = QLabel()
        score_css = "font-size: 28px; font-weight: 900; border: none;"
        self.user_score_lbl.setStyleSheet(f"color: {self.accent}; {score_css}")
        self.ai_score_lbl.setStyleSheet(f"color: {self.ai_accent}; {score_css}")
        self.turn_lbl.setStyleSheet("color: #444; font-size: 16px; font-weight: bold; border: none;")
        hud.addWidget(self.user_score_lbl); hud.addStretch(); hud.addWidget(self.turn_lbl); hud.addStretch(); hud.addWidget(self.ai_score_lbl)
        lay.addLayout(hud)

        # 2. LIVE FEED (Updated to be friendly)
        self.terminal = QFrame()
        self.terminal.setStyleSheet("background-color: #0f0f12; border: 2px solid #222; border-radius: 10px;")
        term_lay = QVBoxLayout(self.terminal)
        term_header = QLabel("MARKET HISTORY")
        term_header.setStyleSheet("color: #555; font-size: 10px; font-weight: bold; letter-spacing: 2px; border: none;")
        term_lay.addWidget(term_header, alignment=Qt.AlignCenter)

        self.feed_container = QVBoxLayout()
        self.feed_container.setSpacing(8)
        self.feed_container.addStretch()
        term_lay.addLayout(self.feed_container)
        lay.addWidget(self.terminal, stretch=1)

        # 3. ACTION PANEL
        ctrl = QFrame(); ctrl.setStyleSheet("border: none;")
        c_lay = QVBoxLayout(ctrl)
        
        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(QLabel("AMT: $", styleSheet="color: #666; font-weight: bold; border: none;"))
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        self.amount_input.setFixedWidth(200)
        self.amount_input.setStyleSheet(f"background: #111; color: white; border: 1px solid {self.accent}; padding: 10px; border-radius: 5px; font-size: 18px;")
        input_row.addWidget(self.amount_input)
        input_row.addStretch()
        c_lay.addLayout(input_row)

        self.asset_lay = QHBoxLayout(); c_lay.addLayout(self.asset_lay)
        self.scam_lay = QHBoxLayout(); c_lay.addLayout(self.scam_lay)

        self.exec_btn = GameButton("EXECUTE STRATEGY", self.accent)
        self.exec_btn.setCheckable(False)
        self.exec_btn.setMinimumHeight(60)
        self.exec_btn.clicked.connect(self.process_turn)
        c_lay.addWidget(self.exec_btn)

        lay.addWidget(ctrl)
        self.update_ui()
        self.stack.addWidget(page)

    def add_feed_event(self, text, color="#00ffcc"):
        # Remove the bottom stretch so the new item pushes everything up correctly
        if self.feed_container.count() > 0:
            item = self.feed_container.takeAt(self.feed_container.count() - 1)
            if item and item.widget(): 
                item.widget().deleteLater()
        
        # Create the new "Friendly" message bubble
        event = QLabel(text)
        event.setStyleSheet(style.STYLE_PLAY_BY_PLAY.format(color=color))
        event.setWordWrap(True)
        
        # Add it to the feed
        self.feed_container.addWidget(event)
        
        # Keep only the last 6 entries to maintain plenty of "white space" 
        # (This is key for the 'uninviting' cold look you mentioned!)
        if self.feed_container.count() > 6:
            old_item = self.feed_container.takeAt(0)
            if old_item and old_item.widget(): 
                old_item.widget().deleteLater()
            
        # Re-add the stretch at the end
        self.feed_container.addStretch()

    def update_ui(self):
        self.user_score_lbl.setText(f"YOU: ${self.balance:,}")
        self.ai_score_lbl.setText(f"AI: ${self.ai_balance:,}")
        self.turn_lbl.setText(f"ROUND {self.turn}/{self.max_turns}")
        
        current_phase = "phase_1"
        if self.turn > 8: current_phase = "phase_3"
        elif self.turn > 4: current_phase = "phase_2"

        for lay in [self.asset_lay, self.scam_lay]:
            while lay.count():
                w = lay.takeAt(0).widget()
                if w: w.deleteLater()

        p_data = self.game_data[self.player_type]
        assets = p_data.get("assets", {}).get(current_phase, p_data.get("assets", {}).get("phase_1", []))
        self.asset_group = []
        for a in random.sample(assets, min(len(assets), 3)):
            btn = GameButton(a['name'], self.accent)
            btn.clicked.connect(lambda _, b=btn: self.sync_btns(b, self.asset_group))
            self.asset_lay.addWidget(btn)
            self.asset_group.append((btn, a))

        scams = p_data.get("scams", [])
        self.scam_group = []
        for s in random.sample(scams, min(len(scams), 2)):
            btn = GameButton(s['name'], "#ff4444", True)
            btn.clicked.connect(lambda _, b=btn: self.sync_btns(b, self.scam_group))
            self.scam_lay.addWidget(btn)
            self.scam_group.append((btn, s))

    def sync_btns(self, clicked, group):
        for btn, data in group:
            if btn != clicked: btn.setChecked(False)

    def process_turn(self):
        asset_data = next((d for b, d in self.asset_group if b.isChecked()), None)
        blocked_scam = next((d for b, d in self.scam_group if b.isChecked()), None)
        
        if not asset_data:
            style.ghost_alert(self, "SYSTEM ERROR", "Select an asset to trade.")
            return

        try:
            amt = int(self.amount_input.text().replace(',', '').replace('$', ''))
        except: amt = 0

        if amt <= 0 or amt > self.balance:
            style.ghost_alert(self, "FUNDS ERROR", "Insufficient liquidity.")
            return

        # Player Result Logic
        prefix = f"<b>ROUND {self.turn}</b> | "
        self.balance -= amt
        if random.random() <= asset_data['success']:
            gain = int(amt * (1 + random.uniform(asset_data.get('min_gain', 0.1), asset_data.get('max_gain', 0.2))))
            self.balance += gain
            u_info = f"{prefix}PROFIT: Your ${amt:,} in {asset_data['name']} yielded +${gain-amt:,}."
            u_win = True
        else:
            loss_rem = int(amt * (1 + random.uniform(asset_data.get('max_loss', -0.5), -0.1)))
            self.balance += loss_rem
            u_info = f"{prefix}LOSS: {asset_data['name']} crashed. You lost ${amt-loss_rem:,} on your ${amt:,} investment."
            u_win = False

        # Scam check - ONLY runs the scam that is currently selected/highlighted
        selected_scam_data = next((d for b, d in self.scam_group if b.isChecked()), None)
        
        if selected_scam_data:
            # Only the highlighted scam has a chance to trigger
            if random.random() <= selected_scam_data.get('chance', 0.15):
                lost = min(selected_scam_data['loss'], self.balance)
                self.balance -= lost
                u_info += f" | 🚨 SCAM: {selected_scam_data['name']} drained ${lost:,}!"
            else:
                # Optional: Feedback that they dodged the specific scam they chose
                u_info += f" | ✅ Safe: {selected_scam_data['name']} avoided."

        # AI Result Logic
        ai_data = self.game_data[self.ai_type]
        ai_asset = random.choice(ai_data['assets']['phase_1'])
        ai_amt = int(self.ai_balance * random.uniform(0.1, 0.3))
        self.ai_balance -= ai_amt
        if random.random() <= ai_asset['success']:
            ai_gain = int(ai_amt * (1 + random.uniform(0.1, 0.2)))
            self.ai_balance += ai_gain
            a_info = f"{prefix}AI PROFIT: +${ai_gain-ai_amt:,} via {ai_asset['name']} (Invested: ${ai_amt:,})"
            a_win = True
        else:
            ai_loss_rem = int(ai_amt * 0.7); self.ai_balance += ai_loss_rem
            a_info = f"{prefix}AI LOSS: -${ai_amt-ai_loss_rem:,} via {ai_asset['name']} (Invested: ${ai_amt:,})"
            a_win = False

        # Update Feed
        self.add_feed_event(u_info, "#00ffcc" if u_win else "#ff4444")
        self.add_feed_event(a_info, "#888")

        if self.turn >= self.max_turns:
            self.end_game()
        else:
            self.turn += 1
            self.amount_input.clear()
            self.update_ui()

    def end_game(self):
        winner = "YOU WIN" if self.balance > self.ai_balance else "AI WINS"
        self.add_feed_event(f"<b>FINAL REPORT</b>: {winner}. YOU: ${self.balance:,} | AI: ${self.ai_balance:,}", "#fff")
        self.exec_btn.setText("TERMINATE SESSION")
        self.exec_btn.clicked.disconnect()
        self.exec_btn.clicked.connect(self.close)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton: self.move(e.globalPos() - self._drag_pos)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = GameEngine(); game.show()
    sys.exit(app.exec())