# [chat_manager.py]


import json
import os
import time
import uuid
from datetime import datetime
from .manifest_manager import ManifestManager
from .encryption_engine import GhostEngine
from core.paths import USER_DATA 

class ChatLogManager:
    def __init__(self, engine: GhostEngine, manifest: ManifestManager):
        self.engine = engine
        self.manifest = manifest
        # Ensure a Chatlogs folder exists in the manifest
        if "Chatlogs" not in self.manifest.get_folders():
            self.manifest.add_folder("Chatlogs")

    def save_chatlog(self, history, name=None, log_id=None):
        # 1. Prepare data
        chat_data = {
            "version": "1.0",
            "timestamp": time.time(),
            "history": history
        }
        json_str = json.dumps(chat_data).encode('utf-8')

        # 2. Use a generic temp name
        temp_path = os.path.join(USER_DATA, "temp_vault_payload.dat")
        
        try:
            with open(temp_path, "wb") as f:
                f.write(json_str)

            # 3. Encrypt file
            actual_ghost_id, size = self.engine.encrypt_file(temp_path)
            
            if os.path.exists(temp_path):
                os.remove(temp_path)

            # 4. Resolve Name intelligently without overwriting user custom names
            manifest_files = self.manifest.get_files()
            existing_entry = next((f for f in manifest_files if f["id"] == log_id), None) if log_id else None

            if existing_entry and not name:
                # Keep the existing name if the log already exists and no explicit new name was passed
                name = existing_entry["name"]
            elif not name:
                # Fallback title generation for brand new logs
                if len(history) >= 1:
                    first_msg = history[0].get("content", "")
                    clean_txt = re.sub(r'<[^<]+?>', '', first_msg).strip()
                    name = (clean_txt[:28] + '...') if len(clean_txt) > 28 else (clean_txt if clean_txt else f"Session {datetime.now().strftime('%m-%d %H:%M')}")
                else:
                    name = f"Session {datetime.now().strftime('%m-%d %H:%M')}"

            # 5. Manifest Sync
            if log_id:
                self.manifest.remove_entry(log_id)
            
            self.manifest.add_entry(
                name=name,
                id=actual_ghost_id,
                size=size,
                file_type="chatlog",
                folder="Chatlogs"
            )
            
            return actual_ghost_id
            
        except Exception as e:
            print(f"CRITICAL SAVE ERROR: {e}")
            return log_id



    def load_chatlog(self, ghost_id):
        """Decrypts and returns the chat history list."""
        try:
            decrypted_data = self.engine.decrypt_file_to_memory(ghost_id)
            chat_json = json.loads(decrypted_data.decode('utf-8'))
            return chat_json.get("history", [])
        except Exception as e:
            print(f"Failed to load chatlog {ghost_id}: {e}")
            return None

    def rename_chatlog(self, ghost_id, new_name):
        """Updates the friendly name in the manifest without touching the encrypted file."""
        for file in self.manifest.data["files"]:
            if file["id"] == ghost_id:
                file["name"] = new_name
                self.manifest.save()
                return True
        return False

    def get_all_logs(self):
        """Returns all entries tagged as chatlogs, sorted by date."""
        all_files = self.manifest.get_files()
        chat_logs = [f for f in all_files if f.get("type") == "chatlog"]
        return sorted(chat_logs, key=lambda x: x.get("created_at", 0), reverse=True)


    def remove_chatlog(self, ghost_id):
        """Deletes the encrypted file from disk and removes manifest entry."""
        # 1. Remove from Manifest
        self.manifest.remove_entry(ghost_id)
        
        # 2. Delete the actual .dat file
        file_path = os.path.join(USER_DATA, ghost_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except Exception as e:
                print(f"Error deleting chatlog file: {e}")
        return False