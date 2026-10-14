# [project_engine.py]

import uuid
from datetime import datetime
from .project_manager import load_project_file, save_project_file

class ProjectEngine:
    def __init__(self, username, fernet, manifest_manager):
        self.username = username
        self.fernet = fernet
        self.manifest = manifest_manager  # Access to the Vault manifest
        self.active_project = None

    def load_project(self, filename):
        self.active_project = load_project_file(self.username, filename, self.fernet)
        
        # AUTO-MIGRATE ON LOAD
        if self.active_project:
            self.migrate_legacy_project()
            
        return self.active_project

    # --- GOAL & TASK LOGIC ---
    def add_goal(self, goal_title):
        if not self.active_project: return
        new_goal = {
            "goal_id": f"goal_{uuid.uuid4().hex[:6]}",
            "title": goal_title,
            "tasks": []
        }
        self.active_project.setdefault('goals', []).append(new_goal)
        return self.save()

    def add_task(self, goal_id, task_text):
        for goal in self.active_project.get('goals', []):
            if goal['goal_id'] == goal_id:
                new_task = {
                    "id": f"task_{uuid.uuid4().hex[:8]}",
                    "text": task_text,
                    "status": "not_done", # not_done, in_progress, done
                    "assets": [] # List of manifest IDs
                }
                goal['tasks'].append(new_task)
                
                # Save first, then return the new ID if successful
                if self.save():
                    return new_task['id']
                    
        return False

    # --- TAGGING LOGIC (MANIFEST BRIDGE) ---
    def tag_asset_to_task(self, task_id, asset_id):
        """Standardizes the link between a project task and a vault file."""
        task = self._find_task(task_id)
        if task:
            if "assets" not in task: task["assets"] = []
            if asset_id not in task["assets"]:
                task["assets"].append(asset_id)
                return self.save()
        return False

    def get_resolved_assets(self, task_id):
        """
        Cross-references task assets with the ManifestManager to return
        full file metadata (name, type, size) for the UI cards.
        """
        task = self._find_task(task_id)
        if not task or not task.get("assets"):
            return []

        resolved = []
        vault_files = self.manifest.get_files()
        
        for asset_id in task["assets"]:
            # Match project asset ID to manifest file ID
            match = next((f for f in vault_files if f['id'] == asset_id), None)
            if match:
                resolved.append(match)
            else:
                # Placeholder for recordings/items not in main vault manifest
                resolved.append({"id": asset_id, "name": "Unknown/External Asset", "type": "unknown"})
        return resolved

    def _find_task(self, task_id):
        for goal in self.active_project.get('goals', []):
            for task in goal['tasks']:
                if task['id'] == task_id:
                    return task
        return None

    def save(self):
        if self.active_project:
            return save_project_file(self.username, self.active_project, self.fernet)
        return False


    def get_completion_percentage(self):
        """Calculates total progress based on all goals/tasks."""
        if not self.active_project: return 0
        all_tasks = []
        
        goals = self.active_project.get('goals', [])
        for goal in goals:
            if isinstance(goal, dict):
                all_tasks.extend(goal.get('tasks', []))
            
        if not all_tasks: return 0
        
        done_count = sum(1 for t in all_tasks if t.get('status') == 'done')
        # Ensure we don't divide by zero and return an integer
        return int((done_count / len(all_tasks)) * 100)

    def update_full_project(self, title, description, deadline, goal_titles):
        """
        Updates metadata and syncs goals list. 
        Preserves tasks for goals that remain in the list.
        """
        if not self.active_project: return False
        
        self.active_project['title'] = title
        self.active_project['description'] = description
        self.active_project['deadline'] = deadline

        existing_goals = self.active_project.get('goals', [])
        new_goals_list = []

        for g_title in goal_titles:
            # Check if goal already exists by title to preserve existing tasks/IDs
            existing = next((g for g in existing_goals if isinstance(g, dict) and g['title'] == g_title), None)
            
            if existing:
                new_goals_list.append(existing)
            else:
                # Create a new goal object for brand new titles
                new_goals_list.append({
                    "goal_id": f"goal_{uuid.uuid4().hex[:6]}",
                    "title": g_title,
                    "tasks": []
                })
        
        self.active_project['goals'] = new_goals_list
        return self.save()

    def create_project(self, title, description, deadline):
        new_proj = {
            "title": title,
            "description": description,
            "deadline": deadline,
            "goals": [],
            "status": "ACTIVE",
            "created_at": datetime.now().strftime("%Y-%m-%d")
        }
        # Pass by reference allows save_project_file to add 'internal_id' to new_proj
        success = save_project_file(self.username, new_proj, self.fernet)
        if success:
            self.active_project = new_proj 
        return success


    def migrate_legacy_project(self):
        """Converts old string-based goals into the new dictionary format."""
        if not self.active_project:
            return False

        goals = self.active_project.get('goals', [])
        upgraded_goals = []
        needs_save = False

        for goal in goals:
            if isinstance(goal, str):
                # This is legacy data! Convert it.
                upgraded_goals.append({
                    "goal_id": f"goal_{uuid.uuid4().hex[:6]}",
                    "title": goal,
                    "tasks": []
                })
                needs_save = True
            elif isinstance(goal, dict):
                # This is already compatible data.
                upgraded_goals.append(goal)

        if needs_save:
            print(f"[SYSTEM] Upgrading project schema for: {self.active_project.get('title')}")
            self.active_project['goals'] = upgraded_goals
            return self.save()
        
        return False


    def update_project_details(self, title, description, deadline):
        """Updates the top-level metadata of the active project."""
        if not self.active_project:
            return False
        
        self.active_project['title'] = title
        self.active_project['description'] = description
        self.active_project['deadline'] = deadline
        
        # This calls the save_project_file function from your project_manager.py
        return self.save()


    def update_task_text(self, task_id, new_text):
        for goal in self.active_project.get('goals', []):
            for task in goal.get('tasks', []):
                if task['id'] == task_id:
                    task['text'] = new_text
                    return self.save()
        return False


    def move_task(self, task_id, goal_id, new_status):
        """Moves a task to a different status within a goal."""
        if not self.active_project: return False
        
        task = self._find_task(task_id)
        if task:
            task['status'] = new_status
            return self.save()
        return False


    def update_task_status(self, task_id, new_status):
        """Updates the status of a task by searching through all goals."""
        if not self.active_project: return False
        
        task = self._find_task(task_id)
        if task:
            task['status'] = new_status
            return self.save()
        return False

    def move_task(self, task_id, goal_id, new_status):
        """Moves a task and updates its status."""
        # You can keep this for drag-and-drop between specific goals if needed
        return self.update_task_status(task_id, new_status)

    def delete_task(self, task_id):
        """Locates and removes a task by ID."""
        if not self.active_project: return False
        
        for goal in self.active_project.get('goals', []):
            tasks = goal.get('tasks', [])
            for i, task in enumerate(tasks):
                if task['id'] == task_id:
                    tasks.pop(i)
                    return self.save()
        return False


    def change_task_goal(self, task_id, new_goal_id):
        """Moves a task from its current goal to a new target goal."""
        if not self.active_project: return False
        
        task_to_move = None
        # 1. Find and remove from current goal
        for goal in self.active_project.get('goals', []):
            tasks = goal.get('tasks', [])
            for i, task in enumerate(tasks):
                if task['id'] == task_id:
                    task_to_move = tasks.pop(i)
                    break
            if task_to_move: break
        
        if not task_to_move: return False

        # 2. Add to the new goal
        for goal in self.active_project.get('goals', []):
            if goal['goal_id'] == new_goal_id:
                goal.setdefault('tasks', []).append(task_to_move)
                return self.save()
        
        return False




    def sync_goals(self, new_goal_titles):
        """Updates goal titles by index and adds/removes goals as needed."""
        if not self.active_project: return False

        current_goals = self.active_project.get('goals', [])
    
        updated_goals = []
    
        for i, title in enumerate(new_goal_titles):
            if i < len(current_goals):
                # UPDATE EXISTING: Change the title but KEEP the goal_id and tasks
                goal = current_goals[i]
                goal['title'] = title
                updated_goals.append(goal)
            else:
                # ADD NEW: Create a fresh goal object
                new_goal = {
                    "goal_id": f"goal_{uuid.uuid4().hex[:6]}",
                    "title": title,
                    "tasks": []
                }
                updated_goals.append(new_goal)

        # Note: This will drop goals that were deleted in the dialog
        self.active_project['goals'] = updated_goals
        return self.save()


    def get_project_title(self, filename):
        """Peeks into an encrypted file to return the human-readable title."""
        try:
            temp_data = load_project_file(self.username, filename, self.fernet)
            if temp_data:
                return temp_data.get('title', 'UNTITLED MISSION')
        except Exception:
            pass
        return "UNKNOWN MISSION"


    def delete_active_project(self):
        """Permanently deletes the currently active project file."""
        if not self.active_project or 'internal_id' not in self.active_project:
            return False
            
        from .project_manager import delete_project_file, get_user_project_dir
        import os
        
        filename = self.active_project['internal_id']
        filepath = os.path.join(get_user_project_dir(self.username), filename)
        
        if delete_project_file(filepath):
            self.active_project = None
            return True
        return False

    def link_document_to_project(self, file_id):
        """Adds a Vault file ID to the project's global document list."""
        if not self.active_project: return False
        
        if 'project_documents' not in self.active_project:
            self.active_project['project_documents'] = []
            
        if file_id not in self.active_project['project_documents']:
            self.active_project['project_documents'].append(file_id)
            return self.save()
        return False

    def get_project_documents(self):
        """Cross-references stored IDs with the Manifest to get full file info."""
        if not self.active_project: return []
        
        doc_ids = self.active_project.get('project_documents', [])
        all_vault_files = self.manifest.get_files()
        
        # Filter manifest for files matching the project's stored IDs
        return [f for f in all_vault_files if f['id'] in doc_ids]

    def unlink_document_from_project(self, file_id):
        """Removes a Vault file ID from the project's global document list."""
        if not self.active_project or 'project_documents' not in self.active_project:
            return False
            
        if file_id in self.active_project['project_documents']:
            self.active_project['project_documents'].remove(file_id)
            return self.save()
        return False

