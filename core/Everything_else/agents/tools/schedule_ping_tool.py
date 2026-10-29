# [schedule_ping_tool.py]

import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from core.paths import HOST_HIDDEN_DIR

TOOL_SPEC = {
    "name": "schedule_ping_tool",
    "description": "Schedules a future proactive ping or reminder for the user. Can be one-time or recurring.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["schedule", "list", "cancel"],
                "description": "Action to perform: 'schedule' a new ping, 'list' active pings, or 'cancel' a ping."
            },
            "ping_time": {
                "type": "string",
                "description": "Exact timestamp for the ping in ISO format (YYYY-MM-DD HH:MM:SS) or relative string like 'in 2 hours' or 'tomorrow at 9am'."
            },
            "message": {
                "type": "string",
                "description": "The specific topic, prompt, or reminder for the agent to check during the ping."
            },
            "recurring": {
                "type": "boolean",
                "description": "True if the ping should repeat daily."
            }
        },
        "required": ["action"]
    }
}

def _get_db():
    db_path = Path.home() / ".ghostdrive" / "scheduled_pings.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_at TIMESTAMP,
            message TEXT,
            recurring INTEGER DEFAULT 0,
            status TEXT DEFAULT 'PENDING'
        )
    """)
    conn.commit()
    return conn

def schedule_ping(message: str, ping_time: str, recurring: bool = False) -> str:
    conn = _get_db()
    # Simple relative or absolute parsing logic can be added here
    # For now, store the raw target time string and message
    conn.execute("INSERT INTO pings (trigger_at, message, recurring, status) VALUES (?, ?, ?, 'PENDING')",
                 (ping_time, message, 1 if recurring else 0))
    conn.commit()
    conn.close()
    return f"Successfully scheduled proactive ping for '{ping_time}': {message}"

def list_pings() -> str:
    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, trigger_at, message, recurring FROM pings WHERE status = 'PENDING'")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return "No scheduled pings found."
    output = ["Scheduled Pings:"]
    for r in rows:
        output.append(f"- ID {r[0]}: At {r[1]} | Message: {r[2]} (Recurring: {r[3]})")
    return "\n".join(output)

def run(action: str, ping_time: str = "", message: str = "", recurring: bool = False, **kwargs) -> str:
    action = action.lower()
    if action == "schedule":
        return schedule_ping(message=message, ping_time=ping_time, recurring=recurring)
    elif action == "list":
        return list_pings()
    else:
        return f"Unknown action '{action}'."