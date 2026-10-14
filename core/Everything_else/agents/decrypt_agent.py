# decrypt_agent.py

import os
import sys
import json
import logging
import traceback
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

# Configure logger
logger = logging.getLogger("DecryptAgent")
logger.setLevel(logging.INFO)


def decrypt_agent_config(
    enc_path: Path | str, 
    key_path: Path | str | None = None
) -> dict:
    """
    Reads an encrypted .enc file and corresponding .key file, validates the key,
    decrypts the payload using Fernet, and returns the raw configuration dictionary.
    
    If key_path is omitted, it auto-discovers the adjacent .key file with the same stem.
    """
    enc_file = Path(enc_path)

    if not enc_file.exists():
        err_msg = f"Encrypted payload file not found: {enc_file}"
        logger.error(f"[DECRYPT ERROR] {err_msg}")
        raise FileNotFoundError(err_msg)

    # Auto-discover .key file if not explicitly passed
    if key_path is None:
        key_file = enc_file.with_suffix(".key")
    else:
        key_file = Path(key_path)

    if not key_file.exists():
        err_msg = f"Key file not found: {key_file}"
        logger.error(f"[DECRYPT ERROR] {err_msg}")
        raise FileNotFoundError(err_msg)

    try:
        # Read raw key bytes
        with open(key_file, "rb") as k_file:
            key_bytes = k_file.read().strip()

        # Fernet keys are 32 URL-safe base64-encoded bytes (length 44)
        if len(key_bytes) != 44:
            err_msg = f"Invalid Fernet key length ({len(key_bytes)} bytes). Expected 44 bytes."
            logger.error(f"[DECRYPT ERROR] {err_msg}")
            raise ValueError(err_msg)

        # Read encrypted payload bytes
        with open(enc_file, "rb") as e_file:
            encrypted_payload = e_file.read()

        # Decrypt payload
        fernet = Fernet(key_bytes)
        decrypted_bytes = fernet.decrypt(encrypted_payload)

        # Parse decrypted JSON back to dict
        config_dict = json.loads(decrypted_bytes.decode("utf-8"))
        logger.info(f"[DECRYPT SUCCESS] Decrypted agent '{config_dict.get('agent_name', 'Unknown')}' ({config_dict.get('agent_id', 'N/A')})")
        return config_dict

    except InvalidToken:
        err_msg = f"Decryption failed for {enc_file.name}: Key does not match payload or data is corrupted (InvalidToken)."
        logger.error(f"[DECRYPT CRITICAL] {err_msg}")
        raise ValueError(err_msg) from None

    except json.JSONDecodeError as e:
        err_msg = f"Decrypted payload in {enc_file.name} is not valid JSON: {str(e)}"
        logger.error(f"[DECRYPT ERROR] {err_msg}")
        raise ValueError(err_msg) from e

    except Exception as e:
        err_msg = f"Unexpected failure decrypting {enc_file.name}: {str(e)}"
        logger.error(f"[DECRYPT ERROR] {err_msg}")
        traceback.print_exc(file=sys.stderr)
        raise RuntimeError(err_msg) from e


if __name__ == "__main__":
    print("[+] Testing standalone decrypt_agent.py...")

    if len(sys.argv) > 1:
        target_enc = sys.argv[1]
        target_key = sys.argv[2] if len(sys.argv) > 2 else None
        
        try:
            config = decrypt_agent_config(target_enc, target_key)
            print("[✓] Decryption Successful!")
            print(f"    - Agent Name: {config.get('agent_name')}")
            print(f"    - Agent ID:   {config.get('agent_id')}")
            print(f"    - Model Path: {config.get('model_path')}")
            print(f"    - Tools:      {config.get('allowed_tools')}")
        except Exception as err:
            print(f"[!] Test Failed: {err}")
    else:
        print("[!] Pass an .enc path (and optional .key path) to test: python decrypt_agent.py <path_to_enc> [path_to_key]")