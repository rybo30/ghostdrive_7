import json
import os
import threading
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QListWidget, QListWidgetItem,
                             QFrame, QApplication, QCheckBox, QStackedWidget, QProgressBar,  
                             QDialog, QScrollArea)
from PySide6.QtCore import Qt

# Style and Path Imports
from ui.style_config import (COLOR_BG, COLOR_FG, COLOR_ACCENT, COLOR_BUTTON, 
                           COLOR_HIGHLIGHT, COLOR_PAGE_BG, COLOR_PROTOCOL, 
                           COLOR_BORDER, FONT_FAMILY, STYLE_BUTTON, STYLE_INPUT,
                           TacticalDialog, ghost_alert) # Added Tactical imports
from core.paths import EVERYTHING_ELSE
from core.network_manager import GhostNetwork 

# Logic Imports
from core.peers_manager import delete_peer, load_peers, save_peer

class SyncPage(QWidget):
    def __init__(self, username, fernet, ghost_id, private_key):
        super().__init__()
        self.username = username
        self.fernet = fernet
        self.ghost_id = ghost_id
        self.private_key = private_key
        
        # 1. INITIALIZE NETWORK
        self.network = GhostNetwork(self.username, self.fernet, self.ghost_id, self.private_key)
        
        # Start background threads
        threading.Thread(target=self.network.start_server, daemon=True).start()
        threading.Thread(target=self.network.start_broadcast, daemon=True).start()
        threading.Thread(target=self.network.listen_for_peers, daemon=True).start()
        
        self.setStyleSheet(f"background-color: {COLOR_PAGE_BG}; font-family: '{FONT_FAMILY}';")
        self.init_ui()
        self.refresh_peer_list()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- TOP BAR ---
        id_bar = QFrame()
        id_bar.setFixedHeight(80)
        id_bar.setStyleSheet(f"background-color: {COLOR_BG}; border-bottom: 1px solid {COLOR_BORDER};")
        id_bar_layout = QHBoxLayout(id_bar)
        
        id_info = QVBoxLayout()
        title = QLabel("LOCAL NODE ADDRESS")
        title.setStyleSheet(f"color: {COLOR_PROTOCOL}; font-weight: bold; font-size: 10px; border: none;")
        
        self.id_display = QLineEdit(self.ghost_id)
        self.id_display.setReadOnly(True)
        self.id_display.setStyleSheet(f"background: transparent; border: none; color: {COLOR_ACCENT}; font-size: 12px;")
        
        id_info.addWidget(title)
        id_info.addWidget(self.id_display)
        
        # IP Display Section
        self.my_ip_display = QLineEdit("IP: HIDDEN")
        self.my_ip_display.setReadOnly(True)
        self.my_ip_display.setFixedWidth(120)
        self.my_ip_display.setStyleSheet("color: #555; border: none; background: transparent; font-size: 11px;")
        
        show_ip_btn = QPushButton("SHOW IP")
        show_ip_btn.setObjectName("SecondaryBtn") # Use style config secondary
        show_ip_btn.setFixedWidth(80)
        show_ip_btn.setStyleSheet(STYLE_BUTTON)
        show_ip_btn.clicked.connect(self.reveal_ip)
        
        copy_btn = QPushButton("COPY ID")
        copy_btn.setStyleSheet(STYLE_BUTTON)
        copy_btn.setFixedWidth(100)
        copy_btn.clicked.connect(self.copy_id)
        
        id_bar_layout.addLayout(id_info)
        id_bar_layout.addStretch()
        id_bar_layout.addWidget(self.my_ip_display)
        id_bar_layout.addWidget(show_ip_btn)
        id_bar_layout.addWidget(copy_btn)
        main_layout.addWidget(id_bar)

        content_row = QHBoxLayout()
        content_row.setSpacing(0)

        # --- SIDEBAR ---
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(260)
        self.sidebar.setStyleSheet(f"background-color: {COLOR_BG}; border-right: 1px solid {COLOR_BORDER};")
        side_layout = QVBoxLayout(self.sidebar)
        
        side_lbl = QLabel("AUTHORIZED NETWORK")
        side_lbl.setStyleSheet(f"color: {COLOR_PROTOCOL}; font-size: 10px; font-weight: bold; margin-bottom: 5px;")
        side_layout.addWidget(side_lbl)

        self.peer_list_widget = QListWidget()
        self.peer_list_widget.setStyleSheet(f"""
            QListWidget {{ border: none; background: transparent; color: {COLOR_FG}; outline: none; }}
            QListWidget::item {{ padding: 15px; border-bottom: 1px solid {COLOR_BORDER}; }}
            QListWidget::item:selected {{ background-color: {COLOR_HIGHLIGHT}; color: {COLOR_FG}; border-left: 3px solid {COLOR_ACCENT}; }}
        """)
        self.peer_list_widget.currentRowChanged.connect(self.display_peer_details)
        side_layout.addWidget(self.peer_list_widget)

        self.delete_btn = QPushButton("REMOVE PEER")
        self.delete_btn.setObjectName("SecondaryBtn")
        self.delete_btn.setStyleSheet(STYLE_BUTTON)
        self.delete_btn.clicked.connect(self.delete_selected_peer)
        side_layout.addWidget(self.delete_btn)
        
        add_btn = QPushButton("+ ADD NEW PEER")
        add_btn.setStyleSheet(STYLE_BUTTON)
        add_btn.clicked.connect(self.add_peer_dialog)
        side_layout.addWidget(add_btn)
        content_row.addWidget(self.sidebar)

        # --- CONFIG AREA ---
        self.right_stack = QStackedWidget()
        empty_msg = QLabel("SELECT A PEER TO CONFIGURE SYNCHRONIZATION")
        empty_msg.setAlignment(Qt.AlignCenter)
        empty_msg.setStyleSheet(f"color: {COLOR_BORDER}; letter-spacing: 1px;")
        self.right_stack.addWidget(empty_msg)

        self.config_view = QWidget()
        config_layout = QVBoxLayout(self.config_view)
        config_layout.setContentsMargins(30, 30, 30, 30)

        self.peer_title = QLabel("PERMISSIONS")
        self.peer_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLOR_FG}; border: none;")
        config_layout.addWidget(self.peer_title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(15)

        self.project_card = self.create_clean_asset_group("PROJECT REPOSITORIES", "project_container")
        self.scroll_layout.addWidget(self.project_card)

        self.inventory_card = self.create_clean_asset_group("INVENTORY DATASETS", "inventory_container")
        self.scroll_layout.addWidget(self.inventory_card)

        scroll.setWidget(scroll_content)
        config_layout.addWidget(scroll)

        # MANUAL IP ENTRY
        self.manual_ip_input = QLineEdit()
        self.manual_ip_input.setPlaceholderText("TARGET IP (OPTIONAL)")
        self.manual_ip_input.setStyleSheet(STYLE_INPUT)
        config_layout.addWidget(self.manual_ip_input)

        # PROGRESS BAR
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {COLOR_BORDER}; border-radius: 2px; text-align: center; color: {COLOR_FG}; height: 10px; font-size: 8px; }}
            QProgressBar::chunk {{ background-color: {COLOR_ACCENT}; }}
        """)
        self.progress_bar.hide()
        config_layout.addWidget(self.progress_bar)

        self.save_btn = QPushButton("INITIALIZE HANDSHAKE")
        self.save_btn.setStyleSheet(STYLE_BUTTON)
        self.save_btn.setFixedHeight(50)
        self.save_btn.clicked.connect(self.initiate_handshake)
        config_layout.addWidget(self.save_btn)

        self.right_stack.addWidget(self.config_view)
        content_row.addWidget(self.right_stack)
        main_layout.addLayout(content_row)

    def reveal_ip(self):
        ip = self.network.get_public_ip()
        self.my_ip_display.setText(ip)
        self.my_ip_display.setStyleSheet(f"color: {COLOR_ACCENT}; border: none; background: transparent; font-weight: bold;")

    def initiate_handshake(self):
        current_item = self.peer_list_widget.currentItem()
        if not current_item: return
        
        alias = current_item.text()
        peers = load_peers(self.username, self.fernet)
        peer_data = peers.get(alias)
        peer_gid = peer_data["ghost_id"]
        recipient_sync_hex = peer_data.get("public_key")

        target_ip = self.manual_ip_input.text().strip()
        if not target_ip:
            target_ip = self.network.discovered_peers.get(peer_gid)

        if not target_ip:
            err_diag = ghost_alert(self, "OFFLINE", "PEER NOT FOUND ON NETWORK. PLEASE ENTER A MANUAL IP.")
            if err_diag:
                err_diag.setStyleSheet("QWidget, QLabel { background: transparent; border: none; }")
                err_diag.exec()
            return

        self.progress_bar.show()
        self.progress_bar.setValue(0)
        
        def run_sync_thread():
            files_to_send = []
            # Gather Project files
            for i in range(self.project_container.count()):
                cb = self.project_container.itemAt(i).widget()
                if isinstance(cb, QCheckBox) and cb.isChecked():
                    file_name = f"{cb.text().replace(' ', '_')}.enc"
                    file_path = os.path.join(EVERYTHING_ELSE, "projects", self.username, file_name)
                    if os.path.exists(file_path):
                        files_to_send.append(file_path)

            for path in files_to_send:
                self.network.send_file(target_ip, path, recipient_sync_hex, 
                                     progress_callback=self.update_progress_safe)
            
            self.progress_bar.hide()

        threading.Thread(target=run_sync_thread, daemon=True).start()

    def update_progress_safe(self, value):
        self.progress_bar.setValue(value)

    def add_peer_dialog(self):
        # 1. Define a transparency fix for labels and inputs inside the popup
        popup_fix = "QLabel, QLineEdit { background: transparent; border: none; }"

        # Using custom TacticalDialog for input
        name_diag = TacticalDialog(self, "AUTHORIZE PEER", "ALIAS:", "e.g. RYAN_LAPTOP")
        name_diag.setStyleSheet(popup_fix) # Apply the fix locally
        
        if name_diag.exec() == QDialog.Accepted:
            alias = name_diag.get_value()
            
            id_diag = TacticalDialog(self, "AUTHORIZE PEER", "GHOST ID:", "NODE ADDRESS...")
            id_diag.setStyleSheet(popup_fix) # Apply the fix locally
            
            if id_diag.exec() == QDialog.Accepted:
                gid = id_diag.get_value()
                
                key_diag = TacticalDialog(self, "AUTHORIZE PEER", "SYNC HEX:", "X25519 PUBLIC KEY...")
                key_diag.setStyleSheet(popup_fix) # Apply the fix locally
                
                if key_diag.exec() == QDialog.Accepted:
                    key = key_diag.get_value()
                    
                    if alias and gid and key:
                        save_peer(self.username, alias, gid, key, self.fernet)
                        self.refresh_peer_list()

    def refresh_peer_list(self):
        self.peer_list_widget.clear()
        peers = load_peers(self.username, self.fernet)
        for alias in peers.keys():
            self.peer_list_widget.addItem(QListWidgetItem(alias))

    def create_clean_asset_group(self, title, container_name):
        group_widget = QWidget()
        layout = QVBoxLayout(group_widget)
        header_row = QHBoxLayout()
        header_label = QLabel(title)
        header_label.setStyleSheet(f"font-weight: bold; color: {COLOR_PROTOCOL}; font-size: 11px;")
        select_all = QPushButton("SELECT ALL")
        select_all.setFlat(True)
        select_all.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 11px; text-decoration: underline; border: none;")
        header_row.addWidget(header_label); header_row.addStretch(); header_row.addWidget(select_all)
        layout.addLayout(header_row)
        container = QVBoxLayout(); layout.addLayout(container)
        setattr(self, container_name, container)
        select_all.clicked.connect(lambda: self.toggle_selection(container))
        return group_widget

    def toggle_selection(self, container):
        if container.count() == 0: return
        state = not container.itemAt(0).widget().isChecked()
        for i in range(container.count()):
            cb = container.itemAt(i).widget()
            if isinstance(cb, QCheckBox): cb.setChecked(state)

    def populate_assets(self, container, subfolder, filter_ext=False):
        while container.count():
            item = container.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        path = os.path.join(EVERYTHING_ELSE, subfolder, self.username)
        if not os.path.exists(path): return
        for item in os.listdir(path):
            if filter_ext and not item.endswith(('.enc', '.csv', '.json')): continue
            cb = QCheckBox(item)
            cb.setStyleSheet(f"""
                QCheckBox {{ padding: 12px; border: 1px solid {COLOR_BORDER}; border-radius: 6px; background: {COLOR_BG}; color: {COLOR_FG}; margin-bottom: 2px; }}
                QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {COLOR_ACCENT}; border-radius: 4px; }}
                QCheckBox::indicator:checked {{ background-color: {COLOR_ACCENT}; }}
            """)
            container.addWidget(cb)

    def display_peer_details(self, index):
        if index == -1:
            self.right_stack.setCurrentIndex(0)
            return
        self.right_stack.setCurrentIndex(1)
        self.peer_title.setText(f"CONFIGURING: {self.peer_list_widget.currentItem().text().upper()}")
        self.populate_assets(self.project_container, "projects")
        self.populate_assets(self.inventory_container, "inventory", filter_ext=True)

    def delete_selected_peer(self):
        current = self.peer_list_widget.currentItem()
        if current:
            # 1. Create the dialog
            dialog = TacticalDialog(self, "DELETE PEER", f"PERMANENTLY REMOVE {current.text()}?")
            dialog.input_field.hide()
            dialog.confirm_btn.setText("TERMINATE")
            
            # 2. LOCAL FIX: We target the background color directly 
            # This bypasses the need for the 'T' variable entirely
            current_style = dialog.container.styleSheet()
            # We know the background-color is set in TacticalDialog's __init__
            # We just force it to transparent for this one specific popup
            dialog.container.setStyleSheet(current_style + "; background-color: transparent;")
            
            # Set the "Terminate" button to red
            dialog.confirm_btn.setStyleSheet(dialog.confirm_btn.styleSheet().replace("#ffb000", "#ff4444"))

            if dialog.exec() == QDialog.Accepted:
                if delete_peer(self.username, current.text(), self.fernet):
                    self.refresh_peer_list()
                    self.right_stack.setCurrentIndex(0)

    def copy_id(self):
        QApplication.clipboard().setText(self.ghost_id)