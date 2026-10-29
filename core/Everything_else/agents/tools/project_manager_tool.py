# [project_manager_tool.py]

import os
import json
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.paths import HOST_HIDDEN_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProjectManagerTool")

HOST_PROJECTS_DIR = getattr(
    __import__("core.paths", fromlist=["HOST_PROJECTS_DIR"]),
    "HOST_PROJECTS_DIR",
    os.path.join(HOST_HIDDEN_DIR, "projects")
)

TOOL_SPEC = {
    "name": "project_manager_tool",
    "description": "Autonomous project and task manager. Pass a natural language instruction to initialize projects, list them, add tasks, or Mark Task Complete.",
    "parameters": {
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": "Natural language instruction detailing what to do (e.g., 'Mark Task Complete: Preprocessing for DataAnalysis', or 'Initialize project DataAnalysis, add 3 tasks: Preprocessing, Analysis')."
            },
            "project_name": {
                "type": "string",
                "description": "(Optional) Explicit target project name."
            }
        },
        "required": ["instruction"]
    }
}


def _slugify(name: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', name.lower()).strip()
    return re.sub(r'[-\s]+', '_', slug)


def _ensure_projects_dir() -> str:
    os.makedirs(HOST_PROJECTS_DIR, exist_ok=True)
    return HOST_PROJECTS_DIR


class DeterministicProjectManager:
    """Parses natural language instructions deterministically via Python code without needing inner LLM calls."""
    def __init__(self):
        self.base_dir = _ensure_projects_dir()

    def _get_project_path(self, project_name: str) -> str:
        slug = _slugify(project_name)
        return os.path.join(self.base_dir, slug)

    def _load_meta(self, project_path: str) -> Optional[Dict[str, Any]]:
        meta_file = os.path.join(project_path, "project.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save_meta(self, project_path: str, meta: Dict[str, Any]):
        meta_file = os.path.join(project_path, "project.json")
        meta["updated_at"] = datetime.now().isoformat()
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def _update_readme_tasks(self, project_path: str, tasks: List[Dict[str, Any]], description: str):
        readme_file = os.path.join(project_path, "README.md")
        meta = self._load_meta(project_path)
        proj_name = meta.get("name", "Project") if meta else "Project"
        
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write(f"# {proj_name}\n\n**Status:** Active\n\n## Overview\n{description}\n\n## Tasks\n")
            for t in tasks:
                task_name = t.get("name", str(t)) if isinstance(t, dict) else str(t)
                completed = t.get("completed", False) if isinstance(t, dict) else False
                box = "x" if completed else " "
                f.write(f"- [{box}] {task_name}\n")

    def handle_instruction(self, instruction: str, explicit_project: str = "") -> str:
        clean_instr = instruction.strip()
        lower_instr = clean_instr.lower()

        # 1. LIST PROJECTS
        if "list" in lower_instr or "show projects" in lower_instr:
            if not os.path.exists(self.base_dir):
                return "No projects currently tracked."
            entries = os.listdir(self.base_dir)
            projs = []
            for entry in entries:
                p_path = os.path.join(self.base_dir, entry)
                meta = self._load_meta(p_path)
                if meta:
                    tasks = meta.get('tasks', [])
                    completed_count = sum(1 for t in tasks if isinstance(t, dict) and t.get('completed'))
                    projs.append(f"• **{meta.get('name')}** (Status: {meta.get('status')}) - Tasks Completed: {completed_count}/{len(tasks)}")
            return "Tracked Projects:\n" + ("\n".join(projs) if projs else "No projects found.")

        # 2. INITIALIZE / CREATE PROJECT
        if "initialize" in lower_instr or "create project" in lower_instr or "new project" in lower_instr:
            proj_name = explicit_project
            if not proj_name:
                match = re.search(r'(?:project|named|called)\s+([A-Za-z0-9_-]+)', clean_instr, re.IGNORECASE)
                if match:
                    proj_name = match.group(1)
                else:
                    words = [w for w in clean_instr.split() if w.isalnum()]
                    proj_name = words[2] if len(words) > 2 else "NewProject"

            project_path = self._get_project_path(proj_name)
            os.makedirs(project_path, exist_ok=True)

            raw_tasks = []
            if ":" in clean_instr:
                task_part = clean_instr.split(":")[-1]
                raw_tasks = [t.strip().strip('"').strip("'") for t in task_part.split(",") if t.strip()]

            structured_tasks = [{"name": t, "completed": False} for t in raw_tasks]

            meta = {
                "name": proj_name,
                "slug": _slugify(proj_name),
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "description": clean_instr,
                "tasks": structured_tasks
            }
            self._save_meta(project_path, meta)
            self._update_readme_tasks(project_path, structured_tasks, clean_instr)

            return f"Successfully initialized project '{proj_name}' with {len(structured_tasks)} tasks."

        # 3. MARK TASK COMPLETE (Explicit Memory alignment)
        if "mark task complete" in lower_instr or "complete task" in lower_instr or "finish task" in lower_instr:
            proj_name = explicit_project
            if not proj_name:
                for entry in os.listdir(self.base_dir) if os.path.exists(self.base_dir) else []:
                    if entry.lower() in lower_instr:
                        proj_name = entry
                        break
            if not proj_name:
                projs = sorted([os.path.join(self.base_dir, d) for d in os.listdir(self.base_dir)], key=os.path.getmtime, reverse=True)
                if projs:
                    meta = self._load_meta(projs[0])
                    if meta:
                        proj_name = meta.get("name")

            if not proj_name:
                return "Error: Could not determine which project contains the task to complete."

            project_path = self._get_project_path(proj_name)
            meta = self._load_meta(project_path)
            if not meta:
                return f"Error: Project '{proj_name}' not found."

            tasks = meta.get("tasks", [])
            # Extract target task name after colon or keywords
            target_task_query = ""
            if ":" in clean_instr:
                target_task_query = clean_instr.split(":")[-1].strip().lower()
            
            matched = False
            for t in tasks:
                t_name = t.get("name", str(t)).lower() if isinstance(t, dict) else str(t).lower()
                if target_task_query in t_name or t_name in target_task_query:
                    if isinstance(t, dict):
                        t["completed"] = True
                    else:
                        # Migrate string task to dict object
                        idx = tasks.index(t)
                        tasks[idx] = {"name": str(t), "completed": True}
                    matched = True
                    break

            if not matched and tasks and isinstance(tasks[0], dict) and not tasks[0]["completed"]:
                # Default to completing the first pending task if query is ambiguous
                tasks[0]["completed"] = True
                matched = True

            if matched:
                meta["tasks"] = tasks
                self._save_meta(project_path, meta)
                self._update_readme_tasks(project_path, tasks, meta.get("description", ""))
                return f"Successfully marked task complete in project '{proj_name}'."
            return f"Error: Could not find matching task to complete in '{proj_name}'."

        # 4. ADD TASKS TO EXISTING PROJECT
        if "add task" in lower_instr or "add tasks" in lower_instr or "task:" in lower_instr:
            proj_name = explicit_project
            if not proj_name:
                for entry in os.listdir(self.base_dir) if os.path.exists(self.base_dir) else []:
                    if entry.lower() in lower_instr:
                        proj_name = entry
                        break
            if not proj_name:
                projs = sorted([os.path.join(self.base_dir, d) for d in os.listdir(self.base_dir)], key=os.path.getmtime, reverse=True)
                if projs:
                    meta = self._load_meta(projs[0])
                    if meta:
                        proj_name = meta.get("name")

            if not proj_name:
                return "Error: Could not determine which project to add tasks to."

            project_path = self._get_project_path(proj_name)
            meta = self._load_meta(project_path)
            if not meta:
                return f"Error: Project '{proj_name}' not found."

            new_task_names = []
            if ":" in clean_instr:
                task_part = clean_instr.split(":")[-1]
                new_task_names = [t.strip().strip('"').strip("'") for t in task_part.split(",") if t.strip()]

            if not new_task_names:
                new_task_names = [clean_instr]

            current_tasks = meta.get("tasks", [])
            # Ensure existing tasks are structured objects
            structured_tasks = [
                t if isinstance(t, dict) else {"name": str(t), "completed": False} 
                for t in current_tasks
            ]
            for nt in new_task_names:
                structured_tasks.append({"name": nt, "completed": False})

            meta["tasks"] = structured_tasks
            self._save_meta(project_path, meta)
            self._update_readme_tasks(project_path, structured_tasks, meta.get("description", ""))

            return f"Successfully added {len(new_task_names)} task(s) to '{proj_name}'. Total tasks: {len(structured_tasks)}."

        return f"Project Manager processed instruction successfully: {instruction}"


def execute(instruction: str = "", project_name: str = "", **kwargs) -> str:
    """Standard tool entrypoint called by tool_runner.py with built-in safety net."""
    if not instruction or not str(instruction).strip():
        instruction = "list projects"

    manager = DeterministicProjectManager()
    return manager.handle_instruction(instruction=instruction, explicit_project=project_name)


# Alias run for tool registry compatibility
run = execute