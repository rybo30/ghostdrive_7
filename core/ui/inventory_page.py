import os
import sys
import csv
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, QLineEdit,
    QHBoxLayout, QMessageBox, QDialog, QFormLayout, QTableWidgetItem, 
    QHeaderView, QLabel, QTabBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

# Import paths and manager mechanics
from core.paths import CORE_DIR, EVERYTHING_ELSE, INVENTORY_DIR

if EVERYTHING_ELSE not in sys.path:
    sys.path.insert(0, EVERYTHING_ELSE)

from inventory_manager import (
    load_inventory, save_inventory, export_inventory_to_csv, list_inventory_sheets, rename_inventory_file
)

from .style_config import (
    FONT_FAMILY, FONT_SIZE,
    COLOR_BG, COLOR_FG, COLOR_ACCENT, COLOR_BUTTON, COLOR_HIGHLIGHT,
    STYLE_LABEL, STYLE_BUTTON, COLOR_PAGE_BG, COLOR_BORDER, ghost_prompt, ghost_alert, TacticalDialog
)

class InventoryPage(QWidget):
    def __init__(self, username, passphrase, fernet):
        super().__init__()
        self.username = username
        self.passphrase = passphrase
        self.fernet = fernet
        self.current_sheet_name = "inventory"
        
        # Internal guard to prevent recursion loops during itemChanged signals
        self._is_refreshing = False 

        # 1. Main Layout & Style
        self.setStyleSheet(f"background-color: {COLOR_BG}; color: {COLOR_FG}; font-family: '{FONT_FAMILY}';")
        self.layout = QVBoxLayout(self)

        # 2. Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search inside current sheet...")
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_BUTTON}; 
                color: {COLOR_FG}; 
                border: 1px solid {COLOR_ACCENT};
                border-radius: 4px;
                padding: 5px;
            }}
        """)
        self.search_bar.textChanged.connect(self.filter_inventory)
        self.layout.addWidget(self.search_bar)

        # 3. Tab Management Section
        tab_container = QHBoxLayout()
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.setStyleSheet(f"""
            QTabBar::tab {{
                background: {COLOR_BUTTON};
                color: {COLOR_FG};
                padding: 8px 15px;
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

        # 4. Spreadsheet Configuration (True Inline Editing & Fluid Columns)
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        
        # Enable sorting when a user clicks a column header
        self.table.setSortingEnabled(True)
        
        # SPREADSHEET MECHANICS: Allow editing by double-clicking or typing
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
                padding: 4px;
            }}
        """)
        
        # --- 🆕 UNLOCKED & RESIZABLE COLUMNS SECTIONS ---
        header = self.table.horizontalHeader()
        
        # 1. Allow the user to manually click and drag column edges
        header.setSectionResizeMode(QHeaderView.Interactive)
        
        # 2. Cascade resizing options or stretch the last section to keep the UI clean
        header.setStretchLastSection(True) 
        
        # Connect the cell mutation listener
        self.table.itemChanged.connect(self.handle_cell_edited)
        self.layout.addWidget(self.table)

        # 5. Core Command Operations Actions
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

        # 6. Initialize State Tracking
        self.schema = [] 
        self.data = []
        self.load_sheet_list() 
        self.refresh_table()

    def load_sheet_list(self):
        """Fetches sheets across encrypted space and updates the navigation tabs."""
        self.tabs.blockSignals(True) 
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
            
        sheets = list_inventory_sheets(self.username)
        for s in sheets:
            self.tabs.addTab(s.replace("_", " ").capitalize())
        
        # Realignment of active index selection
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).lower().replace(" ", "_") == self.current_sheet_name:
                self.tabs.setCurrentIndex(i)
                break
        self.tabs.blockSignals(False)

    def switch_sheet(self, index):
        """Saves any uncommitted changes to disk before checking out another sheet target."""
        if index == -1: return
        
        if hasattr(self, 'schema') and self.schema:
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
        
        self.current_sheet_name = self.tabs.tabText(index).lower().replace(" ", "_")
        payload = load_inventory(self.username, self.fernet, self.current_sheet_name)
        
        self.schema = payload.get("schema", ["name", "quantity", "location", "last_checked"])
        self.data = payload.get("data", [])
        self.refresh_table()

    def refresh_table(self):
        """Redraws the table canvas cleanly without breaking synchronization chains."""
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
                
        # --- 🆕 AUTO-FIT TO INSIDE TEXT ---
        # Automatically adjust column widths based on cell contents and headers
        self.table.resizeColumnsToContents()
        
        self._is_refreshing = False

    def handle_cell_edited(self, item):
        """Tracks adjustments to table elements instantly and commits them straight to database schemas."""
        if self._is_refreshing:
            return

        row = item.row()
        col = item.column()
        new_value = item.text()
        field_key = self.schema[col]

        # Prevent out-of-bounds errors if background calculations mismatch rows
        if row >= len(self.data):
            return

        # Update runtime datasets
        self.data[row][field_key] = new_value

        # Automatically bump the mutation telemetry timestamp column if present
        if "last_checked" in self.schema:
            today = datetime.now().strftime("%Y-%m-%d")
            self.data[row]["last_checked"] = today
            
            # Silently adjust UI visualization field
            self._is_refreshing = True
            time_col = self.schema.index("last_checked")
            time_item = self.table.item(row, time_col)
            if time_item:
                time_item.setText(today)
            self._is_refreshing = False

        # Persist right away to encrypted backup arrays
        save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)

    def add_blank_row(self):
        """Appends a row directly into the interface canvas grid for input."""
        new_item = {field: "" for field in self.schema}
        if "last_checked" in self.schema:
            new_item["last_checked"] = datetime.now().strftime("%Y-%m-%d")
            
        self.data.append(new_item)
        self.refresh_table()
        
        # Put user focus right into the first cell of their new row
        new_row_idx = self.table.rowCount() - 1
        self.table.setCurrentCell(new_row_idx, 0)
        self.table.editItem(self.table.item(new_row_idx, 0))

    def delete_row(self):
        """Removes a row object array targeting from active parameters records."""
        selected_row = self.table.currentRow()
        if selected_row == -1:
            ghost_alert(self, "SYSTEM NOTICE", "No active item array target selected.")
            return
            
        confirm = ghost_alert(self, "CONFIRM PURGE", "Permanently excise selected row tracking telemetry records?")
        if confirm:
            del self.data[selected_row]
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
            self.refresh_table()

    def create_new_sheet(self):
        """Assembles another unique page layout across secure clusters mapping targets."""
        name, ok = ghost_prompt(self, "NEW DESIGNATION DATA SHEET", "ASSIGN IDENTIFIER STRING CODE:")
        if ok and name.strip():
            sheet_id = name.strip().lower().replace(" ", "_")
            
            new_payload = {
                "schema": ["name", "quantity", "location", "last_checked"], 
                "data": []
            }
            save_inventory(self.username, new_payload, self.fernet, sheet_id)
            self.current_sheet_name = sheet_id
            self.load_sheet_list()
            self.refresh_table()

    def rename_current_sheet(self):
        """Modifies identity metrics assigned directly onto underlying tracking logs data records files."""
        if self.current_sheet_name == "inventory":
            ghost_alert(self, "ACCESS REJECTED", "Primary root core inventory configuration datasets are system locked.")
            return

        old_name_display = self.current_sheet_name.replace("_", " ").capitalize()
        new_name, ok = ghost_prompt(self, "MUTATE SHEET DESIGNATION", "ENTER NEW PROFILE CODENAME:", placeholder=old_name_display)
        
        if ok and new_name.strip():
            new_sheet_id = new_name.strip().lower().replace(" ", "_")
            success, error = rename_inventory_file(self.username, self.current_sheet_name, new_sheet_id)
            
            if success:
                self.current_sheet_name = new_sheet_id
                self.load_sheet_list()
            else:
                ghost_alert(self, "SYSTEM FAULT", f"Rename execution halted: {error}")

    def delete_current_sheet(self):
        """Erases the physical data file completely and reverts safely to the root sheet."""
        if self.current_sheet_name == "inventory":
            ghost_alert(self, "ACCESS REJECTED", "Cannot delete core root logging manifest system maps.")
            return
            
        confirm = ghost_alert(self, "TERMINATE MANIFEST", f"Purge sheet profile database completely matching '{self.current_sheet_name}'?")
        if not confirm: 
            return
            
        from inventory_manager import get_inventory_path
        filepath = get_inventory_path(self.username, self.current_sheet_name)
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # Revert smoothly back to safety parameters array spaces
            self.current_sheet_name = "inventory"
            self.load_sheet_list()
            payload = load_inventory(self.username, self.fernet, self.current_sheet_name)
            self.schema = payload.get("schema", ["name", "quantity", "location", "last_checked"])
            self.data = payload.get("data", [])
            self.refresh_table()
        except Exception as e:
            ghost_alert(self, "FATAL ERROR", f"Destruction execution failure mapping sequences: {e}")

    def filter_inventory(self, text):
        """Evaluates content rows filtering hidden properties dynamically."""
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
        """Alters dataset keys structurally modifying dictionary objects array entries framing variables."""
        current_cols_text = "\n".join(self.schema)
        dialog = TacticalDialog(self, title="SCHEMA PARAMETERS ADJUSTMENT", label="COLUMN DESIGNATIONS (ONE PER LINE):", is_multiline=True)
        dialog.input_field.setPlainText(current_cols_text)
        
        if dialog.exec() == QDialog.Accepted:
            cols = dialog.input_field.toPlainText()
            new_schema = [c.strip().lower().replace(" ", "_") for c in cols.split("\n") if c.strip()]
            
            if not new_schema: return

            new_data = []
            for row in self.data:
                if len(new_schema) == len(self.schema):
                    updated_row = {new_schema[i]: row.get(self.schema[i], "") for i in range(len(new_schema))}
                else:
                    updated_row = {k: row.get(k, "") for k in new_schema}
                new_data.append(updated_row)
            
            self.data = new_data
            self.schema = new_schema
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
            self.refresh_table()

    def export_csv(self):
        try:
            current_sheet = self.tabs.tabText(self.tabs.currentIndex())
            save_path = export_inventory_to_csv(self.username, {"schema": self.schema, "data": self.data}, sheet_name=current_sheet)
            ghost_alert(self, "EXPORT ARCHIVED", f"Data stream mapped directly outward via:\n{save_path}")
        except Exception as e:
            ghost_alert(self, "EXPORT INTERRUPTED", str(e))

    def import_csv(self):
        try:
            current_sheet = self.tabs.tabText(self.tabs.currentIndex())
            if not ghost_alert(self, "OVERWRITE RUNTIME CODES", f"Acknowledge import override command parameters targeting '{current_sheet}'?"):
                return  

            user_dir = os.path.join(INVENTORY_DIR, self.username)
            path = os.path.join(user_dir, f"inv_{self.current_sheet_name.lower()}_export.csv")

            if not os.path.exists(path):
                ghost_alert(self, "DATA CORRUPTION STREAM", f"File path mapping failed. Drop matching csv to target field destination: {path}")
                return

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                new_data = list(reader)
                detected_schema = list(reader.fieldnames) if reader.fieldnames else self.schema

            self.schema = detected_schema
            self.data = new_data
            save_inventory(self.username, {"schema": self.schema, "data": self.data}, self.fernet, self.current_sheet_name)
            self.refresh_table()
            ghost_alert(self, "UPLINK RESTORED", f"Synchronized tracking arrays for {len(new_data)} item units across {len(self.schema)} telemetry metrics.")
        except Exception as e:
            ghost_alert(self, "CRITICAL CONFLICT", str(e))