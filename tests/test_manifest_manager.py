import pytest

from core.Everything_else import manifest_manager as mm
from core.Everything_else.encryption_engine import GhostEngine


@pytest.fixture
def engine(fernet, tmp_path, monkeypatch):
    monkeypatch.setattr(mm, "USER_DATA", str(tmp_path))
    eng = GhostEngine(fernet)
    eng.vault_dir = str(tmp_path)
    return eng


def test_default_user_never_writes(engine, tmp_path):
    m = mm.ManifestManager(engine)  # username defaults to "default"
    m.add_folder("Work")
    assert m.manifest_file is None
    assert list(tmp_path.iterdir()) == []


def test_entries_persist_encrypted_across_instances(engine, tmp_path):
    m = mm.ManifestManager(engine, "alice")
    m.add_folder("Work")
    m.add_entry("report.pdf", "ghost_1.dat", 1234, "pdf", folder="Work")

    raw = (tmp_path / "vault_manifest_alice.enc").read_bytes()
    assert b"report.pdf" not in raw

    reloaded = mm.ManifestManager(engine, "alice")
    assert reloaded.get_folders() == ["Personal", "Work"]
    [entry] = reloaded.get_files()
    assert entry["name"] == "report.pdf" and entry["folder"] == "Work"
    assert "created_at" in entry


def test_add_folder_is_idempotent(engine):
    m = mm.ManifestManager(engine, "alice")
    m.add_folder("Work")
    m.add_folder("Work")
    assert m.get_folders().count("Work") == 1


def test_move_remove_and_filter(engine):
    m = mm.ManifestManager(engine, "alice")
    m.add_entry("a.png", "g1", 1, "image")
    m.add_entry("b.txt", "g2", 1, "text")

    m.update_file_folder("g1", "Personal")
    assert next(f for f in m.get_files() if f["id"] == "g1")["folder"] == "Personal"

    assert [f["id"] for f in m.get_entries_by_category("image")] == ["g1"]

    m.remove_entry("g1")
    assert [f["id"] for f in m.get_files()] == ["g2"]

    m.remove_folder("Personal")
    assert "Personal" not in m.get_folders()


def test_set_engine_switches_user(engine, tmp_path):
    mm.ManifestManager(engine, "alice").add_folder("AliceOnly")

    m = mm.ManifestManager(None)
    m.set_engine(engine, "alice")
    assert "AliceOnly" in m.get_folders()

    m.set_engine("legacy/path/string")  # ignored
    assert m.engine is engine
