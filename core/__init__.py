# =============================================================================
# GhostDrive Core Module
# Cross-platform utilities for Windows + Linux
# =============================================================================
#
# This module provides cross-platform abstractions for:
# - OS/Hardware detection
# - Network control (WiFi)
# - System monitoring
#
# Your original encryption (filecrypt.py, ghostvault.py) stays in Everything_else/
# =============================================================================

from .platform_utils import (
    OSType,
    LinuxDistro,
    get_os_type,
    get_linux_distro,
    is_raspberry_pi,
    get_platform_info,
    has_nvidia_gpu,
    get_gpu_info,
    get_recommended_gpu_layers,
    get_data_directory,
    get_config_directory,
    print_system_summary,
    check_command_exists,
)

from .network_protocols import (
    disconnect_wifi,
    reconnect_wifi,
    scan_networks,
    get_connection_status,
    blackout_mode,
    secure_reconnect,
)

from .system_protocols import (
    status_report,
    health_check,
    get_system_uptime,
    get_battery_status,
    get_memory_status,
    get_disk_status,
    get_cpu_status,
    get_cpu_temperature,
    get_network_interfaces,
    get_primary_ip,
    get_hostname,
    get_current_user,
    open_browser,
)

__all__ = [
    # Platform detection
    "OSType",
    "LinuxDistro", 
    "get_os_type",
    "get_linux_distro",
    "is_raspberry_pi",
    "get_platform_info",
    "has_nvidia_gpu",
    "get_gpu_info",
    "get_recommended_gpu_layers",
    "get_data_directory",
    "get_config_directory",
    "print_system_summary",
    "check_command_exists",
    
    # Network protocols
    "disconnect_wifi",
    "reconnect_wifi",
    "scan_networks",
    "get_connection_status",
    "blackout_mode",
    "secure_reconnect",
    
    # System protocols
    "status_report",
    "health_check",
    "get_system_uptime",
    "get_battery_status",
    "get_memory_status",
    "get_disk_status",
    "get_cpu_status",
    "get_cpu_temperature",
    "get_network_interfaces",
    "get_primary_ip",
    "get_hostname",
    "get_current_user",
    "open_browser",
]
