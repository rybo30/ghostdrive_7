# [scheduled_ping_tool.py]

import os
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

TOOL_SPEC = {
    "name": "scheduled_ping_tool",
    "description": (
        "Schedules autonomous agent execution cycles to work on long-term projects, "
        "check stocks, fetch news, or advance specific user goals proactively."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "delete"],
                "description": "Action to perform: 'create' a new scheduled ping, 'list' active schedules, or 'delete' a schedule by ID."
            },
            "topic": {
                "type": "string",
                "enum": ["project_advancement", "stock_market", "news_digest", "weather", "sports_news", "rss_feed", "media_digest", "custom_query"],
                "description": "Category of information to compile for the ping."
            },
            "custom_query": {
                "type": "string",
                "description": "Required if topic is 'custom_query', 'rss_feed', 'weather', or 'project_advancement'."
            },
            "interval_hours": {
                "type": "integer",
                "description": "How often to send the ping in hours (e.g., 4 for 4 times daily, 8, 24 for daily). Default is 24."
            },
            "target_time": {
                "type": "string",
                "description": "Preferred time of day in 24-hour format HH:MM (e.g., '08:00', '18:30')."
            },
            "total_pings": {
                "type": "integer",
                "description": "Maximum number of pings to send before expiring. Omit or set to -1 for indefinite."
            },
            "schedule_id": {
                "type": "string",
                "description": "Required only when action is 'delete'. The ID of the schedule to remove."
            }
        },
        "required": ["action"]
    }
}

def _get_schedules_file_path() -> str:
    try:
        from core.paths import AGENT_RUNTIME_DIR
        os.makedirs(AGENT_RUNTIME_DIR, exist_ok=True)
        return os.path.join(AGENT_RUNTIME_DIR, "scheduled_jobs.json")
    except Exception:
        fallback_dir = os.path.join(os.expanduser("~"), ".ghostdrive")
        os.makedirs(fallback_dir, exist_ok=True)
        return os.path.join(fallback_dir, "scheduled_jobs.json")


def _load_schedules() -> List[Dict[str, Any]]:
    path = _get_schedules_file_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_schedules(schedules: List[Dict[str, Any]]):
    path = _get_schedules_file_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schedules, f, indent=2)


def _calculate_next_run_timestamp(target_time_str: str) -> float:
    """Calculates the exact epoch timestamp for the next occurrence of target HH:MM time."""
    now = datetime.now()
    try:
        target_time = datetime.strptime(target_time_str.strip(), "%H:%M").time()
    except Exception:
        target_time = datetime.strptime("08:00", "%H:%M").time()

    next_run = datetime.combine(now.date(), target_time)
    if next_run <= now:
        next_run += timedelta(days=1)

    return next_run.timestamp()


def execute(**kwargs) -> str:
    action = str(kwargs.get("action", "create")).lower().strip()
    
    if action == "list":
        schedules = _load_schedules()
        if not schedules:
            return "No scheduled pings active at this time."
        
        report = ["=== ACTIVE SCHEDULED PINGS ==="]
        for item in schedules:
            pings_info = "Indefinite" if item.get("total_pings", -1) in [-1, "-1"] else item.get("total_pings")
            pings_sent = item.get("pings_sent", 0)
            next_ts = item.get("next_run_timestamp", 0)
            next_str = datetime.fromtimestamp(next_ts).strftime("%Y-%m-%d %H:%M") if next_ts else "Pending"

            report.append(
                f"• ID: {item['id']} | Topic: {item['topic'].upper()}\n"
                f"  Interval: Every {item['interval_hours']}h | Target Time: {item.get('target_time', '08:00')}\n"
                f"  Next Execution: {next_str} | Sent: {pings_sent} / {pings_info}"
            )
            if item.get("custom_query"):
                report.append(f"  Query/Location: {item['custom_query']}")
        return "\n".join(report)

    elif action == "delete":
        sched_id = str(kwargs.get("schedule_id", "")).strip()
        if not sched_id:
            return "Error: 'schedule_id' is required to delete a scheduled ping."
        
        schedules = _load_schedules()
        filtered = [s for s in schedules if str(s.get("id")) != sched_id]
        if len(filtered) == len(schedules):
            return f"Schedule with ID '{sched_id}' was not found."
        
        _save_schedules(filtered)
        return f"Successfully deleted scheduled ping '{sched_id}'."

    elif action == "create":
        topic = str(kwargs.get("topic", "")).lower().strip()
        if not topic:
            return "Error: 'topic' is required when creating a scheduled ping."

        custom_query = str(kwargs.get("custom_query", "")).strip()
        if topic in ["custom_query", "weather", "rss_feed", "project_advancement"] and not custom_query:
            return f"Error: 'custom_query' parameter is required for topic '{topic}'."

        try:
            interval_hours = max(1, int(kwargs.get("interval_hours", 24)))
        except (ValueError, TypeError):
            interval_hours = 24

        try:
            total_pings = int(kwargs.get("total_pings", -1))
        except (ValueError, TypeError):
            total_pings = -1

        target_time = str(kwargs.get("target_time", "08:00")).strip()
        next_run_ts = _calculate_next_run_timestamp(target_time)

        job_id = str(uuid.uuid4())[:8]
        new_job = {
            "id": job_id,
            "topic": topic,
            "custom_query": custom_query,
            "interval_hours": interval_hours,
            "target_time": target_time,
            "total_pings": total_pings,
            "pings_sent": 0,
            "last_run_timestamp": 0,
            "next_run_timestamp": next_run_ts
        }

        schedules = _load_schedules()
        schedules.append(new_job)
        _save_schedules(schedules)

        query_info = f" ({custom_query})" if custom_query else ""
        next_date_str = datetime.fromtimestamp(next_run_ts).strftime("%Y-%m-%d %H:%M")
        return (
            f"Successfully scheduled '{topic.upper()}' ping{query_info}.\n"
            f"• Schedule ID: {job_id}\n"
            f"• Frequency: Every {new_job['interval_hours']} hour(s)\n"
            f"• Target Daily Time: {new_job['target_time']}\n"
            f"• First Scheduled Execution: {next_date_str}\n"
            f"• Max Pings: {'Unlimited' if new_job['total_pings'] == -1 else new_job['total_pings']}"
        )

    return f"Error: Unknown action '{action}'."
