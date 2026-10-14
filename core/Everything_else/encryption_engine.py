# [encryption_engine.py]

import os
import uuid
import hashlib
from cryptography.fernet import Fernet
from core.paths import USER_DATA 

class GhostEngine:
    def __init__(self, fernet, *args):
        # If 'fernet' is a string, it means an old path is being forced in.
        # We ignore it and wait for the actual Fernet object.
        if isinstance(fernet, str):
            self.fernet = None
        else:
            self.fernet = fernet
            
        self.vault_dir = USER_DATA
        
        # Only create the directory if we actually have a valid engine object
        if self.fernet and not os.path.exists(self.vault_dir):
            os.makedirs(self.vault_dir, exist_ok=True)

    def encrypt_file(self, source_path):
        if not self.fernet: return None, 0
        with open(source_path, "rb") as f:
            data = f.read()

        token = self.fernet.encrypt(data)
        ghost_id = f"ghost_{uuid.uuid4().hex}.dat"
        ghost_path = os.path.join(self.vault_dir, ghost_id)

        with open(ghost_path, "wb") as f:
            f.write(token)

        return ghost_id, len(data)

    def decrypt_file_to_memory_direct(self, full_path):
        with open(full_path, "rb") as f:
            token = f.read()
        return self.fernet.decrypt(token)

    def decrypt_file_to_memory(self, ghost_id):
        ghost_path = os.path.join(self.vault_dir, ghost_id)
        with open(ghost_path, "rb") as f:
            token = f.read()
        return self.fernet.decrypt(token)

    def get_wallet_seed(self, salt_path):
        """
        Tactical Bridge: Creates a deterministic 32-byte seed from the hardware salt.
        This is what the WalletUI uses to generate your keys.
        """
        if not os.path.exists(salt_path):
            raise FileNotFoundError(f"Missing Hardware Salt at: {salt_path}")

        with open(salt_path, "rb") as f:
            hardware_salt = f.read()

        # We hash the hardware salt with a specific 'wallet' pepper 
        # to ensure the wallet seed is unique and secure.
        return hashlib.sha256(hardware_salt + b"GHOST_DRIVE_WALLET_v1").digest()