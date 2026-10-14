import re
import time
from jynx_operator_ui import execute_command

PROTOCOLS = {
    "status_report": "Summarize current system status and health.",
    "soul_vent": "Encrypted journal entry",
    "blackout_mode": "Disable Wi-Fi",
    "reconnect_wifi": "Reconnect Wi-Fi",
    "scan_networks": "Scan Wi-Fi",
    "project_protocol": "Open Projects",
    "inventory_protocol": "Open Inventory",
    # Add others as needed
}

_last_protocol_run = {}
PROTOCOL_COOLDOWN_SEC = 1

def maybe_run_protocol_from_reply(reply: str, username: str | None):
    match = re.search(r'(?i)activating\s+([a-z0-9 _-]+?)\s+protocol', reply)
    if not match:
        return False
    protocol = match.group(1).strip().replace(" ", "_").lower()

    now = time.time()
    if protocol in _last_protocol_run and now - _last_protocol_run[protocol] < PROTOCOL_COOLDOWN_SEC:
        return False

    try:
        execute_command(protocol, username=username)
        _last_protocol_run[protocol] = now
        return True
    except Exception as e:
        print(f"❌ Protocol '{protocol}' failed: {e}")
        return False


def check_for_commands(user_input, jynx_response, username=None):
    text = user_input.lower()

    if "blackout" in text:
        execute_command("blackout_mode")
    elif "reconnect" in text:
        execute_command("reconnect_wifi")
    elif "scan" in text:
        execute_command("scan_networks")
    elif "status" in text:
        execute_command("status_report")
    elif "soul vent" in text:
        execute_command("soul_vent")
