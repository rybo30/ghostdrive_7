import pytest

from core import identity


@pytest.fixture
def salt(tmp_path):
    p = tmp_path / "salt.bin"
    p.write_bytes(b"physical-salt-bytes")
    return str(p)


def test_identity_is_deterministic(salt):
    a = identity.get_hardware_locked_identity("Alice", "pw", salt)
    b = identity.get_hardware_locked_identity("Alice", "pw", salt)
    assert a["identity_pub_hex"] == b["identity_pub_hex"]
    assert a["sync_pub_hex"] == b["sync_pub_hex"]
    assert len(a["seed"]) == 32
    assert len(bytes.fromhex(a["identity_pub_hex"])) == 32


def test_username_is_case_and_whitespace_insensitive(salt):
    a = identity.get_hardware_locked_identity("Alice", "pw", salt)
    b = identity.get_hardware_locked_identity("  alice ", "pw", salt)
    assert a["identity_pub_hex"] == b["identity_pub_hex"]


def test_identity_changes_with_passphrase_or_salt(salt, tmp_path):
    base = identity.get_hardware_locked_identity("alice", "pw", salt)
    assert identity.get_hardware_locked_identity("alice", "pw2", salt)["seed"] != base["seed"]

    other = tmp_path / "other.bin"
    other.write_bytes(b"different")
    assert identity.get_hardware_locked_identity("alice", "pw", str(other))["seed"] != base["seed"]


def test_missing_salt_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        identity.get_hardware_locked_identity("alice", "pw", str(tmp_path / "nope"))


def test_signature_verifies_with_public_key(salt):
    from cryptography.hazmat.primitives.asymmetric import ed25519

    ident = identity.get_hardware_locked_identity("alice", "pw", salt)
    sig = ident["identity_priv"].sign(b"hello")
    pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(ident["identity_pub_hex"]))
    pub.verify(sig, b"hello")  # raises on failure


def test_shared_secret_matches_on_both_sides(salt, tmp_path):
    bob_salt = tmp_path / "bob.bin"
    bob_salt.write_bytes(b"bob-salt")
    alice = identity.get_hardware_locked_identity("alice", "pw", salt)
    bob = identity.get_hardware_locked_identity("bob", "pw", str(bob_salt))

    s1 = identity.derive_shared_secret(alice["sync_priv"], bob["sync_pub_hex"])
    s2 = identity.derive_shared_secret(bob["sync_priv"], alice["sync_pub_hex"])
    assert s1 == s2 and len(s1) == 32


def test_room_id_is_order_independent():
    a, b = "aa" * 32, "bb" * 32
    assert identity.generate_shared_room_id(a, b) == identity.generate_shared_room_id(b, a)
    assert len(identity.generate_shared_room_id(a, b)) == 16
    assert identity.generate_shared_room_id(a, b) != identity.generate_shared_room_id(a, "cc" * 32)
