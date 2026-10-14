# [ghostvault.py]

import os
import json
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
from hashlib import pbkdf2_hmac
from core.paths import USER_DATA

os.makedirs(USER_DATA, exist_ok=True)

def get_vault_paths(username):
    vault_file = os.path.join(USER_DATA, f"ghostvault_{username}.enc")
    salt_file = os.path.join(USER_DATA, f"salt_{username}.bin")
    
    # CRITICAL DEBUG: This will print in your terminal every time you click Login
    #print(f"\n--- PATH DEBUG ---")
    #print(f"Targeting Vault: {vault_file}")
    #print(f"Targeting Salt:  {salt_file}")
    #print(f"File Exists?     {os.path.exists(vault_file)}")
    #print(f"------------------\n")
    
    return vault_file, salt_file

def derive_key(password, salt, iterations=100_000):
    key = pbkdf2_hmac("sha256", password.encode(), salt, iterations, dklen=32)
    return urlsafe_b64encode(key)

def load_key_from_passphrase(passphrase, salt_path):
    if not os.path.exists(salt_path):
        # This branch is for first-time creation via login_helpers
        salt = os.urandom(16)
        with open(salt_path, "wb") as f:
            f.write(salt)
    else:
        with open(salt_path, "rb") as f:
            salt = f.read()
    return derive_key(passphrase, salt)

def encrypt_vault(data_dict, fernet, vault_path):
    encrypted = fernet.encrypt(json.dumps(data_dict).encode())
    with open(vault_path, "wb") as f:
        f.write(encrypted)

def decrypt_vault(fernet, vault_path):
    if not os.path.exists(vault_path):
        return {}
    with open(vault_path, "rb") as f:
        encrypted = f.read()
    try:
        decrypted_bytes = fernet.decrypt(encrypted)
        return json.loads(decrypted_bytes.decode('utf-8'))
    except Exception as e:
        # This prevents the red codec error by returning an empty dict or error flag
        print(f"DEBUG: Vault Decryption Failed (Memory Corruption?): {e}")
        return {"ERROR": "DECRYPTION_FAILURE"}

def create_new_user(username, passphrase):
    vault_path, salt_path = get_vault_paths(username)

    # Generate and store new salt in the new portable location
    salt = os.urandom(16)
    with open(salt_path, "wb") as f:
        f.write(salt)

    # Derive and save encrypted blank vault
    key = derive_key(passphrase, salt)
    fernet = Fernet(key)
    encrypt_vault({}, fernet, vault_path)

def user_exists(username):
    vault_path, salt_path = get_vault_paths(username)
    return os.path.exists(vault_path) and os.path.exists(salt_path)

# === Public UI Functions ===

def load_vault(username, passphrase):
    vault_path, salt_path = get_vault_paths(username)
    try:
        key = load_key_from_passphrase(passphrase, salt_path)
        fernet = Fernet(key)
        return decrypt_vault(fernet, vault_path)
    except Exception as e:
        raise ValueError("Invalid passphrase or corrupted vault.")

def generate_fernet(username, passphrase):
    _, salt_path = get_vault_paths(username)
    key = load_key_from_passphrase(passphrase, salt_path)
    return Fernet(key)

def add_secret(username, passphrase, label, account_user, account_pass):
    vault_path, salt_path = get_vault_paths(username)
    key = load_key_from_passphrase(passphrase, salt_path)
    fernet = Fernet(key)
    vault_data = decrypt_vault(fernet, vault_path)
    

    vault_data[label] = {
        "username": account_user,
        "password": account_pass
    }
    
    encrypt_vault(vault_data, fernet, vault_path)

def delete_secret(username, passphrase, label):
    vault_path, salt_path = get_vault_paths(username)
    key = load_key_from_passphrase(passphrase, salt_path)
    fernet = Fernet(key)
    vault_data = decrypt_vault(fernet, vault_path)
    if label in vault_data:
        del vault_data[label]
        encrypt_vault(vault_data, fernet, vault_path)

def get_secrets(username, passphrase):
    return load_vault(username, passphrase)