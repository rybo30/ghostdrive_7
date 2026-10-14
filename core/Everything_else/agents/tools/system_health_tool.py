# [system_health_tool.py]

import platform
import psutil
from typing import Dict, Any

TOOL_SPEC = {
    "name": "system_health_tool",
    "description": "Retrieves real-time CPU usage, RAM stats, disk capacity, and operating system info from the host machine.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

def execute(**kwargs) -> str:
    """Standard entrypoint called by tool_runner.py."""
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=True)
        
        memory = psutil.virtual_memory()
        ram_total_gb = round(memory.total / (1024 ** 3), 2)
        ram_available_gb = round(memory.available / (1024 ** 3), 2)
        ram_percent = memory.percent

        disk = psutil.disk_usage('/')
        disk_total_gb = round(disk.total / (1024 ** 3), 2)
        disk_free_gb = round(disk.free / (1024 ** 3), 2)
        disk_percent = disk.percent

        os_info = f"{platform.system()} {platform.release()} ({platform.architecture()[0]})"

        report = [
            "=== HOST SYSTEM HEALTH REPORT ===",
            f"OS: {os_info}",
            f"CPU Usage: {cpu_usage}% ({cpu_count} Logical Cores)",
            f"RAM: {ram_percent}% used ({ram_available_gb} GB available / {ram_total_gb} GB total)",
            f"Disk Storage: {disk_percent}% used ({disk_free_gb} GB free / {disk_total_gb} GB total)",
            "================================="
        ]
        return "\n".join(report)
    except Exception as e:
        return f"System Health Check Error: {str(e)}"