# [inventory_page.py] - Fixed row indexing, bottom appending, and data sync

import os
import sys
import csv
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, QLineEdit,
    QHBoxLayout, QMessageBox, QDialog, QTableWidgetItem, 
    QHeaderView, QLabel, QTabBar, QMenu
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QAction

from core.paths import EVERYTHING_ELSE, INVENTORY_DIR

if EVERYTHING_ELSE not in sys.path:
    sys.path.insert(0, EVERYTHING_ELSE)

from inventory_manager import (
    load_inventory, save_inventory, export_inventory_to_csv, list_inventory_sheets, rename_inventory_file
)

from .style_config import (
    FONT_FAMILY, COLOR_BG, COLOR_FG, COLOR_ACCENT, COLOR_BUTTON, 
    STYLE_BUTTON, COLOR_PAGE_BG, COLOR_BORDER, ghost_prompt, ghost_alert, TacticalDialog
)

class InventoryPage(QWidget):
    def __init__(self, username, passphrase, fernet):
        super().__init__()
        self.username = username
        self.passphrase = passphrase
        self.fernet = fernet
        self.current_sheet_name = "inventory"
        
        self.schema = [] 
        self.data = []
        self._is_refreshing = False 

        # 1. Main Layout & Styling
        self.setStyleSheet(f"background-color: {COLOR_BG}; color: {COLOR_FG}; font-family: '{FONT_FAMILY}';")
        self.layout = QVBoxLayout(self)

        # 2. Top Bar (Search + Encryption Status Pill)
        top_bar_layout = QHBoxLayout()
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search inside current sheet...")
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_BUTTON}; 
                color: {COLOR_FG}; 
                border: 1px solid {COLOR_ACCENT};
                border-radius: 4px;
                padding: 6px;
            }}
        """)
        self.search_bar.textChanged.connect(self.filter_inventory)
        top_bar_layout.addWidget(self.search_bar, stretch=3)

        self.status_pill = QLabel("🔒 Encrypted Vault Synced")
        self.status_pill.setStyleSheet(f"""
            QLabel {{
                background-color: {COLOR_BUTTON};
                color: {COLOR_ACCENT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
        self.status_pill.setAlignment(Qt.AlignCenter)
        top_bar_layout.addWidget(self.status_pill, stretch=1)
        
        self.layout.addLayout(top_bar_layout)

        # 3. Tab Navigation Section
        tab_container = QHBoxLayout()
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.setStyleSheet(f"""
            QTabBar::tab {{
                background: {COLOR_BUTTON};
                color: {COLOR_FG};
                padding: 8px 16px;
                border: 1px solid {COLOR_BORDER};
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {COLOR_ACCENT};
                color: black;
                font-weight: bold;
            }}
        """)
        self.tabs.currentChanged.connect(self.switch_sheet)
        
        self.add_sheet_btn = QPushButton("+")
        self.add_sheet_btn.setFixedWidth(40)
        self.add_sheet_btn.setStyleSheet(STYLE_BUTTON)
        self.add_sheet_btn.clicked.connect(self.create_new_sheet)

        tab_container.addWidget(self.tabs)
        tab_container.addWidget(self.add_sheet_btn)
        tab_container.addStretch()
        self.layout.addLayout(tab_container)

        # 4. Table Setup & Context Menus
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        # Disabled automatic sorting to keep 1-to-1 visual row index matching self.data
        self.table.setSortingEnabled(False)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.AnyKeyPressed)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_PAGE_BG}; 
                color: {COLOR_FG};
                gridline-color: {COLOR_ACCENT};
                border-radius: 4px;
            }}
            QHeaderView::section {{
                background-color: {COLOR_ACCENT};
                color: #000000;  
                border: 1px solid {COLOR_BG};
                font-weight: bold;
                padding: 5px;
            }}
        """)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_header_context_menu)
        
        self.table.itemChanged.connect(self.handle_cell_edited)
        self.layout.addWidget(self.table)

        # 5. Live Summary Footer Bar
        self.summary_bar = QLabel("Total Items: 0 | Metrics Summary: Ready")
        self.summary_bar.setStyleSheet(f"""
            QLabel {{
                background-color: {COLOR_BUTTON};
                color: {COLOR_FG};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }}
        """)
        self.layout.addWidget(self.summary_bar)

        # 6. Action Button Controls
        btn_layout = QHBoxLayout()
        buttons = [
            ("Add Row", self.add_blank_row),
            ("Delete Row", self.delete_row),
            ("Columns", self.edit_columns),
            ("Rename Sheet", self.rename_current_sheet),
            ("Delete Sheet", self.delete_current_sheet),
            ("Export CSV", self.export_csv),
            ("Import CSV", self.import_csv)
        ]
        for label, func in buttons:
            b = QPushButton(label)
            b.setStyleSheet(STYLE_BUTTON)
            b.clicked.connect(func)
            btn_layout.addWidget(b)

        self.layout.addLayout(btn_layout)

        # 7. Initial Load
        self.load_sheet_list(load_default_data=True)

    def load_sheet_list(self, load_default_data=False):
        self.tabs.blockSignals(True)
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
            
        sheets = list_inventory_sheets(self.username)
        for s in sheets:
            self.tabs.addTab(s.replace("_", " ").capitalize())
        
        target_index = 0
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).lower().replace(" ", "_") == self.current_sheet_name:
                target_index = i
                break
        
        self.tabs.setCurrentIndex(target_index)
        self.tabs.blockSignals(False)

        if load_default_data:
            payload = load_inventory(self.username, self.fernet, self.current_sheet_name)
            self.schema = payload.get("schema", ["name", "quantity", "location", "last_checked"])
            self.data = payload.get("data", [])
            self.refresh_table()

    def switch_sheet(self, index):
        if index == -1: 
            return
        
        self.table.clearFocus()
        
        if hasattr(self, 'schema') and self.schema:
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
        
        self.current_sheet_name = self.tabs.tabText(index).lower().replace(" ", "_")
        payload = load_inventory(self.username, self.fernet, self.current_sheet_name)
        
        self.schema = payload.get("schema", ["name", "quantity", "location", "last_checked"])
        self.data = payload.get("data", [])
        self.refresh_table()

    def refresh_table(self):
        self._is_refreshing = True 
        self.table.clear()
        self.table.setColumnCount(len(self.schema))
        self.table.setHorizontalHeaderLabels([col.capitalize().replace("_", " ") for col in self.schema])
        self.table.setRowCount(0)
        
        for row_idx, item in enumerate(self.data):
            self.table.insertRow(row_idx)
            for col_idx, key in enumerate(self.schema):
                value = str(item.get(key, ""))
                cell_item = QTableWidgetItem(value)
                cell_item.setForeground(QColor(COLOR_FG))
                
                if key == "last_checked":
                    cell_item.setFlags(cell_item.flags() & ~Qt.ItemIsEditable)
                    cell_item.setBackground(QColor(COLOR_BUTTON))
                    
                self.table.setItem(row_idx, col_idx, cell_item)
                
        self.table.resizeColumnsToContents()
        self._is_refreshing = False
        self.update_summary_footer()

    def update_summary_footer(self):
        total_rows = len(self.data)
        numeric_sums = {}
        
        for key in self.schema:
            total_sum = 0.0
            is_numeric = True
            for row in self.data:
                val = row.get(key, "")
                try:
                    total_sum += float(val)
                except ValueError:
                    is_numeric = False
                    break
            if is_numeric and total_rows > 0:
                numeric_sums[key] = total_sum

        summary_text = f"Total Rows: {total_rows}"
        for col, val in numeric_sums.items():
            summary_text += f" | {col.capitalize().replace('_', ' ')} Sum: {val:g}"
        
        self.summary_bar.setText(summary_text)

    def handle_cell_edited(self, item):
        if self._is_refreshing:
            return

        row = item.row()
        col = item.column()
        field_key = self.schema[col]

        if row >= len(self.data):
            return

        self.data[row][field_key] = item.text()

        if "last_checked" in self.schema:
            today = datetime.now().strftime("%Y-%m-%d")
            self.data[row]["last_checked"] = today
            
            self._is_refreshing = True
            time_col = self.schema.index("last_checked")
            time_item = self.table.item(row, time_col)
            if time_item:
                time_item.setText(today)
            self._is_refreshing = False

        save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
        self.update_summary_footer()

    def add_blank_row(self):
        self.table.clearFocus()
        
        new_item = {field: "" for field in self.schema}
        if "last_checked" in self.schema:
            new_item["last_checked"] = datetime.now().strftime("%Y-%m-%d")
            
        self.data.append(new_item)
        self.refresh_table()
        
        # Focus user right into the first cell of the new bottom row
        new_row_idx = self.table.rowCount() - 1
        self.table.setCurrentCell(new_row_idx, 0)
        self.table.editItem(self.table.item(new_row_idx, 0))

    def delete_row(self):
        self.table.clearFocus()
        selected_row = self.table.currentRow()
        if selected_row == -1:
            ghost_alert(self, "SYSTEM NOTICE", "No active item selected.")
            return
            
        if ghost_alert(self, "CONFIRM PURGE", "Permanently delete selected row?"):
            del self.data[selected_row]
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
            self.refresh_table()

    def create_new_sheet(self):
        self.table.clearFocus()
        name, ok = ghost_prompt(self, "NEW DATA SHEET", "ASSIGN SHEET NAME:")
        if ok and name.strip():
            sheet_id = name.strip().lower().replace(" ", "_")
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
            
            new_payload = {
                "schema": ["name", "quantity", "location", "last_checked"], 
                "data": []
            }
            save_inventory(self.username, new_payload, self.fernet, sheet_id)
            self.current_sheet_name = sheet_id
            self.load_sheet_list(load_default_data=True)

    def rename_current_sheet(self):
        self.table.clearFocus()
        if self.current_sheet_name == "inventory":
            ghost_alert(self, "ACCESS REJECTED", "Default inventory sheet cannot be renamed.")
            return

        old_name = self.current_sheet_name.replace("_", " ").capitalize()
        new_name, ok = ghost_prompt(self, "RENAME SHEET", "ENTER NEW NAME:", placeholder=old_name)
        
        if ok and new_name.strip():
            new_id = new_name.strip().lower().replace(" ", "_")
            success, error = rename_inventory_file(self.username, self.current_sheet_name, new_id)
            if success:
                self.current_sheet_name = new_id
                self.load_sheet_list(load_default_data=True)
            else:
                ghost_alert(self, "SYSTEM FAULT", f"Rename failed: {error}")

    def delete_current_sheet(self):
        self.table.clearFocus()
        if self.current_sheet_name == "inventory":
            ghost_alert(self, "ACCESS REJECTED", "Cannot delete the default root sheet.")
            return
            
        if not ghost_alert(self, "DELETE SHEET", f"Permanently delete '{self.current_sheet_name}'?"):
            return
            
        from inventory_manager import get_inventory_path
        filepath = get_inventory_path(self.username, self.current_sheet_name)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            self.current_sheet_name = "inventory"
            self.load_sheet_list(load_default_data=True)
        except Exception as e:
            ghost_alert(self, "FATAL ERROR", str(e))

    def show_header_context_menu(self, pos: QPoint):
        self.table.clearFocus()
        col_index = self.table.horizontalHeader().logicalIndexAt(pos)
        menu = QMenu(self)
        
        rename_action = QAction("Rename Column", self)
        add_left_action = QAction("Insert Column Left", self)
        add_right_action = QAction("Insert Column Right", self)
        delete_action = QAction("Delete Column", self)
        
        menu.addAction(rename_action)
        menu.addAction(add_left_action)
        menu.addAction(add_right_action)
        if len(self.schema) > 1:
            menu.addAction(delete_action)
            
        action = menu.exec(self.table.horizontalHeader().mapToGlobal(pos))
        if not action:
            return

        current_key = self.schema[col_index]

        if action == rename_action:
            new_col, ok = ghost_prompt(self, "RENAME COLUMN", "ENTER NEW COLUMN NAME:", placeholder=current_key)
            if ok and new_col.strip():
                new_key = new_col.strip().lower().replace(" ", "_")
                self.schema[col_index] = new_key
                for row in self.data:
                    if current_key in row:
                        row[new_key] = row.pop(current_key)
                save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
                self.refresh_table()

        elif action in (add_left_action, add_right_action):
            col_name, ok = ghost_prompt(self, "NEW COLUMN", "ENTER COLUMN NAME:")
            if ok and col_name.strip():
                new_key = col_name.strip().lower().replace(" ", "_")
                insert_idx = col_index if action == add_left_action else col_index + 1
                self.schema.insert(insert_idx, new_key)
                for row in self.data:
                    row[new_key] = ""
                save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
                self.refresh_table()

        elif action == delete_action:
            if ghost_alert(self, "DELETE COLUMN", f"Remove column '{current_key}' and its data?"):
                self.schema.pop(col_index)
                for row in self.data:
                    row.pop(current_key, None)
                save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
                self.refresh_table()

    def filter_inventory(self, text):
        text = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def edit_columns(self):
        self.table.clearFocus()
        current_cols_text = "\n".join(self.schema)
        dialog = TacticalDialog(self, title="EDIT SCHEMA COLUMNS", label="COLUMN NAMES (ONE PER LINE):", is_multiline=True)
        dialog.input_field.setPlainText(current_cols_text)
        
        if dialog.exec() == QDialog.Accepted:
            cols = dialog.input_field.toPlainText()
            new_schema = [c.strip().lower().replace(" ", "_") for c in cols.split("\n") if c.strip()]
            if not new_schema: 
                return

            new_data = []
            for row in self.data:
                updated_row = {k: row.get(k, "") for k in new_schema}
                new_data.append(updated_row)
            
            self.data = new_data
            self.schema = new_schema
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
            self.refresh_table()

    def export_csv(self):
        self.table.clearFocus()
        try:
            current_sheet = self.tabs.tabText(self.tabs.currentIndex())
            save_path = export_inventory_to_csv(self.username, {"schema": self.schema, "data": self.data}, sheet_name=current_sheet)
            ghost_alert(self, "EXPORT SUCCESS", f"CSV exported to:\n{save_path}")
        except Exception as e:
            ghost_alert(self, "EXPORT ERROR", str(e))

    def import_csv(self):
        self.table.clearFocus()
        try:
            current_sheet = self.tabs.tabText(self.tabs.currentIndex())
            if not ghost_alert(self, "IMPORT CSV", f"Overwrite current data in '{current_sheet}' with export file?"):
                return  

            user_dir = os.path.join(INVENTORY_DIR, self.username)
            path = os.path.join(user_dir, f"inv_{self.current_sheet_name.lower()}_export.csv")

            if not os.path.exists(path):
                ghost_alert(self, "FILE NOT FOUND", f"Expected CSV at: {path}")
                return

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                new_data = list(reader)
                detected_schema = list(reader.fieldnames) if reader.fieldnames else self.schema

            self.schema = detected_schema
            self.data = new_data
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
            self.refresh_table()
            ghost_alert(self, "IMPORT SUCCESS", f"Imported {len(new_data)} rows successfully.")
        except Exception as e:
            ghost_alert(self, "IMPORT ERROR", str(e))