# save_agent_config.py

import os
import sys
import json
import uuid
import socket
import traceback
from pathlib import Path
from cryptography.fernet import Fernet

# Resolve paths dynamically from paths.py
from paths import USB_FLEET_DIR

DEFAULT_USB_FLEET_DIR = Path(USB_FLEET_DIR)


def generate_encryption_key() -> bytes:
    """Generates a new Fernet key for agent payload encryption."""
    return Fernet.generate_key()


def save_agent_config(
    config_data: dict, 
    target_dir: str | Path = DEFAULT_USB_FLEET_DIR, 
    encrypt: bool = True
) -> tuple[Path, Path | None]:
    """
    Saves an agent configuration dictionary to disk.
    If encrypt=True, outputs an encrypted .enc file and a corresponding .key file.
    Returns a tuple of (config_file_path, key_file_path).
    """
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    agent_id = config_data.get("agent_id", str(uuid.uuid4())[:8])
    agent_name = config_data.get("agent_name", f"Agent-{agent_id}").replace(" ", "_")
    base_filename = f"{agent_name}_{agent_id}"

    raw_bytes = json.dumps(config_data, indent=4).encode("utf-8")

    if encrypt:
        key = generate_encryption_key()
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(raw_bytes)

        enc_file_path = target_path / f"{base_filename}.enc"
        key_file_path = target_path / f"{base_filename}.key"

        with open(enc_file_path, "wb") as f:
            f.write(encrypted_data)

        with open(key_file_path, "wb") as f:
            f.write(key)

        return enc_file_path, key_file_path
    else:
        else_file_path = target_path / f"{base_filename}.json"
        with open(else_file_path, "wb") as f:
            f.write(raw_bytes)

        return else_file_path, None



def build_agent_payload(
    agent_name: str,
    model_path: str,
    system_prompt: str = "",
    telegram_token: str = "",
    scheduled_ping: dict | None = None,
    user_profile: dict | None = None,  # <--- ADDED PARAMETER
    allowed_tools: list[str] | None = None,
    mail_user: str | None = None,
    mail_pass: str | None = None,
    mail_server: str | None = None,
    target_dir: str | Path = DEFAULT_USB_FLEET_DIR
) -> tuple[dict, Path, Path | None]:
    """
    Validates model existence, constructs the config payload, and writes it to disk.
    """
    cleaned_model_path = model_path.strip()
    if not cleaned_model_path or not os.path.exists(cleaned_model_path):
        raise FileNotFoundError(f"Model file path not found: '{cleaned_model_path}'")

    model_filename_only = os.path.basename(cleaned_model_path)

    agent_id = str(uuid.uuid4())[:8]
    env_secrets = {}

    # --- AUTO-DISCOVER ALL TOOLS IF NONE SPECIFIED ---
    tools_list = allowed_tools or []
    if not tools_list:
        tools_dir = Path(__file__).parent / "tools"
        if tools_dir.exists():
            tools_list = [
                f[:-3] for f in os.listdir(tools_dir)
                if f.endswith("_tool.py") and not f.startswith("__")
            ]

    if "mail_tool" in tools_list:
        if mail_user and mail_pass:
            env_secrets["MAIL_USER"] = mail_user.strip()
            env_secrets["MAIL_PASS"] = mail_pass.strip()
            if mail_server:
                env_secrets["MAIL_IMAP_SERVER"] = mail_server.strip()

    config_data = {
        "agent_id": agent_id,
        "agent_name": agent_name.strip() or f"Agent-{agent_id}",
        "deployed_host": socket.gethostname(),
        "system_prompt": system_prompt.strip(),
        "telegram_bot_token": telegram_token.strip(),
        "model_path": model_filename_only,
        "scheduled_ping": scheduled_ping or {},
        "user_profile": user_profile or {},  # <--- SAVED IN ENCRYPTED PAYLOAD
        "allowed_tools": tools_list,
        "env_secrets": env_secrets
    }

    enc_path, key_path = save_agent_config(config_data, target_dir=target_dir, encrypt=True)
    return config_data, enc_path, key_path

if __name__ == "__main__":
    try:
        print("[+] Testing standalone save_agent_config.py...")
        dummy_model = "test_model.gguf"
        
        with open(dummy_model, "w") as f:
            f.write("dummy model content")

        cfg, enc_file, key_file = build_agent_payload(
            agent_name="Test-Fleet-Agent",
            model_path=dummy_model,
            system_prompt="You are a deployment test agent.",
            allowed_tools=["mail_tool"],
            mail_user="agent@test.com",
            mail_pass="secret123",
            mail_server="imap.test.com"
        )

        print(f"[✓] Agent '{cfg['agent_name']}' created successfully.")
        print(f"    - Encrypted Config: {enc_file}")
        print(f"    - Key File:         {key_file}")

        if os.path.exists(dummy_model):
            os.remove(dummy_model)

    except Exception as err:
        print(f"[!] Error: {err}", file=sys.stderr)
        traceback.print_exc()