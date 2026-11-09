import os

import pytest
from cryptography.fernet import Fernet

from core import paths


@pytest.mark.parametrize(
    "platform_str,key",
    [("win32", "w"), ("cygwin", "l"), ("darwin", "m"), ("linux", "l"), ("freebsd14", "l")],
)
def test_target_os_key(platform_str, key):
    assert paths.get_target_os_key(platform_str) == key


def test_runtime_dir_mappings():
    assert paths.get_agents_runtime_src_dir("w").endswith("runtime_w")
    assert paths.get_agents_runtime_src_dir("m").endswith("runtime_m")
    assert paths.get_agent_runtime_dir("l").endswith(os.path.join("agents", "runtime_l"))


def test_base_path_is_repo_root_when_not_frozen():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    assert paths.BASE_PATH == repo_root
    assert paths.EVERYTHING_ELSE == os.path.join(repo_root, "core", "Everything_else")


def test_master_key_created_once_and_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "HOST_HIDDEN_DIR", str(tmp_path / ".ghostdrive"))
    monkeypatch.setattr(paths, "MASTER_KEY_PATH", str(tmp_path / ".ghostdrive" / ".master.key"))

    key = paths.get_or_create_master_key()
    Fernet(key)  # valid Fernet key
    assert paths.get_or_create_master_key() == key
