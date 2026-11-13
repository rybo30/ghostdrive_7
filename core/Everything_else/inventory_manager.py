# [inventory_manager.py]

import os
import csv
import json
from cryptography.fernet import Fernet
from core.paths import EVERYTHING_ELSE

INVENTORY_BASE = os.path.join(EVERYTHING_ELSE, "inventory")
os.makedirs(INVENTORY_BASE, exist_ok=True)

DEFAULT_SCHEMA = ["name", "quantity", "location", "last_checked"]

def get_inventory_path(username, sheet_name="inventory"):
    """Returns absolute path for a user's encrypted sheet."""
    user_dir = os.path.join(INVENTORY_BASE, username)
    os.makedirs(user_dir, exist_ok=True)
    
    clean_name = sheet_name.lower().strip().replace(" ", "_")
    if clean_name.startswith("inv_") and clean_name.endswith(".enc"):
        return os.path.join(user_dir, clean_name)
    return os.path.join(user_dir, f"inv_{clean_name}.enc")

def list_inventory_sheets(username):
    """Lists clean sheet names from encrypted storage files."""
    user_dir = os.path.join(INVENTORY_BASE, username)
    if not os.path.exists(user_dir): 
        return ["inventory"]
    
    files = [f for f in os.listdir(user_dir) if f.startswith("inv_") and f.endswith(".enc")]
    sheets = [f[4:-4] for f in files] # Strips 'inv_' and '.enc'
    return sheets if sheets else ["inventory"]

def rename_inventory_file(username, old_id, new_id):
    """Renames an encrypted inventory sheet file."""    
    old_path = get_inventory_path(username, old_id)
    new_path = get_inventory_path(username, new_id)
    
    if not os.path.exists(old_path):
        return False, f"Source sheet not found: {old_id}"
    if os.path.exists(new_path):
        return False, "A sheet with that name already exists."
    
    try:
        os.rename(old_path, new_path)
        return True, None
    except Exception as e:
        return False, str(e)

def load_inventory(username, fernet: Fernet, sheet_name="inventory"):
    """Loads and decrypts inventory schema and data safely."""
    filepath = get_inventory_path(username, sheet_name)
    if not os.path.exists(filepath):
        return {"schema": DEFAULT_SCHEMA, "data": []}

    try:
        with open(filepath, "rb") as f:
            decrypted = fernet.decrypt(f.read()).decode("utf-8")
            payload = json.loads(decrypted)
            if isinstance(payload, list):
                return {"schema": DEFAULT_SCHEMA, "data": payload}
            if "internal_id" not in payload:
                payload["internal_id"] = sheet_name
            return payload
    except Exception as e:
        print(f"[ERROR] Failed to decrypt inventory {sheet_name}: {e}")
        return {"schema": DEFAULT_SCHEMA, "data": []}

def save_inventory(username, payload, fernet: Fernet, sheet_name="inventory"):
    """Encrypts and persists full inventory payload to disk."""
    payload["internal_id"] = sheet_name 
    filepath = get_inventory_path(username, sheet_name)
    
    try:
        encrypted = fernet.encrypt(json.dumps(payload, indent=2).encode("utf-8"))
        with open(filepath, "wb") as f:
            f.write(encrypted)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save inventory {sheet_name}: {e}")
        return False

def export_inventory_to_csv(username, payload, sheet_name="inventory", path=None):
    """Exports current sheet to CSV."""
    data = payload.get("data", [])
    schema = payload.get("schema", DEFAULT_SCHEMA)
    
    if path is None:
        user_dir = os.path.join(INVENTORY_BASE, username)
        path = os.path.join(user_dir, f"inv_{sheet_name.lower()}_export.csv")

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=schema, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)
    return path