# [login_window.py]

import os
import sys
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame, QApplication, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QPropertyAnimation, QPoint, QTimer, QEasingCurve
from cryptography.fernet import Fernet

from core.identity import get_hardware_locked_identity

from .style_config import (
    FONT_FAMILY, T, COLOR_BG, COLOR_FG, COLOR_ACCENT, 
    STYLE_INPUT, STYLE_BUTTON
)

# --- ORIGINAL SYSTEM PATHS ---
try:
    from ghostvault import (
        get_vault_paths, load_key_from_passphrase, create_new_user, user_exists, decrypt_vault
    )
except ImportError:
    from Everything_else.ghostvault import (
        get_vault_paths, load_key_from_passphrase, create_new_user, user_exists, decrypt_vault
    )

# --- THEME CONFIG ---
from .style_config import (
    FONT_FAMILY, T, COLOR_BG, COLOR_FG, COLOR_ACCENT, 
    STYLE_INPUT, STYLE_BUTTON
)

class LoginWindow(QWidget):
    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        self.fail_count = 0 
        self.is_first_time = False  # Track if account creation triggered login

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground) 
        self.setFixedSize(400, 480) 

        self.master_layout = QVBoxLayout(self)
        self.master_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Main UI Container
        self.container = QFrame()
        self.container.setObjectName("MainContainer")
        self.master_layout.addWidget(self.container)
        
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(50, 30, 50, 40) 
        self.layout.setSpacing(12) 

        self.title_label = QLabel("GHOSTDRIVE ACCESS")
        self.title_label.setAlignment(Qt.AlignCenter)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("IDENTIFICATION")

        self.passphrase_input = QLineEdit()
        self.passphrase_input.setPlaceholderText("SECURITY PASSPHRASE")
        self.passphrase_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {T['TEXT_DIM']}; font-size: 10px; font-weight: 700; letter-spacing: 1px;")

        self.login_btn = QPushButton("INITIALIZE LOGIN")
        self.login_btn.setObjectName("LoginBtn")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setMinimumHeight(45)
        self.login_btn.clicked.connect(self.try_login)

        self.create_btn = QPushButton("CREATE NEW ACCOUNT")
        self.create_btn.setObjectName("SecondaryBtn")
        self.create_btn.setCursor(Qt.PointingHandCursor)
        self.create_btn.setMinimumHeight(40)
        self.create_btn.clicked.connect(self.create_account)

        self.layout.addStretch(2) 
        self.layout.addWidget(self.title_label)
        self.layout.addSpacing(25) 
        self.layout.addWidget(self.username_input)
        self.layout.addWidget(self.passphrase_input)
        self.layout.addSpacing(10)
        self.layout.addWidget(self.status_label) 
        self.layout.addWidget(self.login_btn)
        self.layout.addWidget(self.create_btn)
        self.layout.addStretch(3) 

        # 2. THE TRANSITION OVERLAY (The "Void")
        self.void_overlay = QFrame(self.container)
        self.void_overlay.setGeometry(0, 0, 400, 480)
        self.void_overlay.setStyleSheet("background-color: #000000; border-radius: 18px;")
        self.void_overlay.hide()

        self.bubble = QLabel("", self.void_overlay)
        self.bubble.setAlignment(Qt.AlignCenter)
        self.bubble.setFixedSize(240, 240) # Slightly bigger to fit names
        self.bubble.move(80, 120) 
        self.bubble.setWordWrap(True)
        self.bubble.setStyleSheet(f"color: white; font-family: '{FONT_FAMILY}'; font-weight: 900; font-size: 18px; letter-spacing: 1px; padding: 20px;")

        self.apply_theme()

    def run_transition(self, text, color, is_success=False, success_callback=None):
        """Unified animation for both 'GET OUT' and 'WELCOME'"""
        self.bubble.setText(text.upper())
        self.bubble.setStyleSheet(self.bubble.styleSheet() + f"background-color: {color}; border-radius: 120px;")
        
        self.void_overlay.show()
        self.fade_effect = QGraphicsOpacityEffect(self.void_overlay)
        self.void_overlay.setGraphicsEffect(self.fade_effect)
        
        self.anim = QPropertyAnimation(self.fade_effect, b"opacity")
        self.anim.setDuration(1200) 
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        if is_success:
            self.anim.finished.connect(lambda: QTimer.singleShot(1000, success_callback))
        else:
            self.anim.finished.connect(lambda: QTimer.singleShot(2000, sys.exit))
            
        self.anim.start()

    def try_login(self):
        username = self.username_input.text().strip()
        passphrase = self.passphrase_input.text().strip()

        if not username or not passphrase:
            self.shake_feedback()
            return

        if not user_exists(username):
            self.fail_count += 1
            self.status_label.setText("IDENTITY NOT FOUND")
            self.shake_feedback()
            if self.fail_count >= 2: self.run_transition("GET OUT", "#ff0000")
            return

        try:
            vault_path, salt_path = get_vault_paths(username)
            key = load_key_from_passphrase(passphrase, salt_path)
            fernet = Fernet(key)

            vault_data = decrypt_vault(fernet, vault_path)
            if isinstance(vault_data, dict) and vault_data.get("ERROR") == "DECRYPTION_FAILURE":
                raise ValueError("Wrong Passphrase")

            identity_data = get_hardware_locked_identity(username, passphrase, salt_path)
            app = QApplication.instance()
            app.ghost_id = identity_data["identity_pub_hex"]
            app.private_key = identity_data["sync_priv"]

            # --- CUSTOM SUCCESS ANIMATION FOR NEW VS RETURNING USERS ---
            if self.is_first_time:
                msg = f"Welcome to GhostDrive, {username}"
                color = T['PROTOCOL_GOLD']
            else:
                msg = f"SYSTEMS ENGAGED.\n Welcome back, {username}"
                color = "#2ea043"  # Green

            self.run_transition(
                text=msg,
                color=color,
                is_success=True,
                success_callback=lambda: self.finalize_login(username, passphrase, fernet)
            )

        except Exception:
            self.fail_count += 1
            self.status_label.setText("INVALID PASSPHRASE")
            self.shake_feedback()
            if self.fail_count >= 2:
                self.run_transition("GET OUT", "#ff0000")

    def create_account(self):
        username = self.username_input.text().strip()
        passphrase = self.passphrase_input.text().strip()
        if not username or not passphrase or user_exists(username):
            self.shake_feedback()
            return
        try:
            create_new_user(username, passphrase)
            self.is_first_time = True  # Set flag for new account creation
            self.login_btn.setText("IDENTITY SECURED")
            self.login_btn.setProperty("success", True)
            self.login_btn.style().unpolish(self.login_btn)
            self.login_btn.style().polish(self.login_btn)
            self.status_label.setText(f"LOGGING {username.upper()} IN...")
            QTimer.singleShot(1000, self.try_login)
        except Exception as e:
            self.show_tactical_msg("Failed", str(e))

    def finalize_login(self, u, p, f):
        self.on_login_success(u, p, f)
        self.close()

    def apply_theme(self):
        self.setStyleSheet("background: transparent;")
        self.container.setStyleSheet(f"QFrame#MainContainer {{ background-color: {COLOR_BG}; border: 2px solid {COLOR_ACCENT}; border-radius: 20px; }} {STYLE_INPUT} {STYLE_BUTTON}")
        self.title_label.setObjectName("Title")
        self.title_label.setStyleSheet(f"color: {COLOR_ACCENT}; font-family: '{FONT_FAMILY}'; font-size: 20px; font-weight: 900; letter-spacing: 3px;")

    def shake_feedback(self):
        self.shake_anim = QPropertyAnimation(self.container, b"pos")
        self.shake_anim.setDuration(50)
        self.shake_anim.setLoopCount(4)
        curr = self.container.pos()
        self.shake_anim.setKeyValueAt(0, curr)
        self.shake_anim.setKeyValueAt(0.25, curr + QPoint(-10, 0))
        self.shake_anim.setKeyValueAt(0.75, curr + QPoint(10, 0))
        self.shake_anim.setKeyValueAt(1, curr)
        self.shake_anim.start()

    def show_tactical_msg(self, title, text, icon=QMessageBox.Warning):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.setStyleSheet(f"background-color: {COLOR_BG}; color: {COLOR_FG}; border: 1px solid {COLOR_ACCENT};")
        return msg.exec()