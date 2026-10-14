# peers_manager.py

import json
import os
from core.paths import EVERYTHING_ELSE

PEERS_FILE = os.path.join(EVERYTHING_ELSE, "inventory", "trusted_peers.enc")

def load_peers(username, fernet):
    """Loads and decrypts the trusted peer database."""
    if not os.path.exists(PEERS_FILE):
        return {}
    try:
        with open(PEERS_FILE, "rb") as f:
            decrypted = fernet.decrypt(f.read()).decode()
            return json.loads(decrypted)
    except Exception:
        return {}

def save_peer(username, alias, ghost_id, public_key, fernet, permissions=None):
    """Adds or updates a peer including their RSA Public Key."""
    peers = load_peers(username, fernet)
    
    if alias in peers and permissions is None:
        existing_data = peers[alias]
        if isinstance(existing_data, dict):
            permissions = existing_data.get("permissions")
    
    if permissions is None:
        permissions = {"projects": [], "inventory": []}

    # Added public_key here so it actually gets saved to the encrypted file
    peers[alias] = {
        "ghost_id": ghost_id,
        "public_key": public_key, 
        "permissions": permissions
    }
    
    _write_to_disk(peers, fernet)
    return True

def delete_peer(username, alias, fernet):
    """Removes a peer from the trusted list."""
    peers = load_peers(username, fernet)
    if alias in peers:
        del peers[alias]
        _write_to_disk(peers, fernet)
        return True
    return False

def rename_peer(username, old_alias, new_alias, fernet):
    """Changes the alias for a peer while keeping their ID and permissions."""
    peers = load_peers(username, fernet)
    if old_alias in peers:
        peers[new_alias] = peers.pop(old_alias)
        _write_to_disk(peers, fernet)
        return True
    return False

def _write_to_disk(peers, fernet):
    """Helper to encrypt and write to the file."""
    encrypted = fernet.encrypt(json.dumps(peers).encode())
    with open(PEERS_FILE, "wb") as f:
        f.write(encrypted)