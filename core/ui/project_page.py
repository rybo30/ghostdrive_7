# [project_page.py]


import os
import tempfile
import subprocess
import platform

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QGridLayout, QScrollArea, QPushButton, 
    QProgressBar, QComboBox, QLineEdit, QFormLayout, QDialog, QSizePolicy, QPlainTextEdit
)
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtCore import Qt, QMimeData
from .style_config import (
    T, COLOR_ACCENT, COLOR_BORDER, STYLE_HUD_VAL, FONT_MAIN, STYLE_HUD_LBL,
    ghost_prompt, ghost_alert, STYLE_INPUT, TacticalDialog, STYLE_SCROLLBAR
)
from core.Everything_else.manifest_manager import ManifestManager
from core.Everything_else.encryption_engine import GhostEngine
from core.Everything_else.project_engine import ProjectEngine
from core.paths import USER_DATA


class TaskCard(QFrame):
    def __init__(self, task_data, goal_id, goal_title, all_goals, select_callback, edit_callback, delete_callback, move_callback):
        super().__init__()
        self.task_id = task_data['id']
        self.task_text = task_data['text']
        self.current_goal_id = goal_id
        self.goal_title = goal_title
        self.all_goals = all_goals 
        
        self.callback = select_callback
        self.edit_callback = edit_callback
        self.delete_callback = delete_callback
        self.move_callback = move_callback

        self.setFixedWidth(185)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)

        # --- TOP BAR (Tag/Dropdown on Left, Red X on Right) ---
        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar_layout.setSpacing(5)

        # Left: Swappable Container
        self.tag_container = QWidget()
        self.tag_sub_layout = QVBoxLayout(self.tag_container)
        self.tag_sub_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_sub_layout.setSpacing(0)

        self.goal_tag = QLabel(self.goal_title.upper())
        self.goal_tag.setFixedHeight(16)
        self.goal_tag.setStyleSheet(f"""
            color: {T.get('PROTOCOL_GOLD', '#ffd700')}; 
            font-size: 8px; font-weight: bold; letter-spacing: 1px;
            background: transparent; border: 1px solid {T.get('PROTOCOL_GOLD', '#ffd700')};
            border-radius: 2px; padding: 1px 4px;
        """)

        self.goal_selector = QComboBox()
        self.goal_selector.setFixedHeight(20)
        self.goal_selector.setStyleSheet(f"""
            background: {T.get('BG_DEEP', '#0a0a0a')}; 
            color: {T.get('PROTOCOL_GOLD', '#ffd700')}; 
            font-size: 8px; font-weight: bold; border: 1px solid {T.get('PROTOCOL_GOLD', '#ffd700')};
        """)
        for g_id, g_title in self.all_goals:
            self.goal_selector.addItem(g_title.upper(), g_id)
        
        idx = self.goal_selector.findData(self.current_goal_id)
        self.goal_selector.setCurrentIndex(idx)
        self.goal_selector.currentIndexChanged.connect(self.on_goal_dropdown_changed)
        self.goal_selector.hide()

        self.tag_sub_layout.addWidget(self.goal_tag)
        self.tag_sub_layout.addWidget(self.goal_selector)

        # Right: Red X Button
        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(18, 18)
        self.del_btn.hide() 
        self.del_btn.setStyleSheet("color: #ff4444; background: transparent; font-weight: bold; border: none;")
        self.del_btn.clicked.connect(lambda: self.delete_callback(self.task_id))

        self.top_bar_layout.addWidget(self.tag_container, 0, Qt.AlignLeft)
        self.top_bar_layout.addStretch()
        self.top_bar_layout.addWidget(self.del_btn, 0, Qt.AlignRight)
        
        self.layout.addLayout(self.top_bar_layout)

        # --- TEXT CONTENT AREA (Label hides, Editor shows) ---
        self.label = QLabel(self.task_text.upper())
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self.label.setStyleSheet(f"color: {T.get('TEXT_FG', '#e0e0e0')}; font-size: 11px; font-weight: 500; border: none;")
        self.layout.addWidget(self.label)

        self.editor = QPlainTextEdit(self.task_text.upper())
        self.editor.setMinimumHeight(60) 
        self.editor.setMaximumHeight(300) 
        self.editor.setStyleSheet(STYLE_INPUT + "font-size: 11px; padding: 5px;")
        self.editor.textChanged.connect(self.adjust_editor_height)
        self.editor.hide()
        self.layout.addWidget(self.editor)

        # --- ASSET INTEL TAG ---
        self.meta_container = QWidget()
        self.meta_layout = QHBoxLayout(self.meta_container)
        self.meta_layout.setContentsMargins(0, 0, 0, 0)
        
        assets = task_data.get('assets', [])
        if assets:
            self.meta = QLabel(f"INTEL: {len(assets)} OBJECTS")
            self.meta.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 8px; font-weight: bold; border: none;")
            self.meta_layout.addWidget(self.meta)
            self.meta_layout.addStretch()
            self.meta_container.show()
        else:
            self.meta_container.hide()
        
        self.layout.addWidget(self.meta_container)


    def minimumSizeHint(self):
        """Calculates the minimum height based on internal layout requirements."""
        # This forces the layout to respect the space taken by the text and tags
        return self.layout.sizeHint()


    def update_style(self, selected=False):
        """Updates the card's border and background based on selection state."""
        if selected:
            # Highlight style for a selected task
            self.setStyleSheet(f"""
                TaskCard {{
                    background: rgba(88, 166, 255, 0.1);
                    border: 1px solid {COLOR_ACCENT};
                    border-radius: 6px;
                }}
            """)
        else:
            # Standard tactical style
            self.setStyleSheet(f"""
                TaskCard {{
                    background: {T.get('BG_PANEL', '#1a1a1a')};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 6px;
                }}
                TaskCard:hover {{
                    border: 1px solid {COLOR_ACCENT};
                    background: rgba(255, 255, 255, 0.05);
                }}
            """)

    def on_goal_dropdown_changed(self):
        """Triggered when the user selects a new goal from the dropdown."""
        if self.goal_selector.isVisible():
            new_goal_id = self.goal_selector.currentData()
            if new_goal_id != self.current_goal_id:
                self.finish_edit()

    def enterEvent(self, event):
        # REMOVED: self.del_btn.show() 
        # Only the hover style from update_style will trigger now
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Only hide if we aren't currently in the middle of an edit
        if self.label.isVisible():
            self.del_btn.hide()
        super().leaveEvent(event)

    def adjust_editor_height(self):
        """Dynamically grows the editor height while editing."""
        doc_height = self.editor.document().size().height()
        # Allow more breathing room for long text
        new_height = max(70, min(doc_height + 20, 400)) 
        self.editor.setFixedHeight(int(new_height))
        # Forces the card to re-evaluate its layout
        self.adjustSize() 
        self.updateGeometry()

    def mouseDoubleClickEvent(self, event):
        from PySide6.QtGui import QTextCursor # Ensure this is available

        self.label.hide()
        self.goal_tag.hide()
    
        self.del_btn.show()
        self.editor.show()
        self.goal_selector.show() 
    
        self.adjust_editor_height()
        self.editor.setFocus()
        
        cursor = self.editor.textCursor()
        # FIX: Point directly to the scoped Enum namespace in PySide6
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.updateGeometry()

    def finish_edit(self):
        """Persists changes and collapses the card."""
        new_text = self.editor.toPlainText().strip()
        new_goal_id = self.goal_selector.currentData()

        if new_text and new_text != self.task_text:
            self.task_text = new_text
            self.label.setText(new_text.upper())
            self.edit_callback(self.task_id, new_text)
        
        if new_goal_id != self.current_goal_id:
            self.move_callback(self.task_id, new_goal_id)

        self.editor.hide()
        self.goal_selector.hide() 
        self.del_btn.hide()
    
        self.label.show()
        self.goal_tag.show()      
        self.adjustSize()
        self.updateGeometry()

    def keyPressEvent(self, event):
        """Restores the 'Enter to Save' workflow."""
        if self.editor.isVisible() and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.finish_edit()
            event.accept()
            return
            
        if event.key() == Qt.Key_Escape:
            self.editor.setPlainText(self.task_text.upper())
            self.finish_edit()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Handle selection to update asset tray and visual style."""
        # 1. Trigger the callback to update the 'Operational Briefing' and 'Asset Tray'
        self.callback(self.task_id)
        
        # 2. Update style (you might need a way to deselect others, 
        # but this will at least highlight this one)
        self.update_style(True)
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Starts the drag operation if the left mouse button is held and moved."""
        if event.buttons() != Qt.LeftButton:
            return
            
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.task_id) # The task ID is the payload
        drag.setMimeData(mime)
        
        # Create a ghost image of the card for the drag icon
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        
        drag.exec(Qt.MoveAction)

class StatusColumn(QFrame):
    def __init__(self, status_key, label_text, color, parent_page):
        super().__init__()
        self.status_key = status_key
        self.parent_page = parent_page
        self.setFixedWidth(215)
        # Use a more robust border styling to prevent visual glitches on resize
        self.setStyleSheet(f"""
            StatusColumn {{
                background: rgba(0, 0, 0, 0.1); 
                border: 1px solid {COLOR_BORDER}; 
                border-radius: 8px;
            }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5) # Added slight breathing room
        
        # Header
        header = QLabel(label_text)
        header.setStyleSheet(f"color: {color}; font-weight: 900; letter-spacing: 2px; padding: 10px; border: none;")
        header.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(header)

        # Drop Zone (Top)
        self.top_drop = DropLabel(label_text, status_key, color, None, parent_page)
        self.layout.addWidget(self.top_drop)

        # Scroll Area for tasks
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent; 
                border: none;
            }}
            {STYLE_SCROLLBAR}
        """)
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.container)
        
        # FIX 1: Strict alignment to top prevents the layout from 
        # distributing "extra space" between your cards (the squish).
        self.content_layout.setAlignment(Qt.AlignTop) 
        self.content_layout.setSpacing(12) # Fixed gap between cards
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)
        
        self.setAcceptDrops(True)

    def clear_tasks(self):
        """Clears widgets but keeps the layout structure."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            # If it's a spacer/stretch, we don't need to delete it, 
            # but we'll re-add it in add_task_card logic if needed.

    def add_task_card(self, card):
        """Adds a card and ensures exactly ONE stretch exists at the bottom."""
        # 1. Remove all existing spacers first
        for i in reversed(range(self.content_layout.count())):
            item = self.content_layout.itemAt(i)
            if item.spacerItem():
                self.content_layout.removeItem(item)
    
        # 2. Add the card
        self.content_layout.addWidget(card)
    
        # 3. Add a single stretch to push everything to the top
        self.content_layout.addStretch(1)

    def remove_stretch(self):
        """Helper to find and remove the stretch item so new cards can be added."""
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            if item.spacerItem():
                self.content_layout.removeItem(item)
                break

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        task_id = event.mimeData().text()
        if self.parent_page.proj_engine.update_task_status(task_id, self.status_key):
            self.parent_page.refresh_ui()
        event.acceptProposedAction()


class GoalSwimlane(QFrame):
    def __init__(self, goal_data, engine, all_goals, select_callback, edit_callback, delete_callback, move_callback): 
        super().__init__()
        
        goal_title = goal_data.get('title', 'UNTITLED GOAL')
        tasks = goal_data.get('tasks', [])

        self.setStyleSheet("margin-bottom: 20px; border-bottom: 1px solid rgba(88, 166, 255, 0.1);")
        layout = QVBoxLayout(self)
        
        title = QLabel(f"GOAL: {goal_title.upper()}")
        title.setStyleSheet(f"color: {T['TEXT_DIM']}; font-size: 10px; font-weight: 900; letter-spacing: 2px;")
        layout.addWidget(title)
        
        col_layout = QHBoxLayout()
        self.cols = {}

        for key, label_text in [("not_done", "READY"), ("in_progress", "ACTIVE"), ("done", "SECURED")]:
            column_container = QWidget()
            column_container.setFixedWidth(225) # The "Master" width
    
            v_box = QVBoxLayout(column_container) # Set layout directly to the container
            v_box.setAlignment(Qt.AlignTop)
            v_box.setContentsMargins(5, 5, 5, 5)
    
            sub_head = QLabel(label_text)
            sub_head.setStyleSheet("color: rgba(255,255,255,0.2); font-size: 8px;")
            v_box.addWidget(sub_head)
    
            # Add the widget to the layout, not just the layout
            col_layout.addWidget(column_container) 
            self.cols[key] = v_box
            
        layout.addLayout(col_layout)

        for task in tasks:
            if isinstance(task, dict) and 'id' in task:
                # Correctly passing all 8 required arguments to TaskCard
                card = TaskCard(
                    task, 
                    goal_id=goal_data.get('goal_id'), 
                    goal_title=goal_title,
                    all_goals=all_goals, 
                    select_callback=select_callback,
                    edit_callback=edit_callback,
                    delete_callback=delete_callback,
                    move_callback=move_callback
                )
                status = task.get('status', 'not_done')
                if status in self.cols: 
                    self.cols[status].addWidget(card)

        for key in self.cols:
            self.cols[key].addStretch(1)

class DropLabel(QLabel):
    def __init__(self, text, status_key, color, goal_id, parent_page):
        super().__init__("")
        self.status_key = status_key
        self.goal_id = goal_id
        self.parent_page = parent_page
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        
        # Store the styles to toggle them
        self.active_style = f"color: {color}; font-size: 9px; font-weight: bold; border: 1px dashed {COLOR_ACCENT}; background: rgba(88, 166, 255, 0.1); padding: 8px; margin-top: 5px;"
        
        # Start invisible and tiny so it takes up no space in the layout
        self.set_inactive()

    def set_inactive(self):
        self.setStyleSheet("background: transparent; border: none; margin: 0; padding: 0;")
        self.setFixedHeight(1) 

    def set_active(self):
        self.setStyleSheet(self.active_style)
        self.setFixedHeight(35) # Give it enough height to be a visible drop target

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self.set_active()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.set_inactive()

    def dropEvent(self, event):
        task_id = event.mimeData().text()
        
        # Logic remains exactly as you had it
        if self.goal_id:
            self.parent_page.proj_engine.change_task_goal(task_id, self.goal_id)
            
        if self.parent_page.proj_engine.update_task_status(task_id, self.status_key):
            self.parent_page.refresh_ui()
            
        event.acceptProposedAction()
        self.set_inactive()


class DocumentLinkDialog(TacticalDialog):
    def __init__(self, manifest, parent=None):
        # 1. Initialize parent (creates the frame, header, and buttons)
        super().__init__(parent, title="LINK PROJECT INTEL", label="SELECT VAULT FILE:")
        
        # 2. HIDE the default input field from TacticalDialog (we want a ComboBox instead)
        self.input_field.hide()
        
        # 3. Reference the existing layout in the container
        layout = self.container.layout() 
        
        # 4. Setup the ComboBox
        files = manifest.get_files()
        self.combo = QComboBox()
        # Ensure the dropdown also matches the gold protocol style
        self.combo.setStyleSheet(f"""
            QComboBox {{ 
                background: #000000; 
                color: {T['PROTOCOL_GOLD']}; 
                border: 1px solid {T['HUD_LINE']}; 
                border-radius: 4px; 
                padding: 10px; 
            }}
            QComboBox QAbstractItemView {{
                background-color: #000000;
                color: {T['PROTOCOL_GOLD']};
                selection-background-color: {T['HUD_LINE']};
            }}
        """)
        
        if not files:
            layout.insertWidget(3, QLabel("NO FILES FOUND IN VAULT"))
            self.combo = None
        else:
            for f in files:
                self.combo.addItem(f"{f['type'].upper()} | {f['name']}", f['id'])
            
            # Insert the combo box into the layout before the buttons
            # We use insertWidget(3, ...) because: 
            # 0=Header, 1=Line, 2=Label, 3=Input(Hidden)
            layout.insertWidget(3, self.combo)

        # 5. Connect the EXISTING confirm button from TacticalDialog
        # This removes the need for a separate "ADD TO PROJECT" button
        self.confirm_btn.setText("LINK ASSET")
        
    def get_id(self):
        return self.combo.currentData() if self.combo else None


class ProjectsPage(QWidget):
    def __init__(self, username, passphrase, fernet):
        super().__init__()
        self.username = username
        self.fernet = fernet
        self.engine = GhostEngine(fernet)
        self.manifest = ManifestManager(self.engine, username)
        self.proj_engine = ProjectEngine(username, fernet, self.manifest)
        
        self.selected_task_id = None

        self.init_ui()

    def init_ui(self):
        # 1. Initialize the master scroll
        self.master_scroll = QScrollArea(self)
        self.master_scroll.setWidgetResizable(True)
        
        self.master_scroll.setStyleSheet(f"""
            QScrollArea {{ 
                background-color: {T.get('BG_DEEP', '#0d1117')}; 
                border: none; 
            }}
            {STYLE_SCROLLBAR}
        """)
    
        self.container = QWidget()
        self.container.setStyleSheet(f"background-color: {T.get('BG_DEEP', '#0d1117')};")
        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(30, 20, 30, 30)
        self.main_layout.setSpacing(15)

        # 2. Setup scroll area for the board
        self.board_scroll = QScrollArea()
        self.board_scroll.setWidgetResizable(True)
        self.board_scroll.setMinimumHeight(500) 
        
        self.board_scroll.viewport().setStyleSheet("background: transparent;")
        self.board_scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }} 
            {STYLE_SCROLLBAR}
        """)

        # 3. Call setup functions
        self.setup_mission_control()
        self.setup_briefing_zone()
        self.setup_scrum_board() 
        self.main_layout.addWidget(self.board_scroll)
        self.setup_asset_tray()
    
        # 4. Finalize the widget hierarchy
        self.master_scroll.setWidget(self.container)
    
        final_layout = QVBoxLayout(self)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(self.master_scroll)

        self.refresh_project_list()

    def setup_mission_control(self):
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet(f"background: rgba(255,255,255,0.03); border: none; border-radius: 8px;")
        layout = QHBoxLayout(ctrl_frame)
        layout.setContentsMargins(15, 10, 15, 10) # Optional: adds a little breathing room inside the frame

        self.project_dropdown = QComboBox()
        self.project_dropdown.setFixedWidth(250)
        self.project_dropdown.setStyleSheet(f"background: {T['BG_DEEP']}; color: {COLOR_ACCENT}; padding: 5px;")
        self.project_dropdown.currentIndexChanged.connect(self.on_project_changed)
        
        new_btn = QPushButton("+ NEW PROJECT")
        new_btn.setStyleSheet(f"background: {COLOR_ACCENT}; color: {T['BG_DEEP']}; font-weight: bold; padding: 6px 15px;")
        new_btn.clicked.connect(self.create_new_mission_dialog)

        goal_btn = QPushButton("EDIT PROJECT")
        goal_btn.setStyleSheet(f"background: transparent; color: {T['PROTOCOL_GOLD']}; border: 1px solid {T['PROTOCOL_GOLD']}; font-weight: bold; padding: 6px 15px;")
        goal_btn.clicked.connect(self.edit_mission_dialog)

        # --- REORDERED LAYOUT (LEFT TO RIGHT) ---
        
        # 1. New Mission Button
        layout.addWidget(new_btn)
        
        # 2. Edit Mission Button
        layout.addWidget(goal_btn)

        layout.addStretch()
        
        # 4. Active Missions Label (STYLING UPDATED)
        active_lbl = QLabel("ACTIVE PROJECTS:")
        active_lbl.setStyleSheet("background: transparent; color: white; font-weight: bold; border: none;")
        layout.addWidget(active_lbl, 0, Qt.AlignRight)
        layout.addWidget(self.project_dropdown)

        self.main_layout.addWidget(ctrl_frame)

    def setup_briefing_zone(self):
        self.briefing_frame = QFrame()
        self.briefing_frame.setStyleSheet(f"background: {T['BG_CARD']}; border: none; border-radius: 10px;")

        layout = QGridLayout(self.briefing_frame)
        layout.setContentsMargins(25, 25, 25, 25) 
        layout.setSpacing(10)

        # --- Title & Edit Button Row ---
        self.proj_title = QLabel("NO ACTIVE PROJECTS")
        self.proj_title.setStyleSheet(f"background: transparent; color: {T['PROTOCOL_GOLD']}; font-weight: bold; font-size: 22px; letter-spacing: 1px;")
    
        # --- Progress & Deadline ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6) # Slightly thinner for a sleeker look
        self.progress_bar.setTextVisible(False)
        
        # Clean, borderless style
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ 
                background: rgba(255, 255, 255, 0.08); 
                border-radius: 3px; 
                border: none; 
            }}
            QProgressBar::chunk {{ 
                background: {COLOR_ACCENT}; 
                border-radius: 3px; 
            }}
        """)
    
        self.deadline_lbl = QLabel("DEADLINE: N/A")
        self.deadline_lbl.setStyleSheet(f"color: {COLOR_ACCENT}; font-family: 'Consolas'; font-size: 11px; font-weight: bold;")

        # --- Description ---
        self.proj_desc = QLabel("Initialize a project to begin tracking objectives.")
        self.proj_desc.setStyleSheet(f"background: none; color: {T['TEXT_DIM']}; font-size: 14px; line-height: 1.5; margin-top: 5px;")
        self.proj_desc.setWordWrap(True)
        self.proj_desc.setMinimumHeight(40) 

        # --- Layout Placement ---
        layout.addWidget(self.proj_title, 0, 0, Qt.AlignLeft)
        layout.addWidget(self.progress_bar, 0, 1)
        layout.addWidget(self.proj_desc, 1, 0, 1, 2) 
        layout.addWidget(self.deadline_lbl, 2, 1, Qt.AlignRight)

        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 1)

        # INITIAL STATE HIDING
        if not self.proj_engine.active_project:
            self.progress_bar.hide()
            self.deadline_lbl.hide()

        self.main_layout.addWidget(self.briefing_frame)


    def refresh_project_list(self):
        from core.Everything_else.project_manager import list_project_files
        
        self.project_dropdown.blockSignals(True)
        self.project_dropdown.clear()
        
        # 1. Add the mandatory placeholder
        self.project_dropdown.addItem("SELECT ACTIVE PROJECT...", None)
        
        # 2. Fetch the list of encrypted filenames
        files = list_project_files(self.username)
        
        if files:
            for filename in files:
                # Get the human-readable mission title for the UI
                display_name = self.proj_engine.get_project_title(filename)
                
                # Store the actual filename in the 'data' role so we can load it later
                self.project_dropdown.addItem(display_name.upper(), filename)
        
        self.project_dropdown.blockSignals(False)

    def on_project_changed(self, index):
        # Retrieve the hidden filename (userData)
        filename = self.project_dropdown.currentData()
        
        # 1. Reset selection state immediately so we don't try to 
        # highlight a task that doesn't exist in the new mission.
        self.selected_task_id = None
        
        # 2. Load or Clear
        if filename:
            self.proj_engine.load_project(filename)
        else:
            # Tell the engine there is no active project
            self.proj_engine.active_project = None
            
        # 3. Centralized Refresh (this handles visibility/clearing for us)
        self.refresh_ui()

    def create_new_mission_dialog(self):
        # Pass 'self' as the first argument to these calls
        title, ok = ghost_prompt(self, "NEW PROJECT", "Enter Project Title:")
        if not ok or not title: return
        
        desc, ok = ghost_prompt(self, "PROJECT BRIEF", "Enter Short Description:")
        if not ok: return
        
        deadline, ok = ghost_prompt(self, "DEADLINE", "Enter Target Date (YYYY-MM-DD):")
        if not ok: return

        if self.proj_engine.create_project(title, desc, deadline):
            self.refresh_project_list()
            # Select by the encrypted filename stored in data
            internal_id = self.proj_engine.active_project['internal_id']
            idx = self.project_dropdown.findData(internal_id)
            if idx != -1:
                self.project_dropdown.setCurrentIndex(idx)


    def setup_scrum_board(self):
        """Creates the horizontal 3-column layout with a task entry area at the top."""
        self.board_container = QWidget()
        # The master layout for the board area is vertical: [Input Area] then [Columns]
        self.master_board_layout = QVBoxLayout(self.board_container)
        self.master_board_layout.setContentsMargins(0, 0, 0, 0)
        self.master_board_layout.setSpacing(15)

        # 1. NEW TASK INPUT AREA (Added at the top)
        self.input_frame = QFrame()
        self.input_frame.setStyleSheet(f"background: rgba(255,255,255,0.02); border-radius: 6px;")
        input_layout = QHBoxLayout(self.input_frame)
        
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("ADD NEW TASK...")
        self.task_input.setStyleSheet(STYLE_INPUT)
        self.task_input.returnPressed.connect(self.quick_add_task)
        
        add_btn = QPushButton("ADD")
        add_btn.setFixedWidth(80)
        add_btn.setStyleSheet(f"background: {COLOR_ACCENT}; color: {T['BG_DEEP']}; font-weight: bold;")
        add_btn.clicked.connect(self.quick_add_task)
        
        input_layout.addWidget(self.task_input)
        input_layout.addWidget(add_btn)
        self.master_board_layout.addWidget(self.input_frame)

        # 2. THE COLUMNS (Horizontal Layout)
        self.column_container = QWidget()
        self.board_layout = QHBoxLayout(self.column_container)
        self.board_layout.setSpacing(20)
        self.board_layout.setContentsMargins(0, 0, 0, 0)
        
        self.column_widgets = {}
        statuses = [
            ("not_done", "READY", T['TEXT_DIM']),
            ("in_progress", "ACTIVE", COLOR_ACCENT),
            ("done", "SECURED", T['PROTOCOL_GOLD'])
        ]
        
        for key, label, color in statuses:
            col = StatusColumn(key, label, color, self)
            self.column_widgets[key] = col
            self.board_layout.addWidget(col)
            
        self.master_board_layout.addWidget(self.column_container)
        self.board_scroll.setWidget(self.board_container)

    def quick_add_task(self):
        """Adds a task to the first goal of the project by default."""
        text = self.task_input.text().strip()
        if not text or not self.proj_engine.active_project:
            return
            
        # Get the first goal ID to attach the task to
        goals = self.proj_engine.active_project.get('goals', [])
        if not goals:
            # Create a default goal if none exists
            self.proj_engine.add_goal("GENERAL OBJECTIVES")
            goals = self.proj_engine.active_project.get('goals', [])
            
        target_goal_id = goals[0].get('goal_id')
        
        # 1. Capture the new ID (instead of just checking if True)
        new_task_id = self.proj_engine.add_task(target_goal_id, text)
        
        if new_task_id:
            self.task_input.clear()
            
            # 2. Refresh the board so the new TaskCard widget is actually created
            self.refresh_ui() 
            
            # 3. Auto-select the newly created task
            # This triggers the gold highlight and updates the Intel tray/sidebar
            self.on_task_selected(new_task_id)

    def refresh_ui(self):
        proj = self.proj_engine.active_project
        
        # 1. Handle the "No Project" state
        if not proj:
            self.proj_title.setText("NO ACTIVE PROJECTS")
            self.proj_desc.setText("Initialize a project to begin tracking objectives.")
            self.deadline_lbl.setText("DEADLINE: N/A")
            self.progress_bar.setValue(0)
            
            # --- HIDE STATS WHEN INACTIVE ---
            self.progress_bar.hide()
            self.deadline_lbl.hide()
            
            # Clear columns and tray
            for col in self.column_widgets.values():
                col.clear_tasks()
            self.refresh_asset_tray() 
            return

        # 2. Update Mission Header
        # --- SHOW STATS WHEN ACTIVE ---
        self.progress_bar.show()
        self.deadline_lbl.show()

        self.proj_title.setText(f"PROJECT: {proj.get('title', 'UNTITLED').upper()}")
        self.proj_desc.setText(proj.get('description', ''))
        self.deadline_lbl.setText(f"DEADLINE: {proj.get('deadline', 'N/A')}")
        
        # Safety: Ensure the progress calculation doesn't crash if goals are missing
        completion = self.proj_engine.get_completion_percentage()
        self.progress_bar.setValue(completion if completion is not None else 0)

        # 3. Clear existing task cards from columns
        for col in self.column_widgets.values():
            col.clear_tasks()

        # 4. Prepare Goal List for TaskCard dropdowns
        all_goals = [(g['goal_id'], g['title']) for g in proj.get('goals', []) if isinstance(g, dict)]

        # 5. Populate Scrum Board Tasks
        for goal in proj.get('goals', []):
            if not isinstance(goal, dict): continue
    
            g_title = goal.get('title') # This will now be the UPDATED title
            g_id = goal.get('goal_id')
            tasks = goal.get('tasks', [])
        
            for task in tasks:
                card = TaskCard(
                    task, 
                    g_id,
                    g_title, 
                    all_goals, 
                    self.on_task_selected, 
                    self.on_task_edited, 
                    delete_callback=self.on_task_deleted,
                    move_callback=self.on_task_moved_goal 
                )
                
                # Check if this task is the one currently selected to maintain the gold highlight
                if task.get('id') == self.selected_task_id:
                    card.update_style(selected=True)

                status = task.get('status', 'not_done')
                if status in self.column_widgets:
                    self.column_widgets[status].add_task_card(card)

        # 6. Populate the Global Document Tray
        self.refresh_asset_tray()
        self.update_mission_hud()


    def update_mission_hud(self):
        """Updates the HUD progress based on task completion."""
        if not self.proj_engine.active_project:
            return

        # Use the engine's built-in percentage logic to stay consistent
        percentage = self.proj_engine.get_completion_percentage()

        # Update the widget that actually exists in your class
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(percentage)
    
        # If you want a text label and it's named something else (like self.status_lbl), 
        # update that here instead.

    def refresh_intel_tray(self):
        # Clear existing items
        for i in reversed(range(self.intel_layout.count())):
            widget = self.intel_layout.itemAt(i).widget()
            if widget: widget.deleteLater()

        # 1. Add the Add Button
        add_btn = QPushButton("+")
        add_btn.setFixedSize(80, 80)
        add_btn.setStyleSheet(f"border: 2px dashed {T['TEXT_DIM']}; color: {T['TEXT_DIM']}; font-size: 24px; border-radius: 8px;")
        add_btn.clicked.connect(self.link_new_document)
        self.intel_layout.addWidget(add_btn)

        # 2. Add Linked Documents
        docs = self.proj_engine.get_project_documents()
        for doc in docs:
            card = QFrame()
            card.setFixedSize(180, 80)
            card.setStyleSheet(f"background: {T['BG_CARD']}; border: 1px solid {COLOR_BORDER}; border-radius: 8px;")
            v = QVBoxLayout(card)
            
            type_lbl = QLabel(doc['type'].upper())
            type_lbl.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 9px; font-weight: bold;")
            
            name_lbl = QLabel(doc['name'])
            name_lbl.setStyleSheet(f"color: {T['TEXT_MAIN']}; font-size: 12px;")
            name_lbl.setWordWrap(True)
            
            v.addWidget(type_lbl)
            v.addWidget(name_lbl)
            self.intel_layout.addWidget(card)

    def link_new_document(self):
        """Standard vault picker for project shortcuts."""
        # We call our custom class, NOT ghost_prompt
        dialog = DocumentLinkDialog(self.manifest, self)
        
        if dialog.exec():
            file_id = dialog.get_id()
            if file_id:
                # This saves the ID to the project JSON via project_engine.py
                if self.proj_engine.link_document_to_project(file_id):
                    self.refresh_asset_tray()


    def setup_asset_tray(self):
        # 1. Header for the section
        self.intel_label = QLabel("PROJECT INTELLIGENCE / QUICK LINKS")
        self.intel_label.setStyleSheet(f"color: {T['TEXT_DIM']}; font-size: 10px; font-weight: bold; margin-top: 15px;")
        self.main_layout.addWidget(self.intel_label)

        # 2. The Scroll Area
        self.asset_scroll = QScrollArea()
        self.asset_scroll.setWidgetResizable(True)
        self.asset_scroll.setFixedHeight(130)
        
        # Ensure horizontal bar is enabled and vertical is disabled
        self.asset_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.asset_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Apply the master scrollbar style
        self.asset_scroll.setStyleSheet(f"""
            QScrollArea {{ 
                background: transparent; 
                border: none; 
            }} 
            {STYLE_SCROLLBAR}
        """)
        
        self.asset_container = QWidget()
        self.asset_container.setStyleSheet("background: transparent;")
        self.asset_layout = QHBoxLayout(self.asset_container)
        self.asset_layout.setContentsMargins(0, 10, 0, 10)
        self.asset_layout.setSpacing(15)
        self.asset_layout.setAlignment(Qt.AlignLeft)
        
        self.asset_scroll.setWidget(self.asset_container)
        self.main_layout.addWidget(self.asset_scroll)

    def refresh_asset_tray(self):
        """Clears and repopulates the bottom Mission Intelligence tray."""
        for i in reversed(range(self.asset_layout.count())):
            item = self.asset_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()

        # 1. Add the '+' Add Button
        add_btn = QPushButton("+")
        add_btn.setFixedSize(80, 80)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                border: 2px dashed {T['TEXT_DIM']}; 
                color: {T['TEXT_DIM']}; 
                font-size: 24px; 
                border-radius: 8px;
                background: transparent;
            }}
            QPushButton:hover {{
                border-color: {COLOR_ACCENT};
                color: {COLOR_ACCENT};
                background: rgba(255, 255, 255, 0.05);
            }}
        """)
        add_btn.clicked.connect(self.link_new_document)
        
        # FIX: Changed from self.intel_layout to self.asset_layout
        self.asset_layout.addWidget(add_btn)

        # 2. Add Linked Documents
        docs = self.proj_engine.get_project_documents()
        for doc in docs:
            card = self.create_intel_card(doc)
            # FIX: Changed from self.intel_layout to self.asset_layout
            self.asset_layout.addWidget(card)
            
        # FIX: Changed from self.intel_layout to self.asset_layout
        self.asset_layout.addStretch()

    def create_intel_card(self, doc):
        """Creates a card that matches the MyDrivePage 'Object' style."""
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor

        card = QFrame()
        card.setFixedSize(200, 90)
        card.setCursor(Qt.PointingHandCursor)
        card.setObjectName("IntelCard")
        
        # 1. Apply MyDrive-style styling
        card.setStyleSheet(f"""
            #IntelCard {{
                background: {T['BG_CARD']}; 
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
            }}
            #IntelCard:hover {{
                background: {T['BG_HOVER']};
                border: 1px solid {COLOR_ACCENT};
            }}
        """)

        # 2. Add the Shadow Effect (Standard in MyDrive)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 100))
        card.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 12, 12, 12)
        layout.setSpacing(5)
        
        # --- Header (Type + Close) ---
        header = QHBoxLayout()
        
        type_lbl = QLabel(doc.get('type', 'DATA').upper())
        type_lbl.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-family: 'Consolas'; 
            font-size: 9px; 
            font-weight: bold; 
            letter-spacing: 1.5px;
            background: transparent;
        """)
        
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                color: {T['TEXT_DIM']};
                border: none;
                font-size: 16px;
                background: transparent;
            }}
            QPushButton:hover {{
                color: {T['DANGER']};
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
            }}
        """)
        remove_btn.clicked.connect(lambda: self.unlink_document(doc['id']))
        
        header.addWidget(type_lbl)
        header.addStretch()
        header.addWidget(remove_btn)
        
        # --- Name (The Primary Object Title) ---
        name_lbl = QLabel(doc.get('name', 'Unknown Object'))
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(f"""
            color: {T['TEXT_MAIN']}; 
            font-family: '{FONT_MAIN}';
            font-size: 12px; 
            font-weight: bold;
            background: transparent;
        """)
        
        layout.addLayout(header)
        layout.addWidget(name_lbl)
        layout.addStretch()
        
        # Click handler to open the physical file
        card.mousePressEvent = lambda event: self.open_project_asset(doc)
        
        return card

    def open_project_asset(self, file_info):
        import os
        import tempfile
        import platform
        import subprocess
        # Import USER_DATA here if not imported at the top
        from core.paths import USER_DATA 

        try:
            file_id = file_info.get('id')
            if not file_id:
                raise ValueError("Document record is missing its ID.")

            # Ensure we have the .dat extension
            if not file_id.endswith('.dat'):
                file_id += '.dat'
                
            # Use the global USER_DATA path from paths.py
            encrypted_path = os.path.join(USER_DATA, file_id)

            if not os.path.exists(encrypted_path):
                raise FileNotFoundError(f"Vault source missing: {file_id}")

            # Read and Decrypt
            with open(encrypted_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt using the fernet instance stored in self
            decrypted_bytes = self.fernet.decrypt(encrypted_data)

            # Write to a temporary file for the OS to open
            temp_path = os.path.join(tempfile.gettempdir(), file_info['name'])
            
            with open(temp_path, 'wb') as f:
                f.write(decrypted_bytes)

            # System Execution
            if platform.system() == 'Windows':
                os.startfile(temp_path)
            elif platform.system() == 'Darwin':
                subprocess.call(['open', temp_path])
            else:
                subprocess.call(['xdg-open', temp_path])

        except Exception as e:
            ghost_alert(self, "VAULT ERROR", f"COULD NOT OPEN ASSET: {str(e)}")

    def unlink_document(self, file_id):
        """Removes the link between this project and a vault file."""
        if self.proj_engine.unlink_document_from_project(file_id):
            self.refresh_asset_tray()

    def open_vault_file(self, doc):
        """Requests the main application to open/view the vault asset."""
        file_id = doc.get('id')
        
        # This is the bridge to your actual file opening logic.
        # Usually, this signal is caught by the main window controller.
        if hasattr(self, 'parent') and hasattr(self.parent(), 'open_vault_file'):
            self.parent().open_vault_file(file_id)
        else:
            # Fallback: Print that we need to connect the viewer
            print("SYSTEM: Document link detected, but no global viewer is connected to ProjectsPage.")


    def on_task_moved_goal(self, task_id, new_goal_id):
        """Callback for when a user changes a task's goal via the dropdown."""
        # This assumes your ProjectEngine has a method to change the goal
        if self.proj_engine.change_task_goal(task_id, new_goal_id):
            self.refresh_ui()

    def on_task_deleted(self, task_id):
        """Removes the task from the engine and refreshes the UI."""
        # Ensure your ProjectEngine has a delete_task(task_id) method
        if self.proj_engine.delete_task(task_id):
            # If the deleted task was the one being viewed, clear the asset tray
            self.refresh_ui()
            for i in reversed(range(self.asset_layout.count())):
                item = self.asset_layout.itemAt(i)
                if item.widget(): item.widget().deleteLater()

    def on_task_selected(self, task_id):
        """Highlights the card and populates the Asset Tray."""
        # Save the ID for persistence across refreshes
        self.selected_task_id = task_id 
        
        # 1. Update visual selection (Highlighting cards)
        for col in self.column_widgets.values():
            for i in range(col.content_layout.count()):
                widget = col.content_layout.itemAt(i).widget()
                if isinstance(widget, TaskCard):
                    widget.update_style(selected=(widget.task_id == task_id))

        # 2. Clear and Repopulate the Task Intel
        for i in reversed(range(self.asset_layout.count())): 
            item = self.asset_layout.itemAt(i)
            if item.widget(): item.widget().deleteLater()
        
        assets = self.proj_engine.get_resolved_assets(task_id)
        for asset in assets:
            card = self.create_intel_card(asset)
            self.asset_layout.addWidget(card)
            
        self.asset_layout.addStretch()


    def add_goal_dialog(self):
        """Opens a prompt to add a new goal column to the current mission."""
        if not self.proj_engine.active_project: return
        
        goal_title, ok = ghost_prompt(self, "STRATEGIC OBJECTIVE", "Enter Goal Title:")
        if ok and goal_title:
            if self.proj_engine.add_goal(goal_title):
                self.refresh_ui()

    def edit_mission_dialog(self):
        """Opens prompts to edit the current mission's title, description, and deadline."""
        proj = self.proj_engine.active_project
        if not proj: return

        # Get Title
        new_title, ok = ghost_prompt(self, "EDIT TITLE", "Update PROJECT Title:", initial_text=proj.get('title'))
        if not ok: return
        
        # Get Description
        new_desc, ok = ghost_prompt(self, "EDIT BRIEF", "Update Short Description:", initial_text=proj.get('description'))
        if not ok: return
        
        # Get Deadline
        new_date, ok = ghost_prompt(self, "EDIT DEADLINE", "Update Target Date (YYYY-MM-DD):", initial_text=proj.get('deadline'))
        if not ok: return

        # Save and Refresh
        if self.proj_engine.update_project_details(new_title, new_desc, new_date):
            self.refresh_ui()
            self.refresh_project_list()


    def show_mission_config_dialog(self, is_new=False):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor

        title_str = "NEW PROJECT CONFIGURATION" if is_new else "PROJECT RE-CONFIGURATION"
        data = self.proj_engine.active_project if not is_new else {"title": "", "description": "", "deadline": "", "goals": []}
    
        if not data and not is_new: 
            return

        # 1. Initialize Dialog
        dialog = TacticalDialog(self, title=title_str, label="PROJECT PARAMETERS")
        
        # Elegant glass/dark container with drop shadow
        dialog.container.setStyleSheet(f"""
            QFrame#ProtocolBox {{ 
                background-color: {T.get('BG_DEEP', '#0d1117')}; 
                border: 1px solid {COLOR_ACCENT}; 
                border-radius: 12px; 
            }}
        """)

        # Add a soft neon glow around the outer frame
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(COLOR_ACCENT))
        shadow.setOffset(0, 0)
        dialog.container.setGraphicsEffect(shadow)
    
        if hasattr(dialog, 'input_field'):
            dialog.input_field.hide() 

        # --- Setup Data Tracking ---
        vgoal_inputs = []

        # 2. Form Container Layout
        form_container = QWidget()
        form_container.setStyleSheet("background: transparent;")
        form_layout = QFormLayout(form_container)
        form_layout.setSpacing(14)
        form_layout.setContentsMargins(18, 12, 18, 12)

        LABEL_STYLE = f"color: {T.get('TEXT_DIM', '#8b949e')}; font-family: '{FONT_MAIN}'; font-size: 10px; font-weight: 700; letter-spacing: 1px;"

        # Stylish accent-bordered inputs
        CLEAN_INPUT_STYLE = f"""
            QLineEdit {{
                background-color: {T.get('BG_CARD', '#161b22')};
                color: {T.get('TEXT_MAIN', '#c9d1d9')};
                border: 1px solid {COLOR_BORDER};
                border-left: 3px solid {T.get('TEXT_DIM', '#484f58')};
                border-radius: 6px;
                padding: 8px 12px;
                font-family: '{FONT_MAIN}';
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_ACCENT};
                border-left: 3px solid {COLOR_ACCENT};
                background-color: rgba(88, 166, 255, 0.03);
            }}
        """

        # Section Header Helper
        def create_section_header(title):
            lbl = QLabel(title.upper())
            lbl.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; margin-top: 5px;")
            return lbl

        form_layout.addRow(create_section_header("Project Details"), None)

        # Main Inputs
        name_input = QLineEdit(data.get('title', ''))
        name_input.setStyleSheet(CLEAN_INPUT_STYLE)
        desc_input = QLineEdit(data.get('description', ''))
        desc_input.setStyleSheet(CLEAN_INPUT_STYLE)
        date_input = QLineEdit(data.get('deadline', ''))
        date_input.setStyleSheet(CLEAN_INPUT_STYLE)

        def make_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(LABEL_STYLE)
            return lbl

        form_layout.addRow(make_label("NAME:"), name_input)
        form_layout.addRow(make_label("BRIEFING:"), desc_input)
        form_layout.addRow(make_label("DEADLINE:"), date_input)

        # Separator line before Objectives
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {COLOR_BORDER}; margin: 8px 0;")
        form_layout.addRow(sep)

        form_layout.addRow(create_section_header("Strategic Objectives"), None)

        # Goals Section
        goal_container = QWidget()
        goal_container.setStyleSheet("background: transparent;")
        goal_vbox = QVBoxLayout(goal_container)
        goal_vbox.setContentsMargins(0, 0, 0, 0)
        goal_vbox.setSpacing(8)
        
        def add_goal_row(text=""):
            row = QHBoxLayout()
            row.setSpacing(8)
            
            inp = QLineEdit(text)
            inp.setStyleSheet(CLEAN_INPUT_STYLE)
            vgoal_inputs.append(inp)
            
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(28, 28)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton {
                    color: #ff5555; 
                    border: 1px solid rgba(255, 85, 85, 0.3); 
                    background: rgba(255, 85, 85, 0.05);
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(255, 85, 85, 0.25);
                    border-color: #ff5555;
                    color: #ffffff;
                }
            """)
            
            def remove_row():
                if inp in vgoal_inputs:
                    vgoal_inputs.remove(inp)
                inp.deleteLater()
                del_btn.deleteLater()
            
            del_btn.clicked.connect(remove_row)
            row.addWidget(inp)
            row.addWidget(del_btn)
            goal_vbox.addLayout(row)

        for g in data.get('goals', []):
            add_goal_row(g.get('title', ''))

        add_goal_btn = QPushButton("+ ADD STRATEGIC OBJECTIVE")
        add_goal_btn.setCursor(Qt.PointingHandCursor)
        add_goal_btn.setStyleSheet(f"""
            QPushButton {{
                color: {COLOR_ACCENT}; 
                border: 1px dashed {COLOR_ACCENT}; 
                background: rgba(88, 166, 255, 0.04);
                padding: 9px; 
                border-radius: 6px;
                font-family: '{FONT_MAIN}';
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                margin-top: 4px;
            }}
            QPushButton:hover {{
                background: rgba(88, 166, 255, 0.15);
                border: 1px solid {COLOR_ACCENT};
            }}
        """)
        add_goal_btn.clicked.connect(lambda: add_goal_row())

        form_layout.addRow(goal_container)
        form_layout.addRow(add_goal_btn)

        # Destructive Option
        if not is_new:
            line_del = QFrame()
            line_del.setFrameShape(QFrame.HLine)
            line_del.setStyleSheet(f"background-color: {COLOR_BORDER}; margin: 12px 0 6px 0;")
            form_layout.addRow(line_del)

            btn_delete = QPushButton("TERMINATE ENTIRE PROJECT")
            btn_delete.setCursor(Qt.PointingHandCursor)
            btn_delete.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 68, 68, 0.08);
                    color: #ff5555;
                    border: 1px solid rgba(255, 68, 68, 0.35);
                    border-radius: 6px;
                    padding: 10px;
                    font-weight: 800;
                    letter-spacing: 1px;
                }
                QPushButton:hover {
                    background-color: #ff4444;
                    color: #ffffff;
                    border-color: #ff4444;
                }
            """)
            btn_delete.clicked.connect(lambda: self.confirm_mission_deletion(dialog))
            form_layout.addRow(btn_delete)

        # 3. Wrap in Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(form_container)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            {STYLE_SCROLLBAR}
        """)

        dialog.container.layout().insertWidget(1, scroll_area)
        
        # 4. Sizing
        dialog.setMinimumWidth(520)
        dialog.setMinimumHeight(420)
        dialog.setMaximumHeight(620)
        dialog.resize(540, 540)
    
        if dialog.exec():
            new_goals = [inp.text().strip() for inp in vgoal_inputs if inp.text().strip()]
        
            if is_new:
                if self.proj_engine.create_project(name_input.text(), desc_input.text(), date_input.text()):
                    for g_title in new_goals:
                        self.proj_engine.add_goal(g_title)
            else:
                self.proj_engine.update_project_details(name_input.text(), desc_input.text(), date_input.text())
                self.proj_engine.sync_goals(new_goals)

            self.refresh_project_list()
            self.refresh_ui()


    def confirm_mission_deletion(self, parent_dialog):
        """Creates a high-stakes confirmation dialog for project deletion."""
        confirm = TacticalDialog(self, title="CONFIRM DESTRUCTION", label="CRITICAL WARNING")
        
        # Hide standard input if it exists
        if hasattr(confirm, 'input_field'):
            confirm.input_field.hide()

        msg = QLabel("ARE YOU ABSOLUTELY SURE?\n\nThis will permanently delete all data associated with this project. This action cannot be reversed.")
        msg.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 14px; padding: 20px;")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        
        confirm.container.layout().insertWidget(1, msg)
        confirm.setMinimumWidth(400)

        if confirm.exec():
            # Call the engine to delete the file
            if self.proj_engine.delete_active_project():
                # Close the edit dialog without saving any other changes
                parent_dialog.reject() 
                # Refresh UI to show the project is gone
                self.refresh_project_list()
                self.refresh_ui()


    def create_new_mission_dialog(self):
        self.show_mission_config_dialog(is_new=True)

    def edit_mission_dialog(self):
        self.show_mission_config_dialog(is_new=False)

    def on_goal_selected(self, goal_id):
        self.selected_goal_id = goal_id
        self.refresh_ui() # Redraws the board to show the gold highlight

    def on_task_edited(self, task_id, new_text):
        if self.proj_engine.update_task_text(task_id, new_text):
            print(f"Task {task_id} updated successfully.")
            # We don't necessarily need a full refresh_ui here 
            # because the TaskCard already updated its own label.