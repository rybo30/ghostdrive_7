import pytest
from cryptography.fernet import Fernet

from core.Everything_else import ghostvault


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    """Point the vault at a temp dir so tests never touch real user data."""
    monkeypatch.setattr(ghostvault, "USER_DATA", str(tmp_path))
    return tmp_path


def test_derive_key_is_deterministic_and_fernet_compatible():
    salt = b"0123456789abcdef"
    k1 = ghostvault.derive_key("hunter2", salt)
    k2 = ghostvault.derive_key("hunter2", salt)
    assert k1 == k2
    Fernet(k1)  # raises if the key is not valid urlsafe base64 of 32 bytes


def test_derive_key_depends_on_password_and_salt():
    salt = b"0123456789abcdef"
    base = ghostvault.derive_key("hunter2", salt)
    assert ghostvault.derive_key("hunter3", salt) != base
    assert ghostvault.derive_key("hunter2", b"fedcba9876543210") != base


def test_create_new_user_writes_vault_and_salt(isolated_vault):
    assert not ghostvault.user_exists("alice")
    ghostvault.create_new_user("alice", "pw")
    assert ghostvault.user_exists("alice")
    vault_path, salt_path = ghostvault.get_vault_paths("alice")
    assert vault_path.startswith(str(isolated_vault))
    with open(salt_path, "rb") as f:
        assert len(f.read()) == 16


def test_new_vault_is_empty():
    ghostvault.create_new_user("alice", "pw")
    assert ghostvault.get_secrets("alice", "pw") == {}


def test_add_and_delete_secret_roundtrip():
    ghostvault.create_new_user("alice", "pw")
    ghostvault.add_secret("alice", "pw", "email", "alice@example.com", "s3cret")
    ghostvault.add_secret("alice", "pw", "bank", "alice", "1234")

    secrets = ghostvault.get_secrets("alice", "pw")
    assert secrets["email"] == {"username": "alice@example.com", "password": "s3cret"}
    assert set(secrets) == {"email", "bank"}

    ghostvault.delete_secret("alice", "pw", "email")
    assert set(ghostvault.get_secrets("alice", "pw")) == {"bank"}


def test_delete_missing_secret_is_noop():
    ghostvault.create_new_user("alice", "pw")
    ghostvault.delete_secret("alice", "pw", "does-not-exist")
    assert ghostvault.get_secrets("alice", "pw") == {}


def test_wrong_passphrase_returns_error_flag():
    ghostvault.create_new_user("alice", "pw")
    assert ghostvault.get_secrets("alice", "wrong") == {"ERROR": "DECRYPTION_FAILURE"}


def test_vault_file_is_not_plaintext():
    ghostvault.create_new_user("alice", "pw")
    ghostvault.add_secret("alice", "pw", "email", "alice@example.com", "s3cret")
    vault_path, _ = ghostvault.get_vault_paths("alice")
    with open(vault_path, "rb") as f:
        raw = f.read()
    assert b"s3cret" not in raw
    assert b"alice@example.com" not in raw


def test_decrypt_missing_vault_returns_empty(fernet, tmp_path):
    assert ghostvault.decrypt_vault(fernet, str(tmp_path / "nope.enc")) == {}
