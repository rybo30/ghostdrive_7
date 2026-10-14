# login_helpers.py (FIXED)

import hashlib
import base64
from cryptography.fernet import Fernet

def load_creds(username, passphrase):
    # Normalize the username to ensure consistent salt generation
    normalized = username.strip().lower()
    salt = normalized.encode()
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 100_000)
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)

def generate_vault_key(username, passphrase):
    # This uses the same normalization for vault access too
    normalized = username.strip().lower()
    salt = normalized.encode()
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 100_000)
    return base64.urlsafe_b64encode(key)