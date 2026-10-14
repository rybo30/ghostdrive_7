# D:\core\Everything_else\agents\load_agent.py

import os
import sys
import json
import logging
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

from core.paths import (
    USB_FLEET_DIR, 
    get_agent_runtime_dir, 
    get_target_os_key
)

try:
    from .decrypt_agent import decrypt_agent_config
    from .agent_manifest import get_agent_paths
except ImportError:
    from decrypt_agent import decrypt_agent_config
    from agent_manifest import get_agent_paths

logger = logging.getLogger("LoadAgent")
logger.setLevel(logging.INFO)


def load_agent(
    target: str | Path, 
    target_dir: Optional[str | Path] = None,
    fleet_dir: Optional[str | Path] = None,
    os_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Loads an agent configuration into memory.
    
    'target' can be:
      1. An explicit file path (.enc or .json)
      2. An agent_id (auto-resolved via AgentManifest)
      
    Decryption happens in-memory only; no plain text is written to disk.
    """
    # Dynamically resolve host target runtime directory based on target OS
    active_os_key = os_key or get_target_os_key()
    default_target_dir = Path(get_agent_runtime_dir(active_os_key))
    default_fleet_dir = Path(USB_FLEET_DIR)

    # Standardize directory argument cleanly
    resolved_dir = target_dir or fleet_dir

    target_path = Path(target) if isinstance(target, (str, Path)) and os.path.exists(str(target)) else None
    
    # 1. Resolve agent_id if direct path not provided or doesn't exist directly
    if not target_path:
        agent_id = str(target)
        search_dir = Path(resolved_dir) if resolved_dir else default_target_dir
        
        paths = get_agent_paths(agent_id, target_dir=search_dir)
        
        # If not found in target dir, check default fleet dir fallback
        if not paths["exists"] and search_dir != default_fleet_dir:
            paths = get_agent_paths(agent_id, target_dir=default_fleet_dir)

        if not paths["exists"]:
            err_msg = f"Unable to locate configuration files for agent_id '{agent_id}' in {search_dir} or {default_fleet_dir}."
            logger.error(f"[LOAD ERROR] {err_msg}")
            raise FileNotFoundError(err_msg)

        if paths.get("enc_path"):
            target_path = Path(paths["enc_path"])
        elif paths.get("json_path"):
            target_path = Path(paths["json_path"])

    if not target_path or not target_path.exists():
        err_msg = f"Target payload file does not exist: {target_path}"
        logger.error(f"[LOAD ERROR] {err_msg}")
        raise FileNotFoundError(err_msg)

    # 2. Handle Encrypted Payload (.enc)
    if target_path.suffix.lower() == ".enc":
        logger.info(f"[LOAD] Decrypting payload in-memory from {target_path.name}")
        config_dict = decrypt_agent_config(str(target_path))
        return config_dict

    # 3. Handle Plain JSON (.json)
    elif target_path.suffix.lower() == ".json":
        logger.info(f"[LOAD] Reading unencrypted JSON payload from {target_path.name}")
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            return config_dict
        except Exception as e:
            err_msg = f"Failed to read JSON config at {target_path}: {str(e)}"
            logger.error(f"[LOAD ERROR] {err_msg}")
            raise RuntimeError(err_msg) from e

    else:
        err_msg = f"Unsupported file extension '{target_path.suffix}'. Expected .enc or .json"
        logger.error(f"[LOAD ERROR] {err_msg}")
        raise ValueError(err_msg)


if __name__ == "__main__":
    print("[+] Testing standalone load_agent.py...")

    if len(sys.argv) > 1:
        target_arg = sys.argv[1]
        try:
            config = load_agent(target_arg)
            print("[✓] Agent Loaded Successfully into RAM!")
            print(f"    - Agent Name: {config.get('agent_name')}")
            print(f"    - Agent ID:   {config.get('agent_id')}")
            print(f"    - Model:      {config.get('model_path') or config.get('model_filename')}")
            print(f"    - Secrets:    {list(config.get('env_secrets', {}).keys())}")
        except Exception as err:
            print(f"[!] Load Failed: {err}")
    else:
        print("[!] Pass an agent_id or path to .enc/.json: python load_agent.py <agent_id_or_path>")