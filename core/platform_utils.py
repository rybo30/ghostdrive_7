# =============================================================================
# platform_utils.py — Cross-Platform Detection & Abstraction Layer
# Supports: Windows 10+, Linux (Desktop & Raspberry Pi), macOS
# =============================================================================

import platform
import subprocess
import shutil
from enum import Enum
from typing import Optional, Tuple, List

class OSType(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNSUPPORTED = "unsupported"

class LinuxDistro(Enum):
    DEBIAN = "debian"      # Includes Ubuntu, Raspberry Pi OS
    FEDORA = "fedora"      # Includes RHEL, CentOS
    ARCH = "arch"
    UNKNOWN = "unknown"

# =============================================================================
# OS Detection
# =============================================================================

def get_os_type() -> OSType:
    """Detect the current operating system."""
    system = platform.system().lower()
    if system == "windows":
        return OSType.WINDOWS
    elif system == "linux":
        return OSType.LINUX
    elif system == "darwin":
        return OSType.MACOS
    else:
        return OSType.UNSUPPORTED

def get_linux_distro() -> LinuxDistro:
    """Detect Linux distribution family (for package manager differences)."""
    if get_os_type() != OSType.LINUX:
        return LinuxDistro.UNKNOWN
    
    try:
        with open("/etc/os-release", "r") as f:
            content = f.read().lower()
            if "debian" in content or "ubuntu" in content or "raspbian" in content:
                return LinuxDistro.DEBIAN
            elif "fedora" in content or "rhel" in content or "centos" in content:
                return LinuxDistro.FEDORA
            elif "arch" in content:
                return LinuxDistro.ARCH
    except FileNotFoundError:
        pass
    
    return LinuxDistro.UNKNOWN

def is_raspberry_pi() -> bool:
    """Check if running on Raspberry Pi hardware."""
    if get_os_type() != OSType.LINUX:
        return False
    
    try:
        with open("/proc/cpuinfo", "r") as f:
            return "raspberry" in f.read().lower()
    except FileNotFoundError:
        return False

def get_platform_info() -> dict:
    """Get comprehensive platform information."""
    os_type = get_os_type()
    
    info = {
        "os_type": os_type.value,
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "is_raspberry_pi": is_raspberry_pi(),
    }
    
    if os_type == OSType.LINUX:
        info["linux_distro"] = get_linux_distro().value
    
    return info

# =============================================================================
# GPU Detection (for LLM acceleration)
# =============================================================================

def has_nvidia_gpu() -> bool:
    """Check if NVIDIA GPU is available (for CUDA acceleration)."""
    os_type = get_os_type()
    
    if os_type == OSType.WINDOWS:
        # Check for nvidia-smi
        return shutil.which("nvidia-smi") is not None
    
    elif os_type == OSType.LINUX:
        # Check for nvidia-smi or /dev/nvidia0
        if shutil.which("nvidia-smi"):
            return True
        try:
            import os
            return os.path.exists("/dev/nvidia0")
        except:
            return False
    
    return False

def _sysctl(name: str) -> Optional[str]:
    try:
        result = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None

def get_apple_silicon_gpu_info() -> Optional[dict]:
    """
    GPU info for Apple Silicon Macs, which llama.cpp drives through Metal.
    The GPU shares unified memory with the CPU, so memory_mb is total system RAM.
    Intel Macs return None: llama.cpp's Metal path isn't worthwhile on their GPUs.
    """
    if get_os_type() != OSType.MACOS:
        return None
    if platform.machine() != "arm64" and _sysctl("hw.optional.arm64") != "1":
        return None  # Intel Mac (also covers Python running under Rosetta)

    memsize = _sysctl("hw.memsize")
    return {
        "name": _sysctl("machdep.cpu.brand_string") or "Apple Silicon",
        "memory_mb": int(memsize) // (1024 * 1024) if memsize and memsize.isdigit() else 0,
        "driver_version": "Metal",
        "backend": "metal",
    }

def get_gpu_info() -> Optional[dict]:
    """Get GPU information for an NVIDIA GPU (CUDA) or Apple Silicon (Metal), if present."""
    if not has_nvidia_gpu():
        return get_apple_silicon_gpu_info()

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return {
                "name": parts[0] if len(parts) > 0 else "Unknown",
                "memory_mb": int(parts[1]) if len(parts) > 1 else 0,
                "driver_version": parts[2] if len(parts) > 2 else "Unknown",
                "backend": "cuda",
            }
    except Exception:
        pass

    return {"name": "NVIDIA GPU (details unavailable)", "memory_mb": 0, "driver_version": "Unknown", "backend": "cuda"}

def get_recommended_gpu_layers(gpu_info: Optional[dict] = None) -> int:
    """
    Recommend number of GPU layers for llama.cpp based on available VRAM.
    Returns -1 for 'all layers on GPU', 0 for 'CPU only'.
    """
    if gpu_info is None:
        gpu_info = get_gpu_info()

    if not gpu_info:
        return 0  # CPU only

    if gpu_info.get("backend") == "metal":
        # Unified memory: Metal can use most of system RAM, so offload every layer.
        # Below 8 GB a 7B model plus the OS doesn't reliably fit; stay on CPU.
        return -1 if gpu_info.get("memory_mb", 0) >= 8000 else 0

    vram_mb = gpu_info.get("memory_mb", 0)
    
    if vram_mb >= 24000:    # 24GB+ (RTX 4090, etc.)
        return -1           # All layers on GPU
    elif vram_mb >= 12000:  # 12GB+ (RTX 3080, etc.)
        return 35
    elif vram_mb >= 8000:   # 8GB (RTX 3070, etc.)
        return 28
    elif vram_mb >= 6000:   # 6GB (RTX 2060, etc.)
        return 20
    elif vram_mb >= 4000:   # 4GB
        return 12
    else:
        return 0            # CPU only for low VRAM

_DEFAULT_GPU_LAYERS = None

def resolve_gpu_layers(configured, offload_supported: bool, gpu_info: Optional[dict] = None) -> int:
    """
    n_gpu_layers to pass to llama.cpp for one model.

    - An explicit n_gpu_layers in models.yaml always wins (0 forces CPU).
    - Otherwise use the hardware recommendation, but only if this llama.cpp
      build can offload at all (a CPU-only wheel can't, whatever the hardware).
    The hardware probe runs once per process and is cached.
    """
    global _DEFAULT_GPU_LAYERS
    if configured is not None:
        try:
            return int(configured)
        except (TypeError, ValueError):
            pass
    if not offload_supported:
        return 0
    if gpu_info is not None:
        return get_recommended_gpu_layers(gpu_info)
    if _DEFAULT_GPU_LAYERS is None:
        _DEFAULT_GPU_LAYERS = get_recommended_gpu_layers()
    return _DEFAULT_GPU_LAYERS

# =============================================================================
# Command Availability Checks
# =============================================================================

def check_command_exists(command: str) -> bool:
    """Check if a command-line tool is available."""
    return shutil.which(command) is not None

def get_network_manager() -> Optional[str]:
    """
    Detect which network manager is available on Linux.
    Returns: 'nmcli', 'iwctl', 'wpa_cli', or None
    """
    if get_os_type() != OSType.LINUX:
        return None
    
    # Preference order: NetworkManager > iwd > wpa_supplicant
    if check_command_exists("nmcli"):
        return "nmcli"
    elif check_command_exists("iwctl"):
        return "iwctl"
    elif check_command_exists("wpa_cli"):
        return "wpa_cli"
    
    return None

# =============================================================================
# Path Utilities (cross-platform safe paths)
# =============================================================================

def get_data_directory() -> str:
    """Get the appropriate data directory for the current platform."""
    import os
    
    os_type = get_os_type()
    
    if os_type == OSType.WINDOWS:
        # Use AppData/Local on Windows
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "GhostDrive")
    
    elif os_type == OSType.LINUX:
        # Use ~/.local/share on Linux (XDG spec)
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        return os.path.join(base, "ghostdrive")
    
    else:
        # Fallback to home directory
        return os.path.join(os.path.expanduser("~"), ".ghostdrive")

def get_config_directory() -> str:
    """Get the appropriate config directory for the current platform."""
    import os
    
    os_type = get_os_type()
    
    if os_type == OSType.WINDOWS:
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "GhostDrive", "config")
    
    elif os_type == OSType.LINUX:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return os.path.join(base, "ghostdrive")
    
    else:
        return os.path.join(os.path.expanduser("~"), ".ghostdrive", "config")

# =============================================================================
# Quick System Summary (for debugging/status reports)
# =============================================================================

def print_system_summary():
    """Print a summary of the detected system configuration."""
    info = get_platform_info()
    gpu = get_gpu_info()
    
    print("=" * 50)
    print("🖥️  GHOSTDRIVE SYSTEM DETECTION")
    print("=" * 50)
    print(f"OS Type:        {info['os_type'].upper()}")
    print(f"Platform:       {info['platform']} {info['platform_release']}")
    print(f"Architecture:   {info['architecture']}")
    print(f"Python:         {info['python_version']}")
    
    if info.get('is_raspberry_pi'):
        print(f"Hardware:       🍓 Raspberry Pi Detected!")
    
    if info.get('linux_distro'):
        print(f"Linux Distro:   {info['linux_distro']}")
    
    print("-" * 50)
    
    if gpu:
        layers = get_recommended_gpu_layers(gpu)
        print(f"GPU:            {gpu['name']}")
        if gpu.get("backend") == "metal":
            print(f"Unified Memory: {gpu['memory_mb']} MB (shared with CPU)")
        else:
            print(f"VRAM:           {gpu['memory_mb']} MB")
        print(f"Driver:         {gpu['driver_version']}")
        print(f"Recommended GPU Layers: {'all' if layers == -1 else layers}")
    else:
        print("GPU:            None detected (CPU inference)")
    
    if get_os_type() == OSType.LINUX:
        nm = get_network_manager()
        print(f"Network Mgr:    {nm or 'None found'}")
    
    print("=" * 50)


if __name__ == "__main__":
    print_system_summary()
