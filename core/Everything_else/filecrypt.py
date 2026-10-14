import os
import json
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
from hashlib import pbkdf2_hmac

def derive_key(passphrase, salt, iterations=100_000):
    key = pbkdf2_hmac("sha256", passphrase.encode(), salt, iterations, dklen=32)
    return urlsafe_b64encode(key)

def get_fernet(passphrase, username="default"):
    salt_dir = os.path.join(os.path.dirname(__file__), "vault")
    os.makedirs(salt_dir, exist_ok=True)

    salt_path = os.path.join(salt_dir, f"salt_{username}.bin")

    if not os.path.exists(salt_path):
        salt = os.urandom(16)
        with open(salt_path, "wb") as f:
            f.write(salt)
    else:
        with open(salt_path, "rb") as f:
            salt = f.read()

    key = derive_key(passphrase, salt)
    return Fernet(key)

def encrypt_file(file_path, fernet):
    if not os.path.exists(file_path):
        return
    with open(file_path, "rb") as f:
        data = f.read()
    encrypted = fernet.encrypt(data)
    with open(file_path + ".enc", "wb") as f:
        f.write(encrypted)
    os.remove(file_path)

def decrypt_file(file_path_enc, fernet):
    if not os.path.exists(file_path_enc):
        return None
    with open(file_path_enc, "rb") as f:
        encrypted = f.read()
    decrypted = fernet.decrypt(encrypted)
    return decrypted.decode()

def encrypt_bytes(data_bytes, out_path, fernet):
    encrypted = fernet.encrypt(data_bytes)
    with open(out_path, "wb") as f:
        f.write(encrypted)
