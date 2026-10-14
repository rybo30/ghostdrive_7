# [identity.py]

import os
import hashlib
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization

def get_hardware_locked_identity(username, passphrase, salt_path):
    """
    Creates the core seed tied to the local physical salt file.
    """
    if not os.path.exists(salt_path):
        raise FileNotFoundError("Physical Salt File missing. Identity cannot be verified.")

    # 1. Read the unique physical randomness
    with open(salt_path, "rb") as f:
        physical_salt = f.read()

    # 2. Mix User secret with Physical salt to create the 'Master Seed'
    hasher = hashlib.sha256()
    hasher.update(physical_salt)
    hasher.update(username.lower().strip().encode())
    hasher.update(passphrase.encode())
    seed = hasher.digest()
    
    # 3. Generate Ed25519 Keys (For Digital Signatures / Proving Identity)
    priv_ed = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    pub_ed_hex = priv_ed.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()
    
    # 4. Generate X25519 Keys (For the 'Straw' / Syncing Encrypted Data)
    priv_x = x25519.X25519PrivateKey.from_private_bytes(seed)
    pub_x_hex = priv_x.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()
    
    # Return both sets of keys and the seed for future derivations
    return {
        "seed": seed,
        "identity_priv": priv_ed,
        "identity_pub_hex": pub_ed_hex,
        "sync_priv": priv_x,
        "sync_pub_hex": pub_x_hex # This is the one you text to friends
    }

def derive_shared_secret(my_private_sync_key, peer_public_sync_hex):
    """
    Creates the 'Session Key' that both users share.
    """
    peer_public_bytes = bytes.fromhex(peer_public_sync_hex)
    peer_public_key = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
    
    # The 'Straw' key (Raw bytes)
    shared_key = my_private_sync_key.exchange(peer_public_key)
    return shared_key

def generate_shared_room_id(my_pub_hex, peer_pub_hex):
    """
    Combines two public keys to create a unique Room ID.
    The result is sorted so both users get the same ID regardless of who starts first.
    """
    combined = "".join(sorted([my_pub_hex, peer_pub_hex]))
    return hashlib.sha256(combined.encode()).hexdigest()[:16]