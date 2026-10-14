# [health_page.py]


import os
import re
import calendar
import pyqtgraph as pg
from datetime import datetime, date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QGridLayout, QPushButton, QLineEdit, QDialog, QScrollArea, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont 
from .style_config import (
    T, COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT_DIM, COLOR_BG,
    STYLE_SECTION_TITLE, STYLE_HUD_VAL, STYLE_HUD_LBL, TacticalDialog, STYLE_SCROLLBAR, COLOR_FG
)
from Everything_else.health_manager import load_health_data, save_health_data
from Everything_else.health_engine import HealthEngine


class MacroEntryDialog(TacticalDialog): # Inherit from TacticalDialog
    def __init__(self, parent=None, initial_macros=None):
        # Initialize TacticalDialog with specific titles
        super().__init__(parent, title="MACRO COMMAND", label="ENTER NUTRITIONAL DATA:")
        self.setFixedWidth(300)
        
        # We don't need the default input field from TacticalDialog
        self.input_field.hide()
        
        # Local refs to style constants from style_config
        GOLD = T['PROTOCOL_GOLD']
        LINE = T['HUD_LINE']

        self.inputs = {}
        # Create the grid for macros
        macro_layout = QVBoxLayout()
        for label_text in ["PROTEIN", "CARBS", "FAT"]:
            l = QLabel(label_text)
            l.setStyleSheet(f"color: {GOLD}; font-family: 'Consolas'; font-size: 10px; border: none; background: transparent;")
            
            edit = QLineEdit()
            edit.setPlaceholderText("0g")
            val = initial_macros.get(label_text.lower(), 0) if initial_macros else 0
            edit.setText(str(val) if val > 0 else "")
            
            # Use the styling consistent with TacticalDialog QLineEdits
            edit.setStyleSheet(f"""
                QLineEdit {{
                    background: #000000; 
                    color: {GOLD}; 
                    border: 1px solid {LINE}; 
                    border-radius: 4px; 
                    padding: 8px; 
                    font-family: 'Consolas'; 
                    font-size: 14px;
                }}
                QLineEdit:focus {{ border: 1px solid {GOLD}; }}
            """)
            
            macro_layout.addWidget(l)
            macro_layout.addWidget(edit)
            macro_layout.addSpacing(5)
            self.inputs[label_text.lower()] = edit

        # Insert our custom macro layout into the TacticalDialog's container
        # The TacticalDialog layout has: [Header, Line, Label, Input, Buttons]
        # We insert before the buttons (index 4)
        self.container.layout().insertLayout(4, macro_layout)

    def get_values(self):
        results = {}
        for k, v in self.inputs.items():
            text = "".join(filter(str.isdigit, v.text()))
            results[k] = int(text) if text else 0
        return results


class WeightChartSection(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {T['BG_PANEL']}; 
                border: 1px solid {COLOR_BORDER}; 
                border-radius: 12px;
            }}
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        header = QLabel("WEIGHT CHART")
        header.setStyleSheet(f"color: {T['PROTOCOL_GOLD']}; font-weight: 900; letter-spacing: 2px; font-size: 10px; border: none; background: transparent;")
        self.layout.addWidget(header)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(T['BG_PANEL']) 
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.hideButtons()
        
        # --- UI REFINEMENT: KILL ALL BORDERS ---
        # 1. Hide the outer widget frame (the "last line" you saw)
        self.plot_widget.setFrameStyle(QFrame.NoFrame) 
        
        # 2. Get the internal plot item to hide the top/right axes
        plot_item = self.plot_widget.getPlotItem()
        plot_item.showAxis('top', False)
        plot_item.showAxis('right', False)
        
        # 3. Ensure the ViewBox itself has no internal border
        plot_item.getViewBox().setBorder(None)
        
        # Tactical grid
        self.plot_widget.showGrid(x=False, y=True, alpha=0.05)
        self.plot_widget.getAxis("bottom").enableAutoSIPrefix(False)
        
        styles = {"color": COLOR_TEXT_DIM, "font-size": "10px", "font-family": "Consolas"}
        
        # Ultra-subtle tactical axis lines
        axis_pen = pg.mkPen(color="#30363d", width=1) 
        self.plot_widget.getAxis("left").setPen(axis_pen)
        self.plot_widget.getAxis("bottom").setPen(axis_pen)
        
        self.plot_widget.getAxis("left").setLabel("LBS", **styles)
        self.plot_widget.getAxis("bottom").setLabel("TIMELINE", **styles)
        
        self.layout.addWidget(self.plot_widget)

    def update_chart(self, logs, profile, engine):
        self.plot_widget.clear()
        
        # --- CRITICAL FIX: Initialize variable at the start ---
        victory_ts = None
        
        # 1. Gather historical projected weight
        calc_history = []
        sorted_dates = sorted(logs.keys())
        
        for date_str in sorted_dates:
            try:
                dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                proj_w = engine.get_projected_weight(logs, dt_obj)
                calc_history.append((dt_obj.timestamp(), proj_w))
            except: 
                continue

        if not calc_history: 
            return

        # 2. Handle Goal Point
        goal_w = float(profile.get("weight_goal", 0))
        arrival_date_str = engine.get_estimated_arrival_date(logs, goal_w)
        
        if arrival_date_str and "/" in arrival_date_str:
            try:
                arrival_dt = datetime.strptime(arrival_date_str, "%m/%d/%Y")
                victory_ts = arrival_dt.timestamp()
                # Append to chart line
                calc_history.append((victory_ts, goal_w))
            except: 
                # Ensure it remains None if parsing fails
                victory_ts = None

        # 3. Plot Main Line (Neon Blue Glow)
        cx = [h[0] for h in calc_history]
        cy = [h[1] for h in calc_history]
        path_pen = pg.mkPen(color=(88, 166, 255, 180), width=2)
        self.plot_widget.plot(cx, cy, pen=path_pen)

        # 4. Draw Goal Node (The Big Gold Star)
        # Now we check 'is not None' because the variable is guaranteed to exist
        if victory_ts is not None:
            goal_node = pg.ScatterPlotItem(
                x=[victory_ts], y=[goal_w], size=22, 
                brush=T['PROTOCOL_GOLD'], 
                pen=pg.mkPen("#FFFFFF", width=1), 
                symbol='star'
            )
            self.plot_widget.addItem(goal_node)
            
            eta_label = pg.TextItem(f"GOAL\n{arrival_date_str}", color=T['PROTOCOL_GOLD'], anchor=(0.5, 1.4))
            
            goal_font = QFont("Consolas", 9)
            goal_font.setBold(True)
            eta_label.setFont(goal_font)
            
            eta_label.setPos(victory_ts, goal_w)
            self.plot_widget.addItem(eta_label)

        # 5. Draw "Current Location" Dot
        latest_actual = None
        for date_str in reversed(sorted_dates):
            w = logs[date_str].get("weight", 0)
            if w > 0:
                ts = datetime.strptime(date_str, "%Y-%m-%d").timestamp()
                latest_actual = (ts, w)
                break
        
        if latest_actual:
            current_node = pg.ScatterPlotItem(
                x=[latest_actual[0]], y=[latest_actual[1]],
                size=12, brush="#FFFFFF", symbol='o',
                pen=pg.mkPen(T['PROTOCOL_GOLD'], width=1)
            )
            self.plot_widget.addItem(current_node)

        # --- INTELLIGENT X-AXIS TICKS ---
        start_ts = cx[0]
        end_ts = cx[-1]
        total_days = (end_ts - start_ts) / 86400

        tick_timestamps = [start_ts + (i * (end_ts - start_ts) / 5) for i in range(6)]
        fmt = '%m/%Y' if total_days > 365 else '%m/%d'

        ticks = [(ts, datetime.fromtimestamp(ts).strftime(fmt)) for ts in tick_timestamps]
        self.plot_widget.getAxis('bottom').setTicks([ticks])
        self.plot_widget.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

class WeightHistoryDialog(TacticalDialog):
    def __init__(self, logs, parent=None):
        # Correctly call TacticalDialog init
        super().__init__(parent, title="WEIGH-IN LOGS", label="CHRONOLOGICAL HISTORY:")
        self.setFixedSize(320, 450)

        # TacticalDialog handles the background/border; we just hide the default input
        self.input_field.hide() 
        
        # Prepare history data
        history = []
        for date_str, day_data in logs.items():
            w = day_data.get("weight", 0)
            if w > 0: history.append((date_str, w))
        history.sort(key=lambda x: x[0], reverse=True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Clean scrollbar logic as you had it
        clean_scrollbar = STYLE_SCROLLBAR.replace("/* Vertical Scrollbar */", "").replace("/* Horizontal Scrollbar - THIS IS WHAT YOU WERE MISSING */", "").replace("/* Hide buttons and track background for both */", "")
        scroll.setStyleSheet(f"border: none; background: transparent; {clean_scrollbar}")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(8)

        # ... (Rest of your history row logic remains the same) ...
        if not history:
            none_lbl = QLabel("NO RECORDS DETECTED")
            none_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-style: italic; font-size: 10px;")
            container_layout.addWidget(none_lbl)
        else:
            for date_str, weight in history:
                row = QFrame()
                row.setStyleSheet(f"background: {T['BG_GLASS']}; border-radius: 4px; border-bottom: 1px solid {T['HUD_LINE']};")
                row_layout = QHBoxLayout(row)
                d_lbl = QLabel(date_str)
                d_lbl.setStyleSheet(f"color: {COLOR_FG}; font-family: 'Consolas'; font-size: 11px; letter-spacing: 1px;")
                w_lbl = QLabel(f"{weight} LBS")
                w_lbl.setStyleSheet(f"color: {T['PROTOCOL_GOLD']}; font-weight: bold; font-family: 'Consolas';")
                row_layout.addWidget(d_lbl); row_layout.addStretch(); row_layout.addWidget(w_lbl)
                container_layout.addWidget(row)

        container_layout.addStretch()
        scroll.setWidget(container)
        
        # Inject into the TacticalDialog structure
        self.container.layout().insertWidget(4, scroll)

        self.confirm_btn.setText("DISMISS")
        self.cancel_btn.hide() # Hide abort as history is read-only


class MiniDayNode(QFrame):
    clicked = Signal(date)

    def __init__(self, day_date, is_active=False, has_data=False):
        super().__init__()
        self.day_date = day_date
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        
        # Sleek Ghost Dark styling
        bg = T['ACCENT_GLOW'] if is_active else "transparent"
        border_color = COLOR_ACCENT if is_active else (T['HUD_LINE'] if has_data else COLOR_BORDER)
        text_color = "#fff" if is_active or has_data else COLOR_TEXT_DIM
        
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QFrame:hover {{ border: 1px solid {COLOR_ACCENT}; background: {T['BG_HOVER']}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        lbl = QLabel(str(day_date.day))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {text_color}; font-size: 11px; font-weight: bold; border: none;")
        layout.addWidget(lbl)

    def mousePressEvent(self, event):
        self.clicked.emit(self.day_date)

class HealthPage(QWidget):
    def __init__(self, username, fernet):
        super().__init__()
        self.username = username
        self.fernet = fernet
        self.selected_date = date.today()
        self.view_date = date.today().replace(day=1)
        self.data = load_health_data(username, fernet)
        self.init_ui()

    def init_ui(self):
        # 1. The Real Main Layout (holds the ScrollArea)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # 2. Setup the Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        # Apply your tactical scrollbar style
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ 
                background: {COLOR_BG}; 
                border: none; 
            }}
            QWidget#scrollViewport {{ 
                background: {COLOR_BG}; 
            }}
            {STYLE_SCROLLBAR}
        """)

        # 3. The Container Widget & Internal Layout
        self.container = QWidget()
        self.container.setStyleSheet(f"background: {COLOR_BG};")
        self.main_layout = QVBoxLayout(self.container) # All your widgets go here
        self.main_layout.setContentsMargins(35, 30, 35, 30)
        self.main_layout.setSpacing(25)

        # 4. Attach everything
        self.scroll.setWidget(self.container)
        outer_layout.addWidget(self.scroll)

        # Header
        title = QLabel("CALORIE TRACKER")
        title.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-weight: 700; 
            font-size: 22px; 
            letter-spacing: 1px; 
            border: none;
            font-family: 'Segoe UI', sans-serif;
        """)
        self.main_layout.addWidget(title)

        # Top Content
        top_layout = QHBoxLayout()
        top_layout.setSpacing(30)

        # 1. Left Sidebar (Profile + Cal)
        left_sidebar = QVBoxLayout()
        left_sidebar.setSpacing(20)

        # Profile
        self.stats_panel = QFrame()
        self.stats_panel.setFixedWidth(280) # Reset to 280 (was accidentally 20)
        self.stats_panel.setStyleSheet(f"background: {T['BG_PANEL']}; border: 1px solid {COLOR_BORDER}; border-radius: 8px;")
        self.stats_layout = QVBoxLayout(self.stats_panel)
        left_sidebar.addWidget(self.stats_panel)

        # Calendar
        self.cal_container = QFrame()
        self.cal_container.setFixedWidth(280) # Match width for symmetry
        self.cal_container.setStyleSheet(f"background: {T['BG_PANEL']}; border: 1px solid {COLOR_BORDER}; border-radius: 8px;")
        self.cal_vbox = QVBoxLayout(self.cal_container)
        
        nav_header = QHBoxLayout()
        self.prev_btn = QPushButton("<")
        self.next_btn = QPushButton(">")
        for b in [self.prev_btn, self.next_btn]:
            b.setFixedSize(24, 24)
            b.setStyleSheet(f"QPushButton {{ background: {T['BG_GLASS']}; color: {COLOR_ACCENT}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; font-weight: bold; }} QPushButton:hover {{ background: {T['BG_HOVER']}; }}")
        
        self.prev_btn.clicked.connect(lambda: self.change_month(-1))
        self.next_btn.clicked.connect(lambda: self.change_month(1))
        
        self.cal_title = QLabel("")
        self.cal_title.setStyleSheet(f"color: {T['TEXT_MAIN']}; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        nav_header.addWidget(self.prev_btn)
        nav_header.addStretch()
        nav_header.addWidget(self.cal_title)
        nav_header.addStretch()
        nav_header.addWidget(self.next_btn)
        self.cal_vbox.addLayout(nav_header)

        self.cal_grid = QGridLayout()
        self.cal_grid.setSpacing(4)
        self.cal_vbox.addLayout(self.cal_grid)
        left_sidebar.addWidget(self.cal_container)
        
        left_sidebar.addStretch()
        top_layout.addLayout(left_sidebar)

        # 2. Main Daily Intel Panel
        self.daily_panel = QFrame()
        self.daily_panel.setStyleSheet(f"background: {T['BG_PANEL']}; border: 1px solid {COLOR_BORDER}; border-radius: 12px;")
        self.daily_layout = QVBoxLayout(self.daily_panel)
        self.daily_layout.setContentsMargins(30, 30, 30, 30)
        top_layout.addWidget(self.daily_panel, 1)

        self.main_layout.addLayout(top_layout)


        self.weight_chart = WeightChartSection()
        self.weight_chart.setFixedHeight(200) # Give it some height
        self.main_layout.addWidget(self.weight_chart)


        # 3. Bottom Projection Panel
        self.projection_frame = QFrame()
        self.projection_frame.setFixedHeight(110)
        self.projection_frame.setStyleSheet(f"""
            QFrame {{
                background: {T['BG_GLASS']}; 
                border: 1px solid {T['HUD_LINE']}; 
                border-radius: 12px;
            }}
        """)
        self.proj_layout = QHBoxLayout(self.projection_frame)
        self.proj_layout.setContentsMargins(40, 15, 40, 15) # Increased padding
        self.main_layout.addWidget(self.projection_frame)
        
        self.refresh_dashboard()

    def refresh_machine_stats(self):
        self.clear_layout(self.stats_layout)
        p = self.data.get("profile", {})
        
        title = QLabel("CORE PROFILE")
        title.setStyleSheet(STYLE_HUD_LBL)
        self.stats_layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)

        # --- New Height Selector Logic ---
        height_container = QWidget()
        height_container.setStyleSheet("background: transparent; border: none;")
        h_vbox = QVBoxLayout(height_container)
        h_vbox.setContentsMargins(0,0,0,0); h_vbox.setSpacing(2)
        
        h_lbl = QLabel("HEIGHT"); h_lbl.setStyleSheet(STYLE_HUD_LBL)
        h_vbox.addWidget(h_lbl)
        
        h_hbox = QHBoxLayout()
        h_hbox.setSpacing(4)
        
        # Calculate current ft/in from total inches
        total_inches = p.get("height", 0)
        curr_ft = int(total_inches // 12) if total_inches > 0 else 5
        curr_in = int(total_inches % 12) if total_inches > 0 else 0

        self.ft_combo = QComboBox()
        self.in_combo = QComboBox()
        
        combo_style = f"""
            QComboBox {{
                background: transparent; border: none; 
                border-bottom: 1px solid {COLOR_BORDER}; 
                color: white; font-size: 13px; padding: 2px;
            }}
            QComboBox QAbstractItemView {{
                background: {T['BG_PANEL']};
                color: white;
                selection-background-color: {T['PROTOCOL_GOLD']};
            }}
        """
        
        self.ft_combo.addItems([f"{i}'" for i in range(3, 9)]) # 3ft to 8ft
        self.in_combo.addItems([f"{i}\"" for i in range(12)]) # 0in to 11in
        
        self.ft_combo.setStyleSheet(combo_style)
        self.in_combo.setStyleSheet(combo_style)
        
        # Set current values
        self.ft_combo.setCurrentText(f"{curr_ft}'")
        self.in_combo.setCurrentText(f"{curr_in}\"")
        
        # Connect signals
        self.ft_combo.currentIndexChanged.connect(self.update_height_from_combos)
        self.in_combo.currentIndexChanged.connect(self.update_height_from_combos)
        
        h_hbox.addWidget(self.ft_combo)
        h_hbox.addWidget(self.in_combo)
        h_vbox.addLayout(h_hbox)
        
        grid.addWidget(height_container, 0, 0)
        # --- End Height Selector ---

        def create_input(label, key, val):
            container = QWidget()
            container.setStyleSheet("background: transparent; border: none;")
            l = QVBoxLayout(container); l.setContentsMargins(0,0,0,0); l.setSpacing(2)
            lbl = QLabel(label); lbl.setStyleSheet(STYLE_HUD_LBL)
            edit = QLineEdit(str(val))
            edit.setStyleSheet(f"background: transparent; border: none; border-bottom: 1px solid {COLOR_BORDER}; color: white; font-size: 13px; padding: 2px;")
            edit.editingFinished.connect(lambda: self.update_profile_field(key, edit.text()))
            l.addWidget(lbl); l.addWidget(edit)
            return container

        # Add the rest of the inputs (Starting at col 1 since height is at 0,0)
        grid.addWidget(create_input("GOAL WEIGHT", "weight_goal", p.get("weight_goal", 0)), 0, 1)
        grid.addWidget(create_input("SEX (M/F)", "sex", p.get("sex", "M")), 1, 0)
        grid.addWidget(create_input("AGE", "age", p.get("age", 0)), 1, 1)
        self.stats_layout.addLayout(grid)
        

        self.stats_layout.addSpacing(10)
        weight_row = QHBoxLayout()
        weight_row.setSpacing(8)

        # Use Engine to find the last known actual weigh-in
        engine = HealthEngine(p)
        last_w = engine.get_latest_weigh_in(self.data["logs"]) 
        
        w_val = QLabel(f"{last_w} lbs" if last_w > 0 else "--- lbs")
        w_val.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 16px; font-weight: bold; font-family: 'Consolas'; border: none;")
        
        btn_style = f"""
            QPushButton {{ 
                background: {T['BG_GLASS']}; color: white; border: 1px solid {COLOR_BORDER}; 
                border-radius: 4px; font-size: 10px; padding: 4px 8px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {T['BG_HOVER']}; border: 1px solid {COLOR_ACCENT}; }}
        """
        
        weigh_btn = QPushButton("Weigh-In")
        weigh_btn.setStyleSheet(btn_style)
        # Always trigger weigh-in for the current real-world date
        weigh_btn.clicked.connect(lambda: self.trigger_weigh_in(date.today().strftime("%Y-%m-%d")))

        hist_btn = QPushButton("History")
        hist_btn.setStyleSheet(btn_style)
        hist_btn.clicked.connect(self.show_weight_history)

        weight_row.addWidget(w_val)
        weight_row.addWidget(weigh_btn)
        weight_row.addWidget(hist_btn)
        weight_row.addStretch()
        
        self.stats_layout.addLayout(weight_row)

    def refresh_daily_view(self):
        self.clear_layout(self.daily_layout)
        date_str = self.selected_date.strftime("%Y-%m-%d")
        engine = HealthEngine(self.data["profile"])
        
        if date_str not in self.data["logs"]:
            self.data["logs"][date_str] = {
                "breakfast": 0, "lunch": 0, "dinner": 0, 
                "calories": 0, "activity": 5, "workout_burn": 0, 
                "weight": 0 
            }

        day_data = self.data["logs"][date_str]
        
        # --- Header ---
        header_layout = QHBoxLayout()
        header = QLabel(self.selected_date.strftime("%B %d, %Y").upper())
        header.setStyleSheet(f"color: {T['TEXT_MAIN']}; font-size: 20px; font-weight: 800; border: none; background: transparent;")
        header_layout.addWidget(header)
        
        if day_data.get("weight", 0) > 0:
            banner = QLabel(" ◆ WEIGH-IN LOGGED")
            banner.setStyleSheet(f"color: {T['PROTOCOL_GOLD']}; font-weight: bold; font-size: 11px; letter-spacing: 1px; border: none; background: transparent;")
            header_layout.addWidget(banner)
        
        header_layout.addStretch()
        self.daily_layout.addLayout(header_layout)

        # --- Energy HUD Calculation ---
        proj_w = engine.get_projected_weight(self.data["logs"], self.selected_date)
        intake = day_data.get('calories', 0)
        
        if intake > 0:
            delta = engine.get_daily_delta(intake, day_data.get('activity', 5), proj_w, day_data.get('workout_burn', 0))
            status_color = T['PROTOCOL_GOLD'] if (delta and delta <= 0) else T['DANGER']
            delta_text = f"{int(delta)} KCAL" if delta is not None else "---"
            sub_text = "DAILY ENERGY VARIANCE"
        else:
            bmr = engine.calculate_bmr(proj_w)
            tdee = bmr * engine.map_activity_to_multiplier(day_data.get('activity', 5)) * 0.6
            delta = 0 - (tdee + day_data.get('workout_burn', 0))
            status_color = COLOR_TEXT_DIM
            delta_text = f"{int(delta)} KCAL"
            sub_text = "ESTIMATED DAILY BURN"

        # --- Variance Display ---
        val = QLabel(delta_text)
        val.setStyleSheet(f"color: {status_color}; font-size: 48px; font-weight: bold; font-family: 'Consolas'; border: none; background: transparent;")
        self.daily_layout.addWidget(val)
        
        sub = QLabel(sub_text)
        sub.setStyleSheet(STYLE_HUD_LBL + " border: none; background: transparent;")
        self.daily_layout.addWidget(sub)

        # --- Daily Macro Counter ---
        total_p = total_c = total_f = 0
        for meal in ["breakfast", "lunch", "dinner"]:
            m = day_data.get(f"{meal}_macros", {})
            total_p += m.get("protein", 0)
            total_c += m.get("carbs", 0)
            total_f += m.get("fat", 0)

        if total_p + total_c + total_f > 0:
            macro_summary = QLabel(f"MACROS:  Protein: {total_p}g  |  Carbs: {total_c}g  |  Fats {total_f}g")
            macro_summary.setStyleSheet(f"color: {T['PROTOCOL_GOLD']}; font-family: 'Consolas'; font-size: 11px; font-weight: bold; margin-top: 5px; border: none; background: transparent;")
            self.daily_layout.addWidget(macro_summary)

        self.daily_layout.addSpacing(30)

        # --- Input Grid ---
        input_grid = QGridLayout()
        input_grid.setSpacing(20)

        def create_field(label, key, val):
            container = QWidget()
            # KILL THE CONTAINER BORDER HERE:
            container.setStyleSheet("background: transparent; border: none;")
            
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.setSpacing(4)
    
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; border: none; background: transparent;")
            v_layout.addWidget(lbl)

            input_row = QHBoxLayout()
            input_row.setSpacing(8)

            meal_macros = day_data.get(f"{key}_macros", {})
            is_macro_driven = any(meal_macros.values()) if meal_macros else False

            if key in ["breakfast", "lunch", "dinner"]:
                plus_btn = QPushButton("+")
                plus_btn.setFixedSize(38, 38)
                btn_border = T['PROTOCOL_GOLD'] if is_macro_driven else COLOR_BORDER
                plus_btn.setStyleSheet(f"""
                    QPushButton {{ 
                        color: {T['PROTOCOL_GOLD']}; background: {T['BG_GLASS']}; 
                        border: 1px solid {btn_border}; font-size: 16px; font-weight: bold; border-radius: 4px; 
                    }}
                    QPushButton:hover {{ background: {T['BG_HOVER']}; }}
                """)
                plus_btn.clicked.connect(lambda: self.open_macro_editor(date_str, key))
                input_row.addWidget(plus_btn)

            edit = QLineEdit("" if not val else str(val))
            edit.setReadOnly(is_macro_driven)
            edit.setFixedHeight(38)
            edit.setAlignment(Qt.AlignCenter)
            bg_color = "rgba(255, 176, 0, 0.05)" if is_macro_driven else "rgba(0, 0, 0, 0.3)"
            # Note: the QLineEdit still gets its 1px border because it needs to look like an input
            edit.setStyleSheet(f"""
                QLineEdit {{ 
                    background: {bg_color}; border: 1px solid {T['HUD_LINE']}; 
                    color: {COLOR_ACCENT}; font-family: 'Consolas'; font-size: 14px; border-radius: 4px; 
                }}
            """)
    
            if not is_macro_driven:
                edit.editingFinished.connect(lambda: self.update_daily_field(date_str, key, edit.text()))
    
            input_row.addWidget(edit)
            v_layout.addLayout(input_row)
            return container

        input_grid.addWidget(create_field("BREAKFAST", "breakfast", day_data.get('breakfast', 0)), 0, 0)
        input_grid.addWidget(create_field("LUNCH", "lunch", day_data.get('lunch', 0)), 1, 0)
        input_grid.addWidget(create_field("DINNER", "dinner", day_data.get('dinner', 0)), 2, 0)
        input_grid.addWidget(create_field("ACTIVITY", "activity", day_data.get('activity', 5)), 0, 1)
        input_grid.addWidget(create_field("WORKOUT BURN", "workout_burn", day_data.get('workout_burn', 0)), 1, 1)
        
        est_lbl = QLabel(f"EST. WEIGHT: {proj_w} LBS")
        est_lbl.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 14px; font-weight: bold; font-family: 'Consolas'; margin-top: 10px; border: none; background: transparent;")
        input_grid.addWidget(est_lbl, 2, 1, Qt.AlignCenter)

        self.daily_layout.addLayout(input_grid)
        self.daily_layout.addStretch()
        self.update_projections(engine, delta)




    def show_weight_history(self):
        dialog = WeightHistoryDialog(self.data["logs"], self)
        dialog.exec()


    def open_macro_editor(self, date_str, meal_key):
        day_data = self.data["logs"][date_str]
        initial = day_data.get(f"{meal_key}_macros", {"protein":0, "carbs":0, "fat":0})
    
        dialog = MacroEntryDialog(self, initial)
        if dialog.exec():
            macros = dialog.get_values()
            engine = HealthEngine(self.data["profile"])
        
            # Calculate total calories from the new macros
            cal_total = engine.calculate_calories_from_macros(
                macros['protein'], macros['carbs'], macros['fat']
            )
        
            # Update the log
            self.data["logs"][date_str][f"{meal_key}_macros"] = macros
            self.data["logs"][date_str][meal_key] = cal_total
        
            # Recalculate daily total
            d = self.data["logs"][date_str]
            d["calories"] = d.get("breakfast", 0) + d.get("lunch", 0) + d.get("dinner", 0)
        
            save_health_data(self.username, self.fernet, self.data)
            self.refresh_dashboard()

    def clear_macros(self, date_str, meal_key):
        """Optional helper to reset a meal to manual calorie entry."""
        if f"{meal_key}_macros" in self.data["logs"][date_str]:
            del self.data["logs"][date_str][f"{meal_key}_macros"]
            save_health_data(self.username, self.fernet, self.data)
            self.refresh_dashboard()


    def update_height_from_combos(self):
        try:
            # Strip the ' and " symbols to get integers
            ft = int(self.ft_combo.currentText().replace("'", ""))
            inch = int(self.in_combo.currentText().replace("\"", ""))
            
            total_inches = (ft * 12) + inch
            
            # Save to profile
            self.data["profile"]["height"] = float(total_inches)
            save_health_data(self.username, self.fernet, self.data)
            
            # Refresh to update any calculations (like BMR) that rely on height
            self.refresh_daily_view() 
        except Exception as e:
            print(f"Height update error: {e}")


    def trigger_weigh_in(self, date_str):
        from .style_config import ghost_prompt
        
        # Get current weight for the placeholder/default
        current_weight = self.data["profile"].get("weight", 0)
        
        # Trigger the Tactical Prompt
        val_str, ok = ghost_prompt(
            self, 
            title="BIOMETRIC UPDATE", 
            label="ENTER CURRENT WEIGHT (LBS):", 
            placeholder=str(current_weight)
        )
        
        if ok and val_str:
            try:
                val = float(val_str)
                # Update the specific day's log
                if date_str not in self.data["logs"]:
                    self.data["logs"][date_str] = {}
                
                self.data["logs"][date_str]["weight"] = val
                
                # Also update the profile master weight for future reference
                self.data["profile"]["weight"] = val
                
                save_health_data(self.username, self.fernet, self.data)
                self.refresh_dashboard()
            except ValueError:
                # Optional: Add a ghost_alert here for "INVALID DATA"
                print("Invalid weight format entered.")

    def update_daily_field(self, date_str, key, value):
        try:
            val = int(float(value)) if value.strip() else 0
            self.data["logs"][date_str][key] = val
            if key in ["breakfast", "lunch", "dinner"]:
                d = self.data["logs"][date_str]
                d["calories"] = d.get("breakfast", 0) + d.get("lunch", 0) + d.get("dinner", 0)

            save_health_data(self.username, self.fernet, self.data)
            self.refresh_dashboard()
        except Exception as e:
            print(f"Update error: {e}")

    def update_projections(self, engine, delta):
        self.clear_layout(self.proj_layout)
        p = self.data["profile"]
        goal_w = float(p.get("weight_goal", 0))
        curr_proj_w = engine.get_projected_weight(self.data["logs"], self.selected_date)
        
        # --- THE FIX ---
        # Instead of projecting based on today's single delta, 
        # we call the engine function that the chart uses.
        arrival_date_str = engine.get_estimated_arrival_date(self.data["logs"], goal_w)
        
        if arrival_date_str:
            # If the engine returns a date string, use it
            eta_str = arrival_date_str.upper()
            status_color = T['PROTOCOL_GOLD']
        else:
            # Fallback if the engine can't calculate a trend (e.g. no logs)
            eta_str = "STATIONARY"
            status_color = COLOR_TEXT_DIM

        def add_stat(label, val, color, sub_label=""):
            v = QVBoxLayout()
            v.setSpacing(2)
            l_lbl = QLabel(label)
            l_lbl.setAlignment(Qt.AlignCenter)
            l_lbl.setStyleSheet(f"{STYLE_HUD_LBL}; border: none; background: transparent;")
            v_val = QLabel(str(val))
            v_val.setAlignment(Qt.AlignCenter)
            v_val.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold; border: none; background: transparent;")
            v.addWidget(l_lbl)
            v.addWidget(v_val)
            if sub_label:
                s_lbl = QLabel(sub_label)
                s_lbl.setAlignment(Qt.AlignCenter)
                s_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 9px; font-style: italic; border: none; background: transparent;")
                v.addWidget(s_lbl)
            self.proj_layout.addLayout(v)

        add_stat("CALCULATED CURRENT WEIGHT", f"{curr_proj_w} LBS", T['PROTOCOL_GOLD'])
        self.proj_layout.addStretch()
        add_stat("TARGET GOAL", f"{goal_w} LBS", COLOR_ACCENT)
        self.proj_layout.addStretch()
        add_stat("ESTIMATED ARRIVAL", eta_str, status_color)

    def update_profile_field(self, key, value):
        try:
            if not value.strip(): return
            
            # Numeric conversion for specific fields
            if key in ["height", "weight", "weight_goal", "age"]:
                self.data["profile"][key] = float(value)
            else:
                self.data["profile"][key] = value
                
            save_health_data(self.username, self.fernet, self.data)
            self.refresh_dashboard()
        except ValueError:
            print(f"Invalid input for {key}")

    def refresh_dashboard(self):
        # 1. Existing UI refreshes
        self.setup_mini_calendar()
        self.refresh_machine_stats()
        self.refresh_daily_view()
        
        # 2. Fix the Weight Chart call
        if hasattr(self, 'weight_chart'):
            # Grab the profile dictionary from your data
            profile = self.data.get("profile", {})
            
            # Initialize the engine using that profile
            engine = HealthEngine(profile)
            
            # Pass all 3 required arguments: logs, profile, and engine
            self.weight_chart.update_chart(self.data["logs"], profile, engine)

    def handle_date_selection(self, new_date):
        self.selected_date = new_date
        self.refresh_dashboard()

    def change_month(self, delta_val):
        new_month = self.view_date.month + delta_val
        new_year = self.view_date.year
        if new_month > 12: new_month = 1; new_year += 1
        elif new_month < 1: new_month = 12; new_year -= 1
        self.view_date = date(new_year, new_month, 1)
        self.setup_mini_calendar()

    def setup_mini_calendar(self):
        self.cal_title.setText(self.view_date.strftime("%B %Y").upper())
        self.clear_layout(self.cal_grid)
        month_days = calendar.monthcalendar(self.view_date.year, self.view_date.month)
        for row, week in enumerate(month_days):
            for col, day in enumerate(week):
                if day == 0: continue
                this_date = date(self.view_date.year, self.view_date.month, day)
                has_data = this_date.strftime("%Y-%m-%d") in self.data["logs"]
                node = MiniDayNode(this_date, (this_date == self.selected_date), has_data)
                node.clicked.connect(self.handle_date_selection)
                self.cal_grid.addWidget(node, row, col)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout(): self.clear_layout(item.layout())