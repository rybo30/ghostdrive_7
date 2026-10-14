# [project_manager.py]

import os
import json
import uuid
from cryptography.fernet import Fernet

# Import the base GPS coordinates from core.paths
from core.paths import EVERYTHING_ELSE

def get_user_project_dir(username):
    """Returns the path to a specific user's project folder anchored in Everything_else."""
    base_projects = os.path.join(EVERYTHING_ELSE, "projects")
    user_dir = os.path.join(base_projects, username)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def load_project_file(username, filename, fernet: Fernet):
    """Refined to handle both full paths or just filenames for the specific user."""
    try:
        if not os.path.isabs(filename):
            user_dir = get_user_project_dir(username)
            filepath = os.path.join(user_dir, filename)
        else:
            filepath = filename

        if not os.path.exists(filepath):
            return None
            
        with open(filepath, "rb") as f:
            encrypted = f.read()
        
        decrypted = fernet.decrypt(encrypted).decode("utf-8")
        data = json.loads(decrypted)
        
        # Ensure the data knows which file it belongs to (useful for re-saving)
        if "internal_id" not in data:
            data["internal_id"] = os.path.basename(filepath)
            
        return data
    except Exception as e:
        print(f"[ERROR] Failed to decrypt project file: {e}")
        return None

def list_project_files(username):
    """Lists just the filenames (cleaner for the UI list)."""
    user_dir = get_user_project_dir(username)
    if not os.path.exists(user_dir):
        return []
    return [f for f in os.listdir(user_dir) if f.endswith(".enc")]

def save_project_file(username, data, fernet: Fernet):
    """Saves an encrypted project file using a randomized filename to hide metadata."""
    try:
        # 1. Handle Filename Logic
        # If the project already has an internal_id, use it. 
        # Otherwise, create a random one (e.g., ghost_a7b2c9...)
        if "internal_id" not in data:
            data["internal_id"] = f"ghost_{uuid.uuid4().hex[:12]}.enc"
        
        filename = data["internal_id"]
        user_dir = get_user_project_dir(username)
        filepath = os.path.join(user_dir, filename)
        
        # 2. Encrypt the data (The 'project' name is now hidden inside the encryption)
        encrypted = fernet.encrypt(json.dumps(data, indent=2).encode("utf-8"))
        
        with open(filepath, "wb") as f:
            f.write(encrypted)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save project for {username}: {e}")
        return False

def delete_project_file(filepath):
    """Deletes a specific project file."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except Exception as e:
        print(f"[ERROR] Failed to delete project file {filepath}: {e}")
        return False

def update_task_status(username, project_data, task_text, new_status, fernet):
    """Updates a specific task's status and saves the project."""
    for task in project_data.get("tasks", []):
        if task["task"] == task_text:
            task["status"] = new_status
            break
    return save_project_file(username, project_data, fernet)