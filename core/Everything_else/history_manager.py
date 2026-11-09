import json, os, time, uuid

def get_log_dir(username):
    path = os.path.join("user_data", username, "chat_logs")
    os.makedirs(path, exist_ok=True)
    return path

def save_chat_session(username, title, full_html_content):
    log_dir = get_log_dir(username)
    # Timestamp prefix keeps files chronological; the random suffix stops
    # sessions saved within the same second from overwriting each other.
    now = time.time()
    filename = f"{int(now)}_{uuid.uuid4().hex[:8]}.json"
    data = {
        "title": title[:50], # Truncate for the sidebar
        "timestamp": now,
        "content": full_html_content
    }
    with open(os.path.join(log_dir, filename), "w") as f:
        json.dump(data, f)

def load_all_sessions(username):
    log_dir = get_log_dir(username)
    sessions = []
    for f in os.listdir(log_dir):
        if f.endswith(".json"):
            with open(os.path.join(log_dir, f), "r") as lf:
                sessions.append(json.load(lf))
    # Sort reverse chronological (newest first)
    return sorted(sessions, key=lambda x: x['timestamp'], reverse=True)