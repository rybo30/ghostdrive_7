import os
import sys
from cryptography.fernet import Fernet

def get_base_path():
    """Finds the GHOSTDRIVE root folder regardless of OS or packaging."""
    if getattr(sys, 'frozen', False):
        ext_path = os.path.dirname(sys.executable)
        if sys.platform == 'darwin':  # macOS App Bundle structure
            return os.path.abspath(os.path.join(ext_path, "../../../.."))
        else:  # Windows and Linux standalone executables
            return os.path.abspath(os.path.join(ext_path, ".."))
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def get_target_os_key(platform_str: str = None) -> str:
    """Returns 'w', 'm', or 'l' based on the operating system."""
    target_platform = platform_str or sys.platform
    if target_platform.startswith("win"):
        return "w"
    elif target_platform == "darwin":
        return "m"
    else:
        return "l"

# --- Core Platform Bases ---
BASE_PATH = get_base_path()
CORE_DIR = os.path.join(BASE_PATH, "core")
EVERYTHING_ELSE = os.path.join(CORE_DIR, "Everything_else")

# --- Portable USB/Data Locations ---
MODELS_DIR = os.path.join(EVERYTHING_ELSE, "models")
USER_DATA = os.path.join(EVERYTHING_ELSE, "vault") 
PROJECTS_DIR = os.path.join(EVERYTHING_ELSE, "projects")
INVENTORY_DIR = os.path.join(EVERYTHING_ELSE, "inventory")
WALLET_DIR = os.path.join(CORE_DIR, "wallet") 
GAMES_DIR = os.path.join(EVERYTHING_ELSE, "games")
HEALTH_DIR = os.path.join(EVERYTHING_ELSE, "health")
AGENTS_DIR = os.path.join(EVERYTHING_ELSE, "agents")

# Multi-OS Source Runtimes on USB
AGENTS_RUNTIME_SRC_DIR_W = os.path.join(AGENTS_DIR, "runtime_w")
AGENTS_RUNTIME_SRC_DIR_M = os.path.join(AGENTS_DIR, "runtime_m")
AGENTS_RUNTIME_SRC_DIR_L = os.path.join(AGENTS_DIR, "runtime_l")

def get_agents_runtime_src_dir(os_key: str = None) -> str:
    key = os_key or get_target_os_key()
    mapping = {
        "w": AGENTS_RUNTIME_SRC_DIR_W,
        "m": AGENTS_RUNTIME_SRC_DIR_M,
        "l": AGENTS_RUNTIME_SRC_DIR_L
    }
    return mapping[key]

# Active dynamic source directory for host OS
AGENTS_RUNTIME_SRC_DIR = get_agents_runtime_src_dir()

USB_TOOLS_DIR = os.path.join(AGENTS_DIR, "tools")
USB_FLEET_DIR = os.path.join(AGENTS_DIR, "fleet")

# --- OS-Specific Host Storage Directories ---
USER_HOME = os.path.expanduser("~")
HOST_HIDDEN_DIR = os.path.abspath(os.path.join(USER_HOME, ".ghostdrive"))

AGENT_CONFIGS_DIR = os.path.join(HOST_HIDDEN_DIR, "agents", "configs")
AGENT_TOOLS_DIR = os.path.join(HOST_HIDDEN_DIR, "agents", "tools")
HOST_PROJECTS_DIR = os.path.join(HOST_HIDDEN_DIR, "projects")

# Host target runtime directories
AGENT_RUNTIME_DIR_W = os.path.join(HOST_HIDDEN_DIR, "agents", "runtime_w")
AGENT_RUNTIME_DIR_M = os.path.join(HOST_HIDDEN_DIR, "agents", "runtime_m")
AGENT_RUNTIME_DIR_L = os.path.join(HOST_HIDDEN_DIR, "agents", "runtime_l")

def get_agent_runtime_dir(os_key: str = None) -> str:
    key = os_key or get_target_os_key()
    mapping = {
        "w": AGENT_RUNTIME_DIR_W,
        "m": AGENT_RUNTIME_DIR_M,
        "l": AGENT_RUNTIME_DIR_L
    }
    return mapping[key]

# Active host target directory for host OS
AGENT_RUNTIME_DIR = get_agent_runtime_dir()

HOST_MODELS_DIR = os.path.join(HOST_HIDDEN_DIR, "models")
HOST_VAULT_DIR = os.path.join(HOST_HIDDEN_DIR, "vault")

# --- Key Management ---
MASTER_KEY_PATH = os.path.join(HOST_HIDDEN_DIR, ".master.key")

def ensure_host_directories():
    """Provisions host directories strictly when explicitly called during deployment."""
    for folder in [
        HOST_HIDDEN_DIR, AGENT_CONFIGS_DIR, AGENT_TOOLS_DIR, 
        AGENT_RUNTIME_DIR_W, AGENT_RUNTIME_DIR_M, AGENT_RUNTIME_DIR_L,
        HOST_MODELS_DIR, HOST_VAULT_DIR
    ]:
        os.makedirs(folder, exist_ok=True)

def get_or_create_master_key() -> bytes:
    """Retrieves or generates the master key."""
    if os.path.exists(MASTER_KEY_PATH):
        with open(MASTER_KEY_PATH, "rb") as f:
            return f.read().strip()

    os.makedirs(HOST_HIDDEN_DIR, exist_ok=True)
    key = Fernet.generate_key()
    with open(MASTER_KEY_PATH, "wb") as f:
        f.write(key)
    return key