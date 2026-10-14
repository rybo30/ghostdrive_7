# [my_drive_page.py]

import os
import tempfile
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QGridLayout, QScrollArea, QMenu, QPushButton, QFileDialog, QInputDialog,
    QLineEdit, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap, QImage, QPainter, QPainterPath
from .style_config import T, STYLE_BUTTON, COLOR_ACCENT, ghost_prompt, ghost_alert, STYLE_SCROLLBAR

class MyDrivePage(QWidget):
    def __init__(self, engine, manifest):
        super().__init__()
        self.engine = engine
        self.manifest = manifest
        self.current_folder = None 
        self.search_query = ""
        
        self.folder_layout = None
        self.grid = None
        
        self.setAcceptDrops(True)
        self.init_ui()
        self.refresh_folders()
        self.refresh_grid()

    def init_ui(self):
        # Main Layout: Deep padding for that "contained" look
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(35, 30, 35, 35)
        self.layout.setSpacing(25)

        # --- 1. TACTICAL HEADER ---
        self.header = QHBoxLayout()
        
        # Interactive Breadcrumb
        self.breadcrumb_frame = QFrame()
        self.breadcrumb_frame.setStyleSheet(f"background: rgba(255,255,255,0.03); border-radius: 10px; padding: 5px 15px;")
        b_layout = QHBoxLayout(self.breadcrumb_frame)
        b_layout.setContentsMargins(10, 5, 10, 5)
        
        self.path_label = QLabel("VAULT ACCESS // ROOT")
        self.path_label.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 11px; font-weight: 900; letter-spacing: 2px;")
        b_layout.addWidget(self.path_label)
        
        # Search Bar with "Neon Focus"
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("SEARCH VAULT...")
        self.search_bar.setFixedWidth(280)
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0d1117;
                border: 1px solid #161b22;
                border-radius: 20px;
                color: {COLOR_ACCENT};
                padding: 10px 18px;
                font-family: 'Consolas'; font-size: 11px;
            }}
            QLineEdit:focus {{ border: 1px solid {COLOR_ACCENT}; background: #121d2f; }}
        """)
        self.search_bar.textChanged.connect(self.update_search)
        
        self.upload_btn = QPushButton("UPLOAD ")
        self.upload_btn.setFixedSize(120, 42)
        self.upload_btn.setCursor(Qt.PointingHandCursor)
        self.upload_btn.setStyleSheet(STYLE_BUTTON) 
        self.upload_btn.clicked.connect(self.open_upload_dialog)

        self.header.addWidget(self.breadcrumb_frame)
        self.header.addStretch()
        self.header.addWidget(self.search_bar)
        self.header.addSpacing(15)
        self.header.addWidget(self.upload_btn)
        self.layout.addLayout(self.header)

        # --- 2. FOLDER HUD ---
        folder_header = QHBoxLayout()
        folder_header.addWidget(QLabel("DIRECTORY TREE", 
            styleSheet=f"color: {T['TEXT_DIM']}; font-size: 10px; font-weight: 900; letter-spacing: 3px;"))
        folder_header.addStretch()
        self.layout.addLayout(folder_header)

        self.folder_scroll = QScrollArea()
        self.folder_scroll.setWidgetResizable(True)
        self.folder_scroll.setFixedHeight(140)
        self.folder_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            {STYLE_SCROLLBAR}
        """)
        self.folder_scroll.viewport().setStyleSheet("background: transparent;")
        self.folder_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.folder_container = QWidget()
        self.folder_container.setAttribute(Qt.WA_TranslucentBackground)
        self.folder_container.setStyleSheet("background: transparent; border: none;")
        
        self.folder_layout = QHBoxLayout(self.folder_container)
        self.folder_layout.setContentsMargins(0, 0, 25, 0)
        self.folder_layout.setSpacing(18)
        self.folder_layout.setAlignment(Qt.AlignLeft)

        self.folder_scroll.setWidget(self.folder_container)
        self.layout.addWidget(self.folder_scroll)

        # --- 3. FILE GRID ---
        self.section_title = QLabel("GLOBAL RECENT")
        self.section_title.setStyleSheet(f"color: white; font-size: 13px; font-weight: 900; letter-spacing: 1px; border-bottom: 1px solid #161b22; padding-bottom: 8px;")
        self.layout.addWidget(self.section_title)

        self.file_scroll = QScrollArea()
        self.file_scroll.setWidgetResizable(True)
        self.file_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.file_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            {STYLE_SCROLLBAR}
        """)
        self.file_scroll.viewport().setStyleSheet("background: transparent;")

        self.grid_widget = QWidget()
        self.grid_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.grid_widget.setStyleSheet("background: transparent; border: none;")
        
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setContentsMargins(0, 0, 10, 0) 
        self.grid.setSpacing(20)
        self.grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.file_scroll.setWidget(self.grid_widget)
        self.layout.addWidget(self.file_scroll)

    def check_and_sync_manifest(self):
        """Forces runtime manifest instances to read fresh data if holding empty tracking arrays."""
        if hasattr(self.manifest, "_load") and (not self.manifest.get_files() or self.manifest.username == "default"):
            self.manifest._load()

    def create_folder_card(self, folder_name):
        card = QFrame()
        card.setObjectName("FolderCard")
        card.setFixedSize(200, 100)
        card.setCursor(Qt.PointingHandCursor)
        card.setContextMenuPolicy(Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos: self.show_folder_context_menu(pos, folder_name, card))

        is_active = (folder_name == self.current_folder)
        accent = COLOR_ACCENT if is_active else "#161b22"
        bg = "#121d2f" if is_active else "transparent"

        card.setStyleSheet(f"""
            QFrame#FolderCard {{ 
                background-color: {bg}; 
                border: 1px solid {accent}; 
                border-radius: 12px; 
            }}
            QFrame#FolderCard:hover {{ 
                border: 1px solid {COLOR_ACCENT}; 
                background: #121d2f; 
            }}
        """)

        if is_active:
            glow = QGraphicsDropShadowEffect()
            glow.setBlurRadius(15)
            glow.setColor(QColor(COLOR_ACCENT))
            glow.setOffset(0)
            card.setGraphicsEffect(glow)

        l = QVBoxLayout(card)
        l.setContentsMargins(15, 12, 15, 12)
        
        icon_row = QHBoxLayout()
        icon = QLabel("📁")
        icon.setStyleSheet("font-size: 20px; border: none; background: transparent;")
        
        status_light = QFrame()
        status_light.setFixedSize(6, 6)
        status_light.setStyleSheet(f"background: {COLOR_ACCENT}; border-radius: 3px;")
        
        icon_row.addWidget(icon)
        icon_row.addStretch()
        if is_active: icon_row.addWidget(status_light)
        l.addLayout(icon_row)

        name = QLabel(folder_name.upper())
        name.setStyleSheet(f"font-weight: 900; color: white; font-size: 11px; letter-spacing: 1px; border: none; background: transparent;")
        l.addWidget(name)
        
        count = len([f for f in self.manifest.get_files() if f.get('folder') == folder_name])
        meta = QLabel(f"FOLDER: {count} OBJECTS")
        meta.setStyleSheet(f"color: {T['TEXT_DIM']}; font-size: 8px; font-weight: 700; border: none; background: transparent;")
        l.addWidget(meta)

        def handle_folder_click(event):
            if event.button() == Qt.LeftButton:
                self.filter_by_folder(folder_name)

        card.mousePressEvent = handle_folder_click
        return card

    def show_folder_context_menu(self, pos, folder_name, card):
        menu = QMenu(self)
        GOLD = T['PROTOCOL_GOLD'] 
        menu.setStyleSheet(f"""
            QMenu {{ 
                background-color: {T['PROTOCOL_BG']}; 
                color: {GOLD}; 
                border: 1px solid {GOLD}; 
                font-family: 'Consolas'; font-size: 10px;
            }} 
            QMenu::item {{ padding: 8px 25px; }}
            QMenu::item:selected {{ background: rgba(255, 176, 0, 0.2); color: white; }}
        """)
        menu.addAction("🗑️ DELETE FOLDER").triggered.connect(lambda: self.delete_folder(folder_name))
        menu.exec(card.mapToGlobal(pos))

    def delete_folder(self, folder_name):
        title = "FOLDER DECOMMISSION // REQUEST"
        msg = f"DELETE FOLDER: {folder_name.upper()}?\n"
        
        if ghost_alert(self, title, msg):
            for file_info in self.manifest.get_files():
                if file_info.get('folder') == folder_name:
                    self.manifest.update_file_folder(file_info['id'], "Recent Files")
            
            self.manifest.remove_folder(folder_name)
            if self.current_folder == folder_name:
                self.current_folder = None
                
            self.refresh_folders()
            self.refresh_grid()

    def get_image_preview(self, info):
        try:
            img_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
            if info.get('type', '').lower() not in img_exts:
                return None

            raw_data = self.engine.decrypt_file_to_memory(info['id'])
            image = QImage.fromData(raw_data)
            if image.isNull():
                return None
                
            target_size = QSize(146, 80)
            scaled_pix = QPixmap.fromImage(image).scaled(
                target_size, 
                Qt.KeepAspectRatioByExpanding, 
                Qt.SmoothTransformation
            )

            rounded_pix = QPixmap(target_size)
            rounded_pix.fill(Qt.transparent)
            
            painter = QPainter(rounded_pix)
            painter.setRenderHint(QPainter.Antialiasing)
            
            path = QPainterPath()
            path.addRoundedRect(0, 0, target_size.width(), target_size.height(), 10, 10)
            painter.setClipPath(path)
            
            x = (target_size.width() - scaled_pix.width()) / 2
            y = (target_size.height() - scaled_pix.height()) / 2
            painter.drawPixmap(x, y, scaled_pix)
            painter.end()
            
            return rounded_pix
        except Exception as e:
            print(f"Preview Error: {e}")
            return None

    def create_file_card(self, info):
        card = QFrame()
        card.setObjectName("FileCard")
        card.setFixedSize(170, 180)
        card.setContextMenuPolicy(Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos: self.show_context_menu(pos, info, card))
        
        ext = info.get('type', '').lower()
        img_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        vid_exts = ['.mp4', '.mov', '.avi', '.mkv']
        pdf_exts = ['.pdf']
        
        if ext in pdf_exts:
            type_color = "#ff4444"
        elif ext in vid_exts:
            type_color = "#bf91ff"
        elif ext in img_exts:
            type_color = COLOR_ACCENT
        else:
            type_color = T['PROTOCOL_GOLD']
            
        card.setStyleSheet(f"""
            QFrame#FileCard {{ 
                background-color: #0d1117; 
                border: 1px solid #161b22; 
                border-radius: 12px; 
            }}
            QFrame#FileCard:hover {{ 
                border: 1px solid {type_color}; 
                background: rgba(255, 255, 255, 0.02); 
            }}
        """)
        
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 12, 12, 12)

        preview = QLabel()
        preview.setFixedSize(146, 80)
        preview.setAlignment(Qt.AlignCenter)
        preview.setStyleSheet(f"background: #080a0d; border: 1px solid rgba(255,255,255,0.03); border-radius: 10px;")
        
        pixmap = self.get_image_preview(info)
        if pixmap:
            preview.setPixmap(pixmap)
        else:
            emoji = "📕" if ext in pdf_exts else "🎬" if ext in vid_exts else "🖼️" if ext in img_exts else "📄"
            preview.setText(emoji)
            preview.setStyleSheet(f"font-size: 32px; color: {type_color}; background: #080a0d; border-radius: 10px;")

        l.addWidget(preview)

        name = QLabel()
        metrics = name.fontMetrics()
        elided_name = metrics.elidedText(info['name'], Qt.ElideRight, 140)
        name.setText(elided_name)
        name.setStyleSheet("color: white; font-weight: 800; font-size: 10px; margin-top: 5px; border: none; background: transparent;")
        l.addWidget(name)
        
        size_mb = info.get('size', 0) / (1024*1024)
        l.addStretch()
        
        meta_row = QHBoxLayout()
        size_label = QLabel(f"{size_mb:.1f} MB")
        size_label.setStyleSheet(f"color: {T['TEXT_DIM']}; font-size: 9px; font-weight: 700; border: none; background: transparent;")
        
        type_tag = QLabel(ext.replace('.','').upper())
        type_tag.setStyleSheet(f"""
            color: {type_color}; 
            font-size: 8px; 
            font-weight: 900; 
            border: 1px solid {type_color}; 
            padding: 1px 4px; 
            border-radius: 4px; 
            background: rgba({QColor(type_color).red()}, {QColor(type_color).green()}, {QColor(type_color).blue()}, 20);
        """)
        
        meta_row.addWidget(size_label)
        meta_row.addStretch()
        meta_row.addWidget(type_tag)
        l.addLayout(meta_row)

        bar = QFrame()
        bar.setFixedHeight(2)
        bar.setStyleSheet(f"background: {type_color}; border-radius: 1px;")
        l.addWidget(bar)

        return card

    def update_search(self, text):
        self.search_query = text.lower().strip()
        self.refresh_grid()

    def refresh_folders(self):
        if not self.folder_layout: return
        self.check_and_sync_manifest()
        
        while self.folder_layout.count():
            item = self.folder_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        new_btn = QFrame()
        new_btn.setFixedSize(80, 100)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setStyleSheet("QFrame { border: 2px dashed #161b22; border-radius: 12px; } QFrame:hover { border: 2px dashed #555; }")
        nl = QVBoxLayout(new_btn)
        n_lbl = QLabel("＋\nNEW")
        n_lbl.setAlignment(Qt.AlignCenter)
        n_lbl.setStyleSheet("color: #555; font-weight: 900; font-size: 10px;")
        nl.addWidget(n_lbl)
        new_btn.mousePressEvent = lambda e: self.add_new_virtual_folder()
        self.folder_layout.addWidget(new_btn)

        for folder in self.manifest.get_folders():
            self.folder_layout.addWidget(self.create_folder_card(folder))
        self.folder_layout.addStretch()

    def refresh_grid(self):
        if not self.grid: return
        self.check_and_sync_manifest()
        
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        all_files = self.manifest.get_files()
        target_folder = self.current_folder if self.current_folder else "Recent Files"
        
        if self.search_query:
            filtered = [f for f in all_files if self.search_query in f.get('name', '').lower()]
            self.section_title.setText(f"SEARCH RESULTS: {self.search_query.upper()}")
        else:
            filtered = [f for f in all_files if f.get('folder') == target_folder]
            display_name = self.current_folder if self.current_folder else "ROOT"
            self.section_title.setText(f"SCANNING FOLDER: {display_name.upper()}")

        self.path_label.setText(f"VAULT ACCESS // { (self.current_folder or 'ROOT').upper() }")

        cols = 4 
        for idx, info in enumerate(filtered):
            row = idx // cols
            col = idx % cols
            card = self.create_file_card(info)
            self.grid.addWidget(card, row, col)
            
        if len(filtered) > 0:
            self.grid.setColumnStretch(cols, 1)
        else:
            self.grid.setColumnStretch(0, 1)

    def filter_by_folder(self, name):
        self.current_folder = name if name != self.current_folder else None
        self.search_bar.clear()
        self.refresh_folders()
        self.refresh_grid()

    def open_upload_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*.*)")
        if files:
            for f in files: self.process_file(f)
            self.refresh_grid()
            self.refresh_folders()

    def process_file(self, file_path):
        target = self.current_folder if self.current_folder else "Recent Files"
        if os.path.isfile(file_path):
            try:
                # Direct check step right before injection
                if hasattr(self.manifest, "_load"):
                    self.manifest._load()
                fid, size = self.engine.encrypt_file(file_path)
                self.manifest.add_entry(os.path.basename(file_path), fid, size, os.path.splitext(file_path)[1], target)
            except Exception as e: 
                print(e)

    def view_file(self, info):
        try:
            data = self.engine.decrypt_file_to_memory(info['id'])
            temp_path = os.path.join(tempfile.gettempdir(), info['name'])
            with open(temp_path, "wb") as f: f.write(data)
            os.startfile(temp_path) if os.name == 'nt' else subprocess.call(["open", temp_path])
        except Exception as e: print(e)

    def decrypt_file(self, info):
        path, _ = QFileDialog.getSaveFileName(self, "Download File", info['name'])
        if path:
            with open(path, "wb") as f: f.write(self.engine.decrypt_file_to_memory(info['id']))

    def delete_file(self, info):
        title = "SECURE ERASE // REQUEST"
        msg = f"DESTROY OBJECT: {info['name']}?"
        
        if ghost_alert(self, title, msg):
            self.manifest.remove_entry(info['id'])
            self.refresh_grid()
            self.refresh_folders()

    def add_new_virtual_folder(self):
        name, ok = ghost_prompt(
            self, 
            title="FILESYSTEM // NEW FOLDER", 
            label="ENTER FOLDER DESIGNATION:"
        )
        
        if ok and name.strip():
            self.manifest.add_folder(name.strip())
            self.refresh_folders()

    def show_context_menu(self, pos, info, card):
        menu = QMenu(self)
        GOLD = T['PROTOCOL_GOLD'] 
        menu.setStyleSheet(f"""
            QMenu {{ 
                background-color: {T['PROTOCOL_BG']}; 
                color: {GOLD}; 
                border: 1px solid {GOLD}; 
                font-family: 'Consolas'; font-size: 10px;
            }} 
            QMenu::item {{ padding: 8px 25px; }}
            QMenu::item:selected {{ background: rgba(255, 176, 0, 0.2); color: white; }}
            QMenu::separator {{ height: 1px; background: rgba(255, 176, 0, 0.3); margin: 4px 10px; }}
        """)

        menu.addAction("👁️ VIEW").triggered.connect(lambda: self.view_file(info))
        menu.addAction("📥 DOWNLOAD").triggered.connect(lambda: self.decrypt_file(info))
        
        move_menu = menu.addMenu("📁 REASSIGN FOLDER")
        root_action = move_menu.addAction("ROOT (RECENT)")
        root_action.triggered.connect(lambda: self.move_file_to_folder(info, "Recent Files"))
        move_menu.addSeparator()

        for folder_name in self.manifest.get_folders():
            if folder_name != info.get('folder'):
                action = move_menu.addAction(folder_name.upper())
                action.triggered.connect(lambda checked=False, f=folder_name: self.move_file_to_folder(info, f))
        
        menu.addSeparator()
        menu.addAction("🗑️ DELETE").triggered.connect(lambda: self.delete_file(info))
        menu.exec(card.mapToGlobal(pos))

    def move_file_to_folder(self, info, new_folder_name):
        """Updates the manifest and refreshes the UI grid."""
        try:
            self.manifest.update_file_folder(info['id'], new_folder_name)
            self.refresh_grid()
            self.refresh_folders()
        except Exception as e:
            print(f"Transfer Error: {e}")

    def dragEnterEvent(self, e): e.accept() if e.mimeData().hasUrls() else e.ignore()
    def dropEvent(self, e):
        for url in e.mimeData().urls(): self.process_file(url.toLocalFile())
        self.refresh_grid()
        self.refresh_folders()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_grid()