# [manifest_manager.py]

import json
import os
import time
from core.ui.style_config import T
from core.paths import USER_DATA 

class ManifestManager:
    def __init__(self, engine, username="default"):
        # Catch if login logic passes a string path instead of engine object
        self.engine = None if isinstance(engine, str) else engine
        self.username = username
        self.vault_path = USER_DATA 
        
        # Initialize container data layout structure
        self.data = {"files": [], "folders": ["Personal"]}
        self.manifest_file = None 
        
        # Resolve target manifest file path and load if valid credentials exist
        self._resolve_manifest_path()
        if self.engine and self.username != "default":
            self._load()

    def set_engine(self, engine, username=None):
        """Called by login logic to pivot from 'default' to the real authenticated user context."""
        if isinstance(engine, str): 
            return # Defend against string parameters leaked from legacy paths
        
        self.engine = engine
        if username:
            self.username = username
        
        # Synchronize location mapping and ingest user records from storage
        self.vault_path = USER_DATA
        self._resolve_manifest_path()
        self._load()

    def _resolve_manifest_path(self):
        """Internal helper to calculate file naming properties cleanly."""
        if self.username and self.username != "default":
            self.manifest_file = os.path.join(self.vault_path, f"vault_manifest_{self.username}.enc")
        else:
            self.manifest_file = None

    def _load(self):
        """Attempts to read and decrypt the secure manifest from local storage."""
        if self.manifest_file and os.path.exists(self.manifest_file) and self.engine:
            try:
                decrypted_data = self.engine.decrypt_file_to_memory_direct(self.manifest_file)
                self.data = json.loads(decrypted_data)
            except Exception as e:
                print(f"Manifest Load Error: {e}")

    def save(self):
        """Encrypts and commits current virtual filesystem manifest indexing structure to storage."""
        # Fallback tracking resolution step if username updated without manifest_file rebuilding
        if self.engine and self.username != "default" and not self.manifest_file:
            self._resolve_manifest_path()

        # DEFENSE CLOSURE: Abandon file persistence execution if critical dependencies missing
        if not self.engine or not self.manifest_file or self.username == "default":
            return

        try:
            json_data = json.dumps(self.data, indent=4).encode()
            encrypted_token = self.engine.fernet.encrypt(json_data)
            
            with open(self.manifest_file, "wb") as f:
                f.write(encrypted_token)
        except Exception as e:
            print(f"Manifest Save Exception Encountered: {e}")

    def add_entry(self, name, id, size, file_type, folder="Recent Files"):
        # Capture current epoch time for high-precision sorting
        current_timestamp = time.time() 
    
        entry = {
            "id": id, 
            "name": name, \
            "size": size,
            "type": file_type, 
            "folder": folder, 
            "created_at": current_timestamp  # Use a dedicated key for sorting
        }
        self.data["files"].append(entry)
        self.save()
    
    def get_files(self):
        return self.data.get("files", [])

    def get_folders(self):
        return self.data.get("folders", [])

    def add_folder(self, folder_name):
        if folder_name not in self.data["folders"]:
            self.data["folders"].append(folder_name)
            self.save()

    def remove_entry(self, file_id):
        self.data["files"] = [f for f in self.data["files"] if f["id"] != file_id]
        self.save()

    def remove_folder(self, folder_name):
        """Removes a folder designation and saves the manifest."""
        if folder_name in self.data.get("folders", []):
            self.data["folders"].remove(folder_name)
            self.save()

    def update_file_folder(self, file_id, new_folder):
        """Updates the folder attribute for a specific file object."""
        for file in self.data.get("files", []):
            if file["id"] == file_id:
                file["folder"] = new_folder
                break
        self.save()

    def get_entries_by_category(self, category):
        """Returns all file entries matching the specified category/file_type."""
        return [f for f in self.data.get("files", []) if f.get("type") == category or f.get("category") == category]