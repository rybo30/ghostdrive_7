"""GhostEngine (encrypted file store) and filecrypt helpers."""

import hashlib

import pytest

from core.Everything_else import filecrypt
from core.Everything_else.encryption_engine import GhostEngine


@pytest.fixture
def engine(fernet, tmp_path):
    eng = GhostEngine(fernet)
    eng.vault_dir = str(tmp_path)
    return eng


def test_encrypt_then_decrypt_file(engine, tmp_path):
    src = tmp_path / "note.txt"
    src.write_bytes(b"top secret contents")

    ghost_id, size = engine.encrypt_file(str(src))

    assert ghost_id.startswith("ghost_") and ghost_id.endswith(".dat")
    assert size == len(b"top secret contents")
    stored = (tmp_path / ghost_id).read_bytes()
    assert b"top secret" not in stored
    assert engine.decrypt_file_to_memory(ghost_id) == b"top secret contents"
    assert engine.decrypt_file_to_memory_direct(str(tmp_path / ghost_id)) == b"top secret contents"


def test_each_encryption_gets_unique_id(engine, tmp_path):
    src = tmp_path / "a.txt"
    src.write_bytes(b"x")
    id1, _ = engine.encrypt_file(str(src))
    id2, _ = engine.encrypt_file(str(src))
    assert id1 != id2


def test_engine_with_string_instead_of_fernet_is_inert(tmp_path):
    eng = GhostEngine("/some/legacy/path")
    assert eng.fernet is None
    src = tmp_path / "a.txt"
    src.write_bytes(b"x")
    assert eng.encrypt_file(str(src)) == (None, 0)


def test_wallet_seed_is_deterministic(engine, tmp_path):
    salt = tmp_path / "salt.bin"
    salt.write_bytes(b"hardware-salt")
    seed = engine.get_wallet_seed(str(salt))
    assert len(seed) == 32
    assert seed == engine.get_wallet_seed(str(salt))
    assert seed == hashlib.sha256(b"hardware-salt" + b"GHOST_DRIVE_WALLET_v1").digest()


def test_wallet_seed_missing_salt_raises(engine, tmp_path):
    with pytest.raises(FileNotFoundError):
        engine.get_wallet_seed(str(tmp_path / "missing.bin"))


def test_filecrypt_encrypt_file_replaces_original(fernet, tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("hello")
    filecrypt.encrypt_file(str(src), fernet)
    assert not src.exists()
    assert filecrypt.decrypt_file(str(src) + ".enc", fernet) == "hello"


def test_filecrypt_missing_files(fernet, tmp_path):
    assert filecrypt.encrypt_file(str(tmp_path / "missing"), fernet) is None
    assert filecrypt.decrypt_file(str(tmp_path / "missing.enc"), fernet) is None


def test_filecrypt_encrypt_bytes(fernet, tmp_path):
    out = tmp_path / "blob.enc"
    filecrypt.encrypt_bytes(b"\x00\x01binary", str(out), fernet)
    assert fernet.decrypt(out.read_bytes()) == b"\x00\x01binary"


def test_filecrypt_derive_key_matches_ghostvault():
    from core.Everything_else import ghostvault

    salt = b"s" * 16
    assert filecrypt.derive_key("pw", salt) == ghostvault.derive_key("pw", salt)
