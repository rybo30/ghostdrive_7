# =============================================================================
# system_protocols.py — Cross-Platform System Monitoring & Control
# Supports: Windows 10+, Linux (Desktop & Raspberry Pi)
# =============================================================================
#
# System protocols for GhostDrive operator interface.
# These provide system status, health monitoring, and control functions
# that will be essential for robot command & control operations.
#
# =============================================================================

import os
import socket
import getpass
import datetime
import webbrowser
from typing import Optional, Dict, Any

import psutil

from .platform_utils import (
    get_os_type, 
    OSType, 
    is_raspberry_pi,
    has_nvidia_gpu,
    get_gpu_info,
    get_platform_info
)

# =============================================================================
# System Status
# =============================================================================

def get_system_uptime() -> str:
    """Get system uptime as a human-readable string."""
    try:
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        
        return " ".join(parts)
    except Exception as e:
        return f"Unknown (error: {e})"


def get_battery_status() -> str:
    """Get battery status (or indicate if no battery)."""
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return "N/A (no battery / desktop system)"
        
        percent = battery.percent
        plugged = battery.power_plugged
        
        status = f"{percent}%"
        if plugged:
            status += " (charging)" if percent < 100 else " (fully charged)"
        else:
            # Estimate time remaining
            secs_left = battery.secsleft
            if secs_left > 0:
                hours, remainder = divmod(secs_left, 3600)
                minutes, _ = divmod(remainder, 60)
                status += f" ({int(hours)}h {int(minutes)}m remaining)"
            else:
                status += " (on battery)"
        
        return status
    except Exception as e:
        return f"Unknown (error: {e})"


def get_memory_status() -> Dict[str, Any]:
    """Get memory usage statistics."""
    try:
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent_used": mem.percent,
        }
    except Exception:
        return {"error": "Could not get memory info"}


def get_disk_status(path: str = "/") -> Dict[str, Any]:
    """Get disk usage for a specific path."""
    try:
        # On Windows, default to C:
        if get_os_type() == OSType.WINDOWS and path == "/":
            path = "C:\\"
        
        disk = psutil.disk_usage(path)
        return {
            "path": path,
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent_used": round(disk.percent, 1),
        }
    except Exception as e:
        return {"error": str(e)}


def get_cpu_status() -> Dict[str, Any]:
    """Get CPU usage and info."""
    try:
        return {
            "percent": psutil.cpu_percent(interval=0.5),
            "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(logical=True),
            "frequency_mhz": round(psutil.cpu_freq().current, 0) if psutil.cpu_freq() else "N/A",
        }
    except Exception as e:
        return {"error": str(e)}


def get_network_interfaces() -> Dict[str, str]:
    """Get IP addresses for all network interfaces."""
    interfaces = {}
    try:
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    interfaces[name] = addr.address
    except Exception:
        pass
    return interfaces


def get_primary_ip() -> str:
    """Get the primary IP address of this machine."""
    try:
        # Create a socket to determine the outbound IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Doesn't actually send data
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback method
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "Unknown"


def get_hostname() -> str:
    """Get the system hostname."""
    try:
        return socket.gethostname()
    except Exception:
        return "Unknown"


def get_current_user() -> str:
    """Get the current logged-in user."""
    try:
        return getpass.getuser()
    except Exception:
        return "Unknown"


# =============================================================================
# Temperature Monitoring (especially for Raspberry Pi)
# =============================================================================

def get_cpu_temperature() -> Optional[float]:
    """
    Get CPU temperature in Celsius.
    Works on Linux (especially Raspberry Pi). Limited support on Windows.
    """
    os_type = get_os_type()
    
    if os_type == OSType.LINUX:
        # Try thermal zone (common on Linux)
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read().strip()) / 1000.0
                return round(temp, 1)
        except FileNotFoundError:
            pass
        
        # Try Raspberry Pi specific path
        if is_raspberry_pi():
            try:
                import subprocess
                result = subprocess.run(
                    ["vcgencmd", "measure_temp"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Output format: temp=XX.X'C
                temp_str = result.stdout.strip()
                temp = float(temp_str.split("=")[1].replace("'C", ""))
                return round(temp, 1)
            except Exception:
                pass
        
        # Try psutil sensors
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current > 0:
                            return round(entry.current, 1)
        except Exception:
            pass
    
    elif os_type == OSType.WINDOWS:
        # Windows requires WMI or specific drivers, not easily available
        # Could implement with wmi package if needed
        pass
    
    return None


# =============================================================================
# Comprehensive Status Report
# =============================================================================

def status_report() -> str:
    """
    Generate a comprehensive system status report.
    
    This is the main status command for the GhostDrive operator interface.
    Returns a formatted string with all relevant system information.
    """
    try:
        platform_info = get_platform_info()
        memory = get_memory_status()
        disk = get_disk_status()
        cpu = get_cpu_status()
        gpu = get_gpu_info()
        temp = get_cpu_temperature()
        
        # Build the report
        lines = [
            "🌐 GHOSTDRIVE SYSTEM STATUS",
            "=" * 40,
            "",
            "📋 SYSTEM INFO",
            f"  • Hostname:     {get_hostname()}",
            f"  • User:         {get_current_user()}",
            f"  • OS:           {platform_info['platform']} {platform_info['platform_release']}",
            f"  • Architecture: {platform_info['architecture']}",
            f"  • Uptime:       {get_system_uptime()}",
        ]
        
        if platform_info.get('is_raspberry_pi'):
            lines.append("  • Hardware:     🍓 Raspberry Pi")
        
        lines.extend([
            "",
            "🔋 POWER",
            f"  • Battery:      {get_battery_status()}",
        ])
        
        lines.extend([
            "",
            "💻 CPU",
            f"  • Usage:        {cpu.get('percent', 'N/A')}%",
            f"  • Cores:        {cpu.get('cores_physical', '?')} physical / {cpu.get('cores_logical', '?')} logical",
            f"  • Frequency:    {cpu.get('frequency_mhz', 'N/A')} MHz",
        ])
        
        if temp is not None:
            lines.append(f"  • Temperature:  {temp}°C")
        
        lines.extend([
            "",
            "🧠 MEMORY",
            f"  • Used:         {memory.get('used_gb', '?')} / {memory.get('total_gb', '?')} GB ({memory.get('percent_used', '?')}%)",
            f"  • Available:    {memory.get('available_gb', '?')} GB",
        ])
        
        lines.extend([
            "",
            "💾 STORAGE",
            f"  • Used:         {disk.get('used_gb', '?')} / {disk.get('total_gb', '?')} GB ({disk.get('percent_used', '?')}%)",
            f"  • Free:         {disk.get('free_gb', '?')} GB",
        ])
        
        if gpu:
            lines.extend([
                "",
                "🎮 GPU",
                f"  • Model:        {gpu.get('name', 'Unknown')}",
                f"  • VRAM:         {gpu.get('memory_mb', '?')} MB",
                f"  • Driver:       {gpu.get('driver_version', 'Unknown')}",
            ])
        else:
            lines.extend([
                "",
                "🎮 GPU",
                "  • No NVIDIA GPU detected (CPU inference mode)",
            ])
        
        lines.extend([
            "",
            "🌐 NETWORK",
            f"  • Primary IP:   {get_primary_ip()}",
        ])
        
        interfaces = get_network_interfaces()
        for name, ip in interfaces.items():
            if ip != "127.0.0.1":
                lines.append(f"  • {name}: {ip}")
        
        lines.extend([
            "",
            "=" * 40,
        ])
        
        # Convert the list of lines into a single string
        final_output = "\n".join(lines)

        # Tactical Formatting for HTML Display
        # 1. Replace headers with Bold + Underline
        headers = ["📋 SYSTEM INFO", "🔋 POWER", "💻 CPU", "🧠 MEMORY", "💾 STORAGE", "🎮 GPU", "🌐 NETWORK"]
        for header in headers:
            final_output = final_output.replace(header, f"<br><b>{header}</b><br>"+ "—"*20)

        # 2. Turn newlines into HTML breaks
        final_output = final_output.replace("\n", "<br>")

        # 3. Add non-breaking spaces to preserve the indent of the bullets
        final_output = final_output.replace("  •", "&nbsp;&nbsp;[>]")

        return f"<div style='font-family: monospace; line-height: 1.4;'>{final_output}</div>"
        
    except Exception as e:
        return f"❌ Status report failed: {e}"


# =============================================================================
# Quick Health Check (for robot heartbeats)
# =============================================================================

def health_check() -> Dict[str, Any]:
    """
    Quick health check returning structured data.
    Useful for robot-to-controller heartbeat messages.
    """
    try:
        cpu = get_cpu_status()
        memory = get_memory_status()
        temp = get_cpu_temperature()
        
        health = {
            "status": "OK",
            "timestamp": datetime.datetime.now().isoformat(),
            "hostname": get_hostname(),
            "ip": get_primary_ip(),
            "cpu_percent": cpu.get("percent", 0),
            "memory_percent": memory.get("percent_used", 0),
            "temperature_c": temp,
            "is_raspberry_pi": is_raspberry_pi(),
        }
        
        # Set warning/critical status based on thresholds
        if cpu.get("percent", 0) > 90 or memory.get("percent_used", 0) > 90:
            health["status"] = "WARNING"
        if temp and temp > 80:
            health["status"] = "CRITICAL"
        
        return health
        
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat(),
        }


# =============================================================================
# Utility Commands
# =============================================================================

def open_browser(url: str = "https://duckduckgo.com") -> str:
    """Open a URL in the default web browser."""
    try:
        webbrowser.open(url)
        return f"🌐 Opened browser: {url}"
    except Exception as e:
        return f"❌ Failed to open browser: {e}"


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    print(status_report())
    print("\n\nHealth Check:")
    import json
    print(json.dumps(health_check(), indent=2))
