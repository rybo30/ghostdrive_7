import os

import pytest
from cryptography.fernet import Fernet

from core.Everything_else import inventory_manager as inv


@pytest.fixture(autouse=True)
def isolated_inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(inv, "INVENTORY_BASE", str(tmp_path))
    monkeypatch.setattr(inv, "INVENTORY_DIR", str(tmp_path))
    return tmp_path


def test_inventory_path_naming(isolated_inventory):
    assert inv.get_inventory_path("bob", "Tools").endswith(os.path.join("bob", "inv_tools.enc"))
    # Already-prefixed IDs are used as-is
    assert inv.get_inventory_path("bob", "inv_abc.enc").endswith(os.path.join("bob", "inv_abc.enc"))


def test_load_missing_sheet_returns_default_schema(fernet):
    payload = inv.load_inventory("bob", fernet, "pantry")
    assert payload == {"schema": inv.DEFAULT_SCHEMA, "data": []}


def test_save_and_load_roundtrip(fernet):
    payload = {"schema": ["name", "qty"], "data": [{"name": "rice", "qty": "5"}]}
    assert inv.save_inventory("bob", payload, fernet, "pantry")

    loaded = inv.load_inventory("bob", fernet, "pantry")
    assert loaded["data"] == [{"name": "rice", "qty": "5"}]
    assert loaded["schema"] == ["name", "qty"]
    assert loaded["internal_id"] == "pantry"


def test_saved_file_is_encrypted(fernet):
    inv.save_inventory("bob", {"schema": ["name"], "data": [{"name": "flashlight"}]}, fernet, "gear")
    with open(inv.get_inventory_path("bob", "gear"), "rb") as f:
        assert b"flashlight" not in f.read()


def test_wrong_key_falls_back_to_empty(fernet):
    inv.save_inventory("bob", {"schema": ["name"], "data": [{"name": "x"}]}, fernet, "gear")
    other = Fernet(Fernet.generate_key())
    assert inv.load_inventory("bob", other, "gear")["data"] == []


def test_legacy_list_payload_is_wrapped(fernet):
    import json

    path = inv.get_inventory_path("bob", "old")
    with open(path, "wb") as f:
        f.write(fernet.encrypt(json.dumps([{"name": "axe"}]).encode()))
    loaded = inv.load_inventory("bob", fernet, "old")
    assert loaded == {"schema": inv.DEFAULT_SCHEMA, "data": [{"name": "axe"}]}


def test_list_sheets(fernet):
    assert inv.list_inventory_sheets("nobody") == ["inventory"]
    inv.save_inventory("bob", {"schema": [], "data": []}, fernet, "pantry")
    inv.save_inventory("bob", {"schema": [], "data": []}, fernet, "gear")
    assert sorted(inv.list_inventory_sheets("bob")) == ["gear", "pantry"]


def test_rename_sheet(fernet):
    inv.save_inventory("bob", {"schema": [], "data": []}, fernet, "a")
    inv.save_inventory("bob", {"schema": [], "data": []}, fernet, "b")

    assert inv.rename_inventory_file("bob", "missing", "c") == (False, "Source file not found: missing")
    assert inv.rename_inventory_file("bob", "a", "b") == (False, "A sheet with that name already exists.")
    assert inv.rename_inventory_file("bob", "a", "c") == (True, None)
    assert sorted(inv.list_inventory_sheets("bob")) == ["b", "c"]


def test_csv_export_import_roundtrip(fernet, tmp_path):
    payload = {
        "schema": ["name", "quantity"],
        "data": [{"name": "water", "quantity": "10"}, {"name": "beans", "quantity": "4"}],
    }
    csv_path = str(tmp_path / "out.csv")
    inv.export_inventory_to_csv("bob", payload, "pantry", path=csv_path)

    target = {"schema": ["name", "quantity"], "data": []}
    ok, count = inv.import_inventory_from_csv("bob", fernet, target, "pantry", path=csv_path)
    assert (ok, count) == (True, 2)
    assert inv.load_inventory("bob", fernet, "pantry")["data"] == payload["data"]


def test_csv_import_missing_file(fernet, tmp_path):
    ok, msg = inv.import_inventory_from_csv("bob", fernet, {}, "pantry", path=str(tmp_path / "x.csv"))
    assert not ok and "No export file" in msg
