# [vault_page.py]

import random
import string
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel,
    QListWidget, QInputDialog, QMessageBox, QDialog, QHBoxLayout, 
    QApplication, QFrame
)
from PySide6.QtCore import Qt
from Everything_else.ghostvault import add_secret, get_secrets, delete_secret
from .style_config import (
    T, FONT_MAIN, FONT_SIZE, STYLE_BUTTON, STYLE_INPUT,
    ghost_prompt, ghost_alert, TacticalDialog, STYLE_SCROLLBAR
)

class VaultPage(QWidget):
    def __init__(self, username, passphrase, fernet):
        super().__init__()
        self.username = username
        self.passphrase = passphrase
        self.fernet = fernet
        self.secrets = {}

        # Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(15)

        # 2. SEARCH & ADD
        top_bar = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search vault entries...")
        self.search_bar.setFixedHeight(40)
        self.search_bar.setStyleSheet(STYLE_INPUT)
        
        self.add_btn = QPushButton("+ New Entry")
        self.add_btn.setFixedSize(140, 40)
        self.add_btn.setStyleSheet(STYLE_BUTTON)
        self.add_btn.clicked.connect(self.add_secret_ui)
        
        top_bar.addWidget(self.search_bar)
        top_bar.addWidget(self.add_btn)
        self.layout.addLayout(top_bar)

        # 3. VAULT LIST
        self.secret_list = QListWidget()
        self.secret_list.itemDoubleClicked.connect(self.show_secret_popup)
        self.secret_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {T['BG_CARD']};
                border: 1px solid {T['BORDER']};
                border-radius: 12px;
                color: {T['TEXT_MAIN']};
                padding: 5px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 16px;
                border-bottom: 1px solid {T['BORDER']};
                font-family: '{FONT_MAIN}';
            }}
            QListWidget::item:selected {{
                background-color: {T['ACCENT_GLOW']};
                color: {T['ACCENT_SOLID']};
                font-weight: bold;
                border-radius: 8px;
            }}
            {STYLE_SCROLLBAR}
        """)
        self.layout.addWidget(self.secret_list)

        # 4. Footer Controls
        footer = QHBoxLayout()
        self.edit_btn = QPushButton("Edit Entry")
        self.del_btn = QPushButton("Delete")
        
        for btn in [self.edit_btn, self.del_btn]:
            btn.setStyleSheet(STYLE_BUTTON)
            btn.setFixedHeight(38)
            footer.addWidget(btn)
            
        self.edit_btn.clicked.connect(self.edit_selected)
        self.del_btn.clicked.connect(self.delete_selected)
        self.layout.addLayout(footer)

        self.refresh_vault()
        self.search_bar.textChanged.connect(self.filter_secrets)

    def refresh_vault(self):
        self.secret_list.clear()
        try:
            self.secrets = get_secrets(self.username, self.passphrase)
            for name in sorted(self.secrets.keys(), key=str.lower):
                self.secret_list.addItem(name)
        except Exception as e:
            # Replaced QMessageBox.critical
            ghost_alert(self, "VAULT ERROR", f"ACCESS DENIED: {str(e)}")

    def filter_secrets(self, text):
        self.secret_list.clear()
        filtered = [n for n in sorted(self.secrets.keys(), key=str.lower)
                    if text.lower() in n.lower()]
        for name in filtered:
            self.secret_list.addItem(name)


    def show_secret_popup(self, item):
        """Re-styled to use the TacticalDialog container for consistency"""
        secret_name = item.text()
        data = self.secrets.get(secret_name, {})
        u_val = data.get("username", "N/A") if isinstance(data, dict) else "[Legacy]"
        p_val = data.get("password", "N/A") if isinstance(data, dict) else str(data)

        # Using TacticalDialog as a base to keep the frame, gold border, and scanlines
        dialog = TacticalDialog(self, title=f"DECRYPTED: {secret_name}", label="CREDENTIALS")
        dialog.input_field.hide() # Hide default single input
        
        # Create the view layout
        view_layout = QVBoxLayout()
        
        u_field = QLineEdit(u_val)
        u_field.setReadOnly(True)
        u_field.setStyleSheet(STYLE_INPUT)
        
        p_field = QLineEdit(p_val)
        p_field.setEchoMode(QLineEdit.Password)
        p_field.setReadOnly(True)
        p_field.setStyleSheet(STYLE_INPUT)
        
        h_buttons = QHBoxLayout()
        show_btn = QPushButton("Show Password")
        show_btn.setStyleSheet(STYLE_BUTTON)
        copy_btn = QPushButton("Copy")
        copy_btn.setStyleSheet(STYLE_BUTTON)
        
        def toggle():
            is_pass = p_field.echoMode() == QLineEdit.Password
            p_field.setEchoMode(QLineEdit.Normal if is_pass else QLineEdit.Password)
            show_btn.setText("Hide Password" if is_pass else "Show Password")
            
        show_btn.clicked.connect(toggle)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(p_field.text()))
        
        h_buttons.addWidget(show_btn)
        h_buttons.addWidget(copy_btn)
        
        view_layout.addWidget(QLabel("USERNAME"))
        view_layout.addWidget(u_field)
        view_layout.addWidget(QLabel("PASSWORD"))
        view_layout.addWidget(p_field)
        view_layout.addLayout(h_buttons)
        
        # Inject into tactical frame
        dialog.container.layout().insertLayout(3, view_layout)
        dialog.confirm_btn.setText("DONE")
        dialog.cancel_btn.hide() # Only need one button to close
        
        dialog.exec()

    def _tactical_entry_dialog(self, title, u_val="", p_val=""):
        """The missing engine for your Add/Edit functions"""
        dialog = TacticalDialog(self, title=title, label="USER & PASSWORD")
        dialog.input_field.hide()
        
        form_layout = QVBoxLayout()
        
        u_input = QLineEdit(u_val)
        u_input.setPlaceholderText("Username...")
        u_input.setStyleSheet(dialog.input_field.styleSheet())
        
        p_input = QLineEdit(p_val)
        p_input.setPlaceholderText("Password...")
        p_input.setStyleSheet(dialog.input_field.styleSheet())
        
        gen_btn = QPushButton("SUGGEST STRONG")
        gen_btn.clicked.connect(lambda: p_input.setText(self.generate_password_suggestion()))
        
        form_layout.addWidget(u_input)
        form_layout.addWidget(p_input)
        form_layout.addWidget(gen_btn)
        
        dialog.container.layout().insertLayout(3, form_layout)
        
        if dialog.exec() == QDialog.Accepted:
            return {'u': u_input.text(), 'p': p_input.text()}
        return None

    def show_secret_popup(self, item):
        """Re-styled to use Tactical Gold accents for internal buttons"""
        secret_name = item.text()
        data = self.secrets.get(secret_name, {})
        u_val = data.get("username", "N/A") if isinstance(data, dict) else "[Legacy]"
        p_val = data.get("password", "N/A") if isinstance(data, dict) else str(data)

        dialog = TacticalDialog(self, title=f"DECRYPTED: {secret_name}")
        dialog.input_field.hide() 
        
        view_layout = QVBoxLayout()
        
        u_field = QLineEdit(u_val)
        u_field.setReadOnly(True)
        u_field.setStyleSheet(STYLE_INPUT)
        
        p_field = QLineEdit(p_val)
        p_field.setEchoMode(QLineEdit.Password)
        p_field.setReadOnly(True)
        p_field.setStyleSheet(STYLE_INPUT)
        
        h_buttons = QHBoxLayout()
        
        # --- NEW TACTICAL BUTTON STYLE ---
        TACTICAL_BTN = f"""
            QPushButton {{ 
                background: rgba(255, 176, 0, 0.1); 
                border: 1px solid {T['HUD_LINE']}; 
                color: {T['PROTOCOL_GOLD']}; 
                padding: 8px; 
                font-weight: bold; 
                border-radius: 4px; 
            }}
            QPushButton:hover {{ background: rgba(255, 176, 0, 0.2); }}
        """

        show_btn = QPushButton("SHOW")
        show_btn.setStyleSheet(TACTICAL_BTN)
        copy_btn = QPushButton("COPY")
        copy_btn.setStyleSheet(TACTICAL_BTN)
        
        def toggle():
            is_pass = p_field.echoMode() == QLineEdit.Password
            p_field.setEchoMode(QLineEdit.Normal if is_pass else QLineEdit.Password)
            show_btn.setText("HIDE" if is_pass else "SHOW")
            
        show_btn.clicked.connect(toggle)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(p_field.text()))
        
        h_buttons.addWidget(show_btn)
        h_buttons.addWidget(copy_btn)
        
        view_layout.addWidget(QLabel("USERNAME"))
        view_layout.addWidget(u_field)
        view_layout.addWidget(QLabel("PASSWORD"))
        view_layout.addWidget(p_field)
        view_layout.addLayout(h_buttons)
        
        dialog.container.layout().insertLayout(3, view_layout)
        dialog.confirm_btn.setText("DONE")
        dialog.cancel_btn.hide()
        
        dialog.exec()

    def _tactical_entry_dialog(self, title, u_val="", p_val=""):
        """Updated Suggest button to match Protocol Gold theme"""
        dialog = TacticalDialog(self, title=title, label="USER & PASSWORD")
        dialog.input_field.hide()
        
        form_layout = QVBoxLayout()
        
        # Use the same input style as the dialog's hidden field
        input_style = dialog.input_field.styleSheet()
        
        u_input = QLineEdit(u_val)
        u_input.setPlaceholderText("Username...")
        u_input.setStyleSheet(input_style)
        
        p_input = QLineEdit(p_val)
        p_input.setPlaceholderText("Password...")
        p_input.setStyleSheet(input_style)
        
        # --- MATCHING THE DIALOG CONFIRM BUTTON STYLE ---
        gen_btn = QPushButton("GENERATE STRONG PASSWORD")
        gen_btn.setStyleSheet(f"""
            QPushButton {{ 
                background: rgba(255, 176, 0, 0.15); 
                border: 1px solid {T['PROTOCOL_GOLD']}; 
                color: {T['PROTOCOL_GOLD']}; 
                padding: 10px; 
                font-weight: bold; 
                border-radius: 4px; 
                margin-top: 5px;
            }}
            QPushButton:hover {{ background: rgba(255, 176, 0, 0.25); }}
        """)
        gen_btn.clicked.connect(lambda: p_input.setText(self.generate_password_suggestion()))
        
        form_layout.addWidget(u_input)
        form_layout.addWidget(p_input)
        form_layout.addWidget(gen_btn)
        
        dialog.container.layout().insertLayout(3, form_layout)
        
        if dialog.exec() == QDialog.Accepted:
            return {'u': u_input.text(), 'p': p_input.text()}
        return None

    def add_secret_ui(self):
        name, ok1 = ghost_prompt(self, "NEW ENTRY", "SYSTEM/SITE NAME:")
        if not ok1 or not name: return

        data = self._tactical_entry_dialog(f"CREDENTIALS: {name}")
        if data:
            try:
                add_secret(self.username, self.passphrase, name, data['u'], data['p'])
                self.refresh_vault()
            except Exception as e:
                ghost_alert(self, "ERROR", f"STOWAGE FAILED: {str(e)}")

    def edit_selected(self):
        selected = self.secret_list.currentItem()
        if not selected: return
        
        old_name = selected.text()
        raw_data = self.secrets.get(old_name, {})
        u_init = raw_data.get("username", "") if isinstance(raw_data, dict) else ""
        p_init = raw_data.get("password", "") if isinstance(raw_data, dict) else str(raw_data)

        # Reuse the tactical dialog with initial values
        data = self._tactical_entry_dialog(f"EDIT: {old_name}", u_init, p_init)
        if data:
            try:
                delete_secret(self.username, self.passphrase, old_name)
                add_secret(self.username, self.passphrase, old_name, data['u'], data['p'])
                self.refresh_vault()
            except Exception as e:
                ghost_alert(self, "ERROR", f"UPDATE FAILED: {str(e)}")

    def delete_selected(self):
        selected = self.secret_list.currentItem()
        if not selected: return
        name = selected.text()
        
        if ghost_alert(self, "TERMINATE ENTRY", f"PERMANENTLY ERASE {name}?"):
            try:
                delete_secret(self.username, self.passphrase, name)
                self.refresh_vault()
            except Exception as e:
                ghost_alert(self, "ERROR", f"DELETION FAILED: {str(e)}")

    def generate_password_suggestion(self) -> str:
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choices(chars, k=random.randint(14, 18)))