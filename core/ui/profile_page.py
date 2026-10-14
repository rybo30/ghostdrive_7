# [profile_page.py]

import json, os, time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QLabel, QPushButton, 
    QFormLayout, QFrame, QHBoxLayout, QScrollArea, QMessageBox, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from .style_config import (
    COLOR_FG, COLOR_ACCENT, STYLE_BUTTON, T, COLOR_TEXT_DIM, STYLE_INPUT,
    STYLE_SECTION_TITLE, STYLE_HUD_VAL, STYLE_HUD_LBL, STYLE_HEURISTIC_INPUT,
    STYLE_CARD_HEURISTIC
)

# Logic/Path Imports (restored)
from core.paths import USER_DATA, PROJECTS_DIR, INVENTORY_DIR, CORE_DIR, MODELS_DIR
from project_manager import list_project_files
from Everything_else.inventory_manager import list_inventory_sheets
from core.peers_manager import load_peers
from core.system_protocols import (
    get_disk_status, get_battery_status, get_primary_ip, get_system_uptime
)

class ProfilePage(QWidget):
    profile_updated = Signal()

    def __init__(self, username, fernet, passphrase=None): 
        super().__init__()
        self.username = username
        self.fernet = fernet
        self.passphrase = passphrase
        self.profile_path = os.path.join(USER_DATA, f"{username}_profile.enc")
        
        self.setup_ui()
        self.load_profile()  
        self.refresh_stats() 
        
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_live_metrics)
        self.refresh_timer.start(3000)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(25)

        # 1. HEADER
        header_row = QHBoxLayout()
        self.title_label = QLabel("OPERATOR OVERVIEW")
        self.title_label.setStyleSheet(f"color: {COLOR_FG}; font-size: 20px; font-weight: 900; letter-spacing: 3px;")
        
        self.uptime_label = QLabel("UPTIME: --")
        self.uptime_label.setStyleSheet(f"color: {COLOR_ACCENT}; font-family: 'Consolas'; font-size: 11px;")
        
        header_row.addWidget(self.title_label)
        header_row.addStretch()
        header_row.addWidget(self.uptime_label)
        main_layout.addLayout(header_row)

        # 2. SCROLL AREA
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setAttribute(Qt.WA_TranslucentBackground)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        scroll_style = f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:horizontal {{ height: 0px; }}
            QScrollBar:vertical {{
                border: none;
                background: rgba(0, 0, 0, 0.05);
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLOR_ACCENT};
                min-height: 30px;
                border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """
        scroll.setStyleSheet(scroll_style)
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        self.content_vbox = QVBoxLayout(content_widget)
        self.content_vbox.setContentsMargins(0, 0, 20, 0) 
        self.content_vbox.setSpacing(30)
        self.content_vbox.setSizeConstraint(QVBoxLayout.SetMinimumSize)

        # --- SECTION A: SYSTEM HUD (TOP) ---
        self.hud_card = QFrame()
        self.hud_card.setStyleSheet(f"background-color: {T['BG_PANEL']}; border: 1px solid {T['BORDER']}; border-radius: 12px;")
        hud_layout = QGridLayout(self.hud_card)
        hud_layout.setContentsMargins(25, 25, 25, 25)
        
        self.stat_labels = {}
        metrics = [
            ("Vault Files", "vault_count", 0, 0), ("AI Models", "pass_count", 0, 1),
            ("Active Projects", "proj_count", 0, 2), ("Data Sheets", "inv_count", 0, 3),
            ("Network", "net_count", 1, 0), ("Device Storage", "disk", 1, 1),
            ("Battery", "batt", 1, 2), ("Local IP", "ip", 1, 3)
        ]

        for name, key, r, c in metrics:
            vbox = QVBoxLayout()
            vbox.setSpacing(2)
            t_lbl = QLabel(name.upper()); t_lbl.setStyleSheet(STYLE_HUD_LBL)
            v_lbl = QLabel("0"); v_lbl.setStyleSheet(STYLE_HUD_VAL)
            vbox.addWidget(t_lbl); vbox.addWidget(v_lbl)
            self.stat_labels[key] = v_lbl
            hud_layout.addLayout(vbox, r, c)

        self.content_vbox.addWidget(self.hud_card)

        # --- SECTION B: SEGMENTED OPERATOR HEURISTICS ---
        self.heuristic_segments = {
            "THE WHO?": [
                ("callsign", "Callsign", "What should the AI Council call you?"),
                ("identity", "Core Identity", "Who are you at your core? (e.g. Architect, Father, Stoic)"),
                ("values", "Core Values", "What principles are non-negotiable for you?"),
                ("inner_circle", "Key Relationships", "VIPs in your life (e.g. Partner, Siblings, Pets)."),
                ("social_iq", "Social Style", "How do you interact with the world? (Introvert/Extrovert)")
            ],
            "THE WHAT?": [
                ("vocation", "Primary Profession", "What is your main trade or field of expertise?"),
                ("projects", "Active Objectives", "What are you working on right now?"),
                ("tech_stack", "Primary Toolkit", "What tools do you use daily?"),
                ("limitations", "Hard Constraints", "Physical, financial, or technical limits the AI must respect."),
                ("habits", "Daily Habits", "Recurring actions that define your day-to-day.")
            ],
            "THE WHERE?": [
                ("region", "Geographic Region", "What part of the world are you operating from?"),
                ("workspace", "Operational Environment", "Home office? Remote? Mobile/Field work?"),
                ("travel", "Frequent Locations", "Where do you go often or plan to move?"),
                ("digital_loc", "Digital Footprint", "Where do you live online? (e.g. GitHub, X, Forums)")
            ],
            "THE WHEN?": [
                ("peak_performance", "Focus Window", "When is your brain at 100%? (e.g. 10PM - 2AM)"),
                ("deadlines", "Critical Milestones", "What are the next major dates on your calendar?"),
                ("timeline", "Life Stage", "Are you starting a career? Scaling a business? Retiring?"),
                ("history", "Operational Past", "Relevant past experience that informs your current logic.")
            ],
            "THE WHY?": [
                ("motivations", "Core Drivers", "What truly wakes you up in the morning?"),
                ("fear", "Critical Fear", "What is the 'fail state' you avoid at all costs?"),
                ("ghostdrive_why", "Tool Purpose", "Why did you choose an encrypted tool like GhostDrive?"),
                ("victory_condition", "Target Outcome", "What does 'Winning' look like for you this year?")
            ],
            "THE HOW?": [
                ("logic", "Processing Style", "e.g. Big Picture, Step-by-step, or Visual."),
                ("learning_pref", "Knowledge Intake", "How do you best absorb complex data?"),
                ("decision_engine", "Decision Logic", "Data-driven, intuition, or risk-mitigation?"),
                ("tone_pref", "Interaction Protocol", "Direct/Tactical, Supportive, or Sarcastic/Cynical?")
            ]
        }

        self.h_inputs = {}

        # Dynamically create a card for each segment
        for segment_title, questions in self.heuristic_segments.items():
            segment_card = QFrame()
            segment_card.setStyleSheet(STYLE_CARD_HEURISTIC)
            card_layout = QVBoxLayout(segment_card)
            card_layout.setContentsMargins(30, 30, 30, 30)

            title_label = QLabel(segment_title)
            title_label.setStyleSheet(STYLE_SECTION_TITLE)
            card_layout.addWidget(title_label)
            card_layout.addSpacing(15)

            h_form = QFormLayout()
            h_form.setSpacing(15)
            h_form.setLabelAlignment(Qt.AlignLeft)
            h_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            h_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

            for key, label_text, placeholder in questions:
                self.h_inputs[key] = QLineEdit()
                w = self.h_inputs[key]
                w.setPlaceholderText(placeholder)
                w.setStyleSheet(STYLE_HEURISTIC_INPUT)
                label = QLabel(label_text.upper())
                label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px; font-weight: bold; border: none;")
                h_form.addRow(label, w)

            card_layout.addLayout(h_form)
            self.content_vbox.addWidget(segment_card)

        # --- SECTION C: PROTOCOL COMMAND TERMINAL ---
        self.terminal_card = QFrame()
        self.terminal_card.setStyleSheet(f"background-color: rgba(0, 0, 0, 0.3); border: 1px solid {T['BORDER']}; border-radius: 12px;")
        terminal_layout = QVBoxLayout(self.terminal_card)
        terminal_layout.setContentsMargins(30, 25, 30, 25)

        term_header = QLabel("ACTIVE PROTOCOL REGISTRY")
        term_header.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: bold; border: none; letter-spacing: 2px;")
        terminal_layout.addWidget(term_header)
        terminal_layout.addSpacing(20)

        command_list = [
            ("sweep", "Scans host for malicious software."),
            ("wipe", "Removes all temporary data from host computer."),
            ("shred", "Performs a 3-pass cryptographic overwrite on target files."),
            ("blackout_mode", "Terminates all active WiFi transmissions."),
            ("reconnect_wifi", "Restores connection to known secure Wi-Fi networks."),
            ("scan_networks", "Performs a reconnaissance scan of local frequencies."),
            ("status_report", "Generates a full audit of system and network telemetry."),
            ("soul_vent", "Registers an encrypted journal entry."),
            ("soul_vent_summon", "Decrypts and retrieves archived journal entries."),
            ("activate_big_brother", "Open up Chat GPT in default browser."),
            ("update", "Ensures GhostDrive software is fully up-to-date.")
        ]

        for cmd, desc in command_list:
            cmd_row = QHBoxLayout()
            cmd_row.setSpacing(15)
            cmd_lbl = QLabel(f"> {cmd}")
            cmd_lbl.setStyleSheet(f"color: {COLOR_FG}; font-family: 'Consolas', 'Monospace'; font-size: 18px; font-weight: bold; border: none;")
            dots = QLabel("................................................")
            dots.setStyleSheet(f"color: {T['BORDER']}; border: none; font-size: 10px;")
            dots.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            desc_lbl = QLabel(desc.upper())
            desc_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 12px; border: none; font-family: 'Consolas';")
            cmd_row.addWidget(cmd_lbl); cmd_row.addWidget(dots); cmd_row.addWidget(desc_lbl)
            terminal_layout.addLayout(cmd_row)
            terminal_layout.addSpacing(8)

        self.content_vbox.addWidget(self.terminal_card)

        # --- SECTION D: OPERATIONAL GUIDELINES ---
        self.guidelines_card = QFrame()
        self.guidelines_card.setStyleSheet(f"background-color: {T['BG_PANEL']}; border: 2px solid {T['BORDER']}; border-radius: 12px;")
        guide_main_layout = QVBoxLayout(self.guidelines_card)
        guide_main_layout.setContentsMargins(30, 25, 30, 30)

        header_lay = QHBoxLayout()
        guide_header = QLabel("PROGRAM INSTRUCTIONS")
        guide_header.setStyleSheet(f"color: {COLOR_FG}; font-size: 13px; font-weight: 900; border: none; letter-spacing: 2px;")
        accent_line = QFrame()
        accent_line.setFixedHeight(1)
        accent_line.setStyleSheet(f"background: {COLOR_ACCENT}; border: none;")
        header_lay.addWidget(guide_header); header_lay.addWidget(accent_line, 1)
        guide_main_layout.addLayout(header_lay)
        guide_main_layout.addSpacing(20)

        grid_lay = QGridLayout()
        grid_lay.setSpacing(25)
        guidelines = [
            ("FILE VAULT", "Store any kind of file with top-tier, AES-256 encryption security. Your file names are automatically scrambled so no one else can read them. This keeps your private data completely hidden from prying eyes."),
            ("PASSWORDS", "Keep all of your passwords safe, organized, and easily accessible. Your data stays entirely on your own device and is never saved to the internet. This ensures that you are the only person who can ever reach them."),
            ("PROJECTS", "Track your daily tasks and big goals using a clean, digital scrum board. You can easily attach your secured vault files directly to any project. It is the perfect way to keep projects organized and on-schedule."),
            ("DATA", "Create custom spreadsheets to keep track of your personal belongings or business inventory. You can fully customize the categories and labels to fit whatever you are tracking. It makes managing your assets simple and flexible."),
            ("HEALTH", "This is a private space to log your daily meals, track your nutrition, and follow your fitness goals. Safely monitor your physical progress over time without sharing your health data with outside apps. It is your personal wellness journal."),
            ("AI COUNCIL", "Chat with 20+ AI Models at once! Multi-Model Reasoning incorporates all AI experts to offer contrasting perspectives and provide the user with a unique answer. Or select a specific AI Expert and chat directly. All offline, no internet needed."),
            ("MEETINGS", "Record your live meetings and instantly turn the audio into written text and AI analysis. Use offline AI Models to create Meeting Notes that stay encrypted and never touch the cloud. Your private conversations never leave the room."),
            ("ARCADE", "Take a quick break and play a collection of built-in, community-made games. Open source favorites like SuperTuxKart and BlockOut, and originals like Boomers vs Zoomers, and more to come!"),
            ("CODING", "The ultimate offline Coding AI Assistant. Drop in your source file, describe the problem or error message, and then receive a fully written, corrected software script."),
            ("SIGNATURE", "This shows your unique digital footprint within the app. These questions are used to provide insight to the AI Council and are used in the AI responses.")
        ]

        row, col = 0, 0
        for feature, instruction in guidelines:
            feat_container = QFrame()
            feat_container.setStyleSheet("border: none; background: transparent;")
            v_lay = QVBoxLayout(feat_container)
            v_lay.setContentsMargins(0,0,0,0)
            v_lay.setSpacing(4)
            f_label = QLabel(f"{feature}")
            f_label.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 800; font-size: 11px; font-family: 'Consolas';")
            i_label = QLabel(instruction)
            i_label.setWordWrap(True)
            i_label.setStyleSheet(f"color: {COLOR_FG}; font-size: 11px; line-height: 15px; opacity: 0.8;")
            v_lay.addWidget(f_label); v_lay.addWidget(i_label)
            grid_lay.addWidget(feat_container, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1

        guide_main_layout.addLayout(grid_lay)
        self.content_vbox.addWidget(self.guidelines_card)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # FOOTER
        footer = QHBoxLayout()
        self.save_btn = QPushButton("INITIALIZE SYSTEM COMMIT")
        self.save_btn.setFixedSize(280, 50)
        self.save_btn.setStyleSheet(STYLE_BUTTON)
        self.save_btn.clicked.connect(self.save_profile)
        footer.addStretch()
        footer.addWidget(self.save_btn)
        main_layout.addLayout(footer)





    # --- HELPER & REFRESH LOGIC ---
    def refresh_live_metrics(self):
        try:
            disk = get_disk_status()
            if "disk" in self.stat_labels:
                self.stat_labels["disk"].setText(f"{disk.get('percent_used', 0)}% USED")
            batt_info = get_battery_status()
            batt_val = batt_info.split("(")[0].strip() if batt_info else "N/A"
            if "batt" in self.stat_labels: self.stat_labels["batt"].setText(batt_val)
            if "ip" in self.stat_labels: self.stat_labels["ip"].setText(get_primary_ip())
            self.uptime_label.setText(f"UPTIME: {get_system_uptime().upper()}")
        except Exception as e: print(f"HUD Error: {e}")

    def refresh_stats(self):
        try:
            if os.path.exists(USER_DATA):
                v_files = [f for f in os.listdir(USER_DATA) if f.endswith('.dat')]
                self.stat_labels["vault_count"].setText(str(len(v_files)))
            

            if os.path.exists(MODELS_DIR):
                # We create a tuple of the extensions we want to track
                valid_extensions = ('.gguf', '.pt')
                m_files = [f for f in os.listdir(MODELS_DIR) if f.lower().endswith(valid_extensions)]
                self.stat_labels["pass_count"].setText(str(len(m_files)))


            self.stat_labels["proj_count"].setText(str(len(list_project_files(self.username))))
            self.stat_labels["inv_count"].setText(str(len(list_inventory_sheets(self.username))))
            self.stat_labels["net_count"].setText(str(len(load_peers(self.username, self.fernet))))
        except Exception as e: 
            print(f"Stats Error: {e}")

    def save_profile(self):
        data = {"heuristics": {k: w.text() for k, w in self.h_inputs.items()}}
        try:
            raw_json = json.dumps(data).encode()
            encrypted = self.fernet.encrypt(raw_json)
            with open(self.profile_path, "wb") as f: f.write(encrypted)
            self.save_btn.setText("SYNC COMPLETE")
            self.profile_updated.emit()
            QTimer.singleShot(2000, lambda: self.save_btn.setText("INITIALIZE SYSTEM COMMIT"))
        except Exception as e: QMessageBox.critical(self, "Error", f"Link Failed: {e}")

    def load_profile(self):
        if not os.path.exists(self.profile_path): return
        try:
            with open(self.profile_path, "rb") as f:
                decrypted = self.fernet.decrypt(f.read())
                data = json.loads(decrypted)
                heur = data.get("heuristics", {})
                for k, w in self.h_inputs.items(): w.setText(heur.get(k, ""))
        except Exception as e: print(f"Load Error: {e}")