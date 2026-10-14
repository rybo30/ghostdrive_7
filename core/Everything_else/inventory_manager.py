# [inventory_manager.py]

import os
import csv
import json
import uuid
from cryptography.fernet import Fernet

# Import the Universal Path from your new paths.py
from core.paths import EVERYTHING_ELSE

# Define the global inventory directory in the central core
INVENTORY_BASE = os.path.join(EVERYTHING_ELSE, "inventory")
INVENTORY_DIR = INVENTORY_BASE
os.makedirs(INVENTORY_BASE, exist_ok=True)

# ──────────────────────────────────────────────
# 🔒 Dynamic, User-Defined Inventory Manager
# ──────────────────────────────────────────────

DEFAULT_SCHEMA = ["name", "quantity", "location", "last_checked"]

def get_inventory_path(username, sheet_name="inventory"):
    """Returns the absolute path. Supports both legacy names and random IDs."""
    user_dir = os.path.join(INVENTORY_BASE, username)
    os.makedirs(user_dir, exist_ok=True)
    
    # If sheet_name already has the prefix/extension, use it directly
    if sheet_name.startswith("inv_") and sheet_name.endswith(".enc"):
        return os.path.join(user_dir, sheet_name)
    
    # Standardizing to 'inv_sheetname.enc' for legacy/named support
    return os.path.join(user_dir, f"inv_{sheet_name.lower()}.enc")

def list_inventory_sheets(username):
    """Lists sheets using the legacy 'inv_' prefix logic."""
    user_dir = os.path.join(INVENTORY_DIR, username)
    if not os.path.exists(user_dir): return ["inventory"]
    
    # Only look for our 'inv_' prefix
    files = [f for f in os.listdir(user_dir) if f.startswith("inv_") and f.endswith(".enc")]
    
    # We return the "clean" names for the UI tabs
    sheets = [f[4:-4] for f in files] # Strips 'inv_' and '.enc'
    return sheets if sheets else ["inventory"]

def rename_inventory_file(username, old_id, new_id):
    """Renames the physical .enc file on disk."""    
    old_path = get_inventory_path(username, old_id)
    new_path = get_inventory_path(username, new_id)
    
    if not os.path.exists(old_path):
        return False, f"Source file not found: {old_id}"
        
    if os.path.exists(new_path):
        return False, "A sheet with that name already exists."
    
    try:
        os.rename(old_path, new_path)
        return True, None
    except Exception as e:
        return False, str(e)

def load_inventory(username, fernet: Fernet, sheet_name="inventory"):
    """Load inventory and schema. Handles legacy list-style and new dict-style payloads."""
    filepath = get_inventory_path(username, sheet_name)
    
    if not os.path.exists(filepath):
        return {"schema": DEFAULT_SCHEMA, "data": []}

    try:
        with open(filepath, "rb") as f:
            decrypted = fernet.decrypt(f.read()).decode("utf-8")
            payload = json.loads(decrypted)

            # Legacy fallback: if file was just a list of items
            if isinstance(payload, list):
                return {"schema": DEFAULT_SCHEMA, "data": payload}
            
            # Ensure the payload knows its own name/id for future saves
            if "internal_id" not in payload:
                payload["internal_id"] = sheet_name

            return payload
    except Exception as e:
        print(f"[ERROR] Failed to decrypt inventory {sheet_name}: {e}")
        return {"schema": DEFAULT_SCHEMA, "data": []}

def save_inventory(username, payload, fernet: Fernet, sheet_name="inventory"):
    """Saves full inventory payload. Ensures the payload and filename stay synced."""
    # Force the payload to match the intended filename
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

# ──────────────────────────────────────────────
# 📤 Export / Import (Legacy Logic Maintained)
# ──────────────────────────────────────────────

def export_inventory_to_csv(username, payload, sheet_name="inventory", path=None):
    """Export inventory to a sheet-specific CSV."""
    data = payload.get("data", [])
    schema = payload.get("schema", DEFAULT_SCHEMA)
    
    if path is None:
        user_dir = os.path.join(INVENTORY_BASE, username)
        path = os.path.join(user_dir, f"inv_{sheet_name.lower()}_export.csv")

    with open(path, "w", newline="", encoding="utf-8") as f:
        # Use schema directly to preserve column order
        writer = csv.DictWriter(f, fieldnames=schema, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)
    return path

def import_inventory_from_csv(username, fernet, current_payload, sheet_name="inventory", path=None):
    """Import CSV data and overwrite the specific active sheet."""
    if path is None:
        user_dir = os.path.join(INVENTORY_BASE, username)
        path = os.path.join(user_dir, f"inv_{sheet_name.lower()}_export.csv")

    if not os.path.exists(path):
        return False, f"No export file found for {sheet_name}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        current_payload["data"] = rows
        save_inventory(username, current_payload, fernet, sheet_name=sheet_name)
        return True, len(rows)
    except Exception as e:
        return False, str(e)