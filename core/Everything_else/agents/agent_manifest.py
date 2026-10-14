# agent_manifest.py

import os
import sys
import json
import glob
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Resolve paths dynamically from paths.py
from paths import USB_FLEET_DIR

# Configure logger
logger = logging.getLogger("AgentManifest")
logger.setLevel(logging.INFO)

DEFAULT_FLEET_DIR = Path(USB_FLEET_DIR)


class AgentManifest:
    """
    Central fleet ledger for discovering, indexing, and looking up 
    agent configuration artifacts (.enc, .key, .json) across target directories.
    """

    def __init__(self, target_dir: Path | str = DEFAULT_FLEET_DIR):
        self.target_dir = Path(target_dir)
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def scan_fleet(self) -> Dict[str, Dict[str, Any]]:
        registry = {}

        # Look for encrypted files (.enc)
        enc_files = glob.glob(str(self.target_dir / "*.enc"))
        for enc_path_str in enc_files:
            enc_path = Path(enc_path_str)
            base_name = enc_path.stem
            
            agent_id = base_name.split("_")[-1] if "_" in base_name else base_name
            key_path = enc_path.with_suffix(".key")

            registry[agent_id] = {
                "agent_id": agent_id,
                "base_name": base_name,
                "encrypted": True,
                "enc_path": enc_path,
                "key_path": key_path if key_path.exists() else None,
                "json_path": None,
                "valid_pair": key_path.exists()
            }

        # Look for unencrypted files (.json)
        json_files = glob.glob(str(self.target_dir / "*.json"))
        for json_path_str in json_files:
            json_path = Path(json_path_str)
            base_name = json_path.stem
            agent_id = base_name.split("_")[-1] if "_" in base_name else base_name

            if agent_id not in registry:
                registry[agent_id] = {
                    "agent_id": agent_id,
                    "base_name": base_name,
                    "encrypted": False,
                    "enc_path": None,
                    "key_path": None,
                    "json_path": json_path,
                    "valid_pair": True
                }

        return registry

    def get_agent_paths(self, agent_id: str, target_dir: Optional[Path | str] = None) -> Dict[str, Optional[Path]]:
        search_dir = Path(target_dir) if target_dir else self.target_dir
        
        enc_matches = list(search_dir.glob(f"*{agent_id}*.enc"))
        key_matches = list(search_dir.glob(f"*{agent_id}*.key"))
        json_matches = list(search_dir.glob(f"*{agent_id}*.json"))

        enc_path = enc_matches[0] if enc_matches else None
        key_path = key_matches[0] if key_matches else None
        json_path = json_matches[0] if json_matches else None

        if enc_path and not key_path:
            potential_key = enc_path.with_suffix(".key")
            if potential_key.exists():
                key_path = potential_key

        return {
            "agent_id": agent_id,
            "enc_path": enc_path,
            "key_path": key_path,
            "json_path": json_path,
            "exists": bool(enc_path or json_path)
        }

    def validate_agent_pair(self, agent_id: str, target_dir: Optional[Path | str] = None) -> Tuple[bool, str]:
        paths = self.get_agent_paths(agent_id, target_dir)
        
        if not paths["exists"]:
            return False, f"No agent matching ID '{agent_id}' found in {target_dir or self.target_dir}"

        if paths["enc_path"]:
            if not paths["key_path"]:
                return False, f"Missing matching .key file for encrypted agent '{agent_id}' ({paths['enc_path']})"
            return True, "Valid encrypted file pair (.enc + .key) present."

        if paths["json_path"]:
            return True, "Valid unencrypted config (.json) present."

        return False, "Unknown artifact state."

    def list_fleet_summary(self) -> List[Dict[str, Any]]:
        registry = self.scan_fleet()
        summary = []
        for agent_id, info in registry.items():
            summary.append({
                "agent_id": agent_id,
                "name": info["base_name"],
                "encrypted": info["encrypted"],
                "status": "Ready" if info["valid_pair"] else "Missing Key File",
                "enc_path": str(info["enc_path"]) if info["enc_path"] else None,
                "key_path": str(info["key_path"]) if info["key_path"] else None,
                "json_path": str(info["json_path"]) if info["json_path"] else None
            })
        return summary


def get_agent_paths(agent_id: str, target_dir: Path | str = DEFAULT_FLEET_DIR) -> Dict[str, Optional[Path]]:
    manifest = AgentManifest(target_dir)
    return manifest.get_agent_paths(agent_id)


def validate_agent_pair(agent_id: str, target_dir: Path | str = DEFAULT_FLEET_DIR) -> Tuple[bool, str]:
    manifest = AgentManifest(target_dir)
    return manifest.validate_agent_pair(agent_id)


if __name__ == "__main__":
    print("[+] Testing standalone agent_manifest.py...")
    manifest = AgentManifest()
    fleet = manifest.list_fleet_summary()
    
    print(f"[✓] Fleet Scan Complete. Found {len(fleet)} agents in '{manifest.target_dir}':")
    for item in fleet:
        print(f"    - ID: {item['agent_id']} | Name: {item['name']} | Status: {item['status']}")