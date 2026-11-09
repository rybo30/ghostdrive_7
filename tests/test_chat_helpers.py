"""Chat text helpers and the protocol trigger parser.

execute_command is always stubbed out: the real one can disable Wi-Fi,
wipe temp files, or shred files.
"""

import pytest

import command_checker
import history_manager
import prompt_utils


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Stay hydrated. Do you understand?", "Stay hydrated."),
        ("Boil water first. Does that make sense?", "Boil water first."),
        ("Hold position, do you understand, commander?", "Hold position."),
        ("A normal answer.", "A normal answer."),
        ("Do you understand the risks here?", "Do you understand the risks here?"),
    ],
)
def test_remove_forced_endings(text, expected):
    assert prompt_utils.remove_forced_endings(text) == expected


@pytest.fixture
def calls(monkeypatch):
    recorded = []
    monkeypatch.setattr(
        command_checker, "execute_command", lambda name, username=None: recorded.append((name, username))
    )
    monkeypatch.setattr(command_checker, "_last_protocol_run", {})
    return recorded


def test_protocol_trigger_is_parsed(calls):
    assert command_checker.maybe_run_protocol_from_reply("Sure.\nActivating Status Report protocol", "alice")
    assert calls == [("status_report", "alice")]


def test_no_trigger_no_call(calls):
    assert not command_checker.maybe_run_protocol_from_reply("Just chatting, no actions.", None)
    assert calls == []


def test_protocol_cooldown(calls):
    reply = "Activating scan_networks protocol"
    assert command_checker.maybe_run_protocol_from_reply(reply, None)
    assert not command_checker.maybe_run_protocol_from_reply(reply, None)
    assert len(calls) == 1


def test_failed_protocol_returns_false(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(command_checker, "execute_command", boom)
    monkeypatch.setattr(command_checker, "_last_protocol_run", {})
    assert not command_checker.maybe_run_protocol_from_reply("Activating sweep protocol", None)


@pytest.mark.parametrize(
    "user_input,protocol",
    [
        ("go into blackout", "blackout_mode"),
        ("please reconnect", "reconnect_wifi"),
        ("scan for networks", "scan_networks"),
        ("give me a status", "status_report"),
        ("open soul vent", "soul_vent"),
    ],
)
def test_check_for_commands_keywords(calls, user_input, protocol):
    command_checker.check_for_commands(user_input, "")
    assert calls == [(protocol, None)]


def test_chat_history_save_and_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # history_manager writes relative to the cwd
    t = iter([1000.0, 1000.0, 2000.0, 2000.0])
    monkeypatch.setattr(history_manager.time, "time", lambda: next(t))

    history_manager.save_chat_session("alice", "first chat", "<p>1</p>")
    history_manager.save_chat_session("alice", "x" * 80, "<p>2</p>")

    sessions = history_manager.load_all_sessions("alice")
    assert [s["content"] for s in sessions] == ["<p>2</p>", "<p>1</p>"]  # newest first
    assert len(sessions[0]["title"]) == 50


@pytest.mark.xfail(strict=True, reason="Known bug: sessions saved in the same second overwrite each other")
def test_chat_history_same_second_keeps_both(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(history_manager.time, "time", lambda: 1000.0)
    history_manager.save_chat_session("alice", "a", "1")
    history_manager.save_chat_session("alice", "b", "2")
    assert len(history_manager.load_all_sessions("alice")) == 2
