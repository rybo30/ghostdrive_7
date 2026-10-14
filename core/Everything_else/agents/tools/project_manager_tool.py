# project_manager_tool.py

import os
import json
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.paths import EVERYTHING_ELSE, HOST_HIDDEN_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProjectManagerTool")

# Define Host Projects Directory
HOST_PROJECTS_DIR = getattr(
    __import__("core.paths", fromlist=["HOST_PROJECTS_DIR"]),
    "HOST_PROJECTS_DIR",
    os.path.join(HOST_HIDDEN_DIR, "projects")
)

TOOL_SPEC = {
    "name": "project_manager_tool",
    "description": "Manages, tracks, creates, updates, and inspects long-term user projects, goals, and ideas stored locally on the host system.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "update", "list", "get", "add_note"],
                "description": "Action to perform: 'create' a new project, 'update' status or details, 'list' active projects, 'get' details of a project, or 'add_note' to write project notes."
            },
            "project_name": {
                "type": "string",
                "description": "Name or title of the project."
            },
            "description": {
                "type": "string",
                "description": "Brief description, goals, or context for the project."
            },
            "status": {
                "type": "string",
                "enum": ["planning", "active", "paused", "completed"],
                "description": "Current status of the project (default: 'planning')."
            },
            "note_content": {
                "type": "string",
                "description": "Content of the note, requirement, or update to append to project logs."
            },
            "tasks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of action items, goals, or tasks associated with the project."
            }
        },
        "required": ["action"]
    }
}


def _slugify(name: str) -> str:
    """Converts a project title into a clean directory slug."""
    slug = re.sub(r'[^\w\s-]', '', name.lower()).strip()
    return re.sub(r'[-\s]+', '_', slug)


def _ensure_projects_dir() -> str:
    """Ensures host project directory exists."""
    os.makedirs(HOST_PROJECTS_DIR, exist_ok=True)
    return HOST_PROJECTS_DIR


def create_project(project_name: str, description: str = "", status: str = "planning", tasks: Optional[List[str]] = None) -> str:
    """Creates a new project directory with metadata files."""
    if not project_name:
        return "Error: Project name is required to create a project."

    base_dir = _ensure_projects_dir()
    slug = _slugify(project_name)
    project_path = os.path.join(base_dir, slug)

    if os.path.exists(project_path):
        return f"Project '{project_name}' already exists at {project_path}."

    os.makedirs(project_path, exist_ok=True)

    meta = {
        "name": project_name,
        "slug": slug,
        "status": status,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "description": description,
        "tasks": tasks or []
    }

    meta_file = os.path.join(project_path, "project.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    readme_file = os.path.join(project_path, "README.md")
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(f"# {project_name}\n\n")
        f.write(f"**Status:** {status.capitalize()}\n")
        f.write(f"**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"## Overview\n{description if description else 'No description provided.'}\n\n")
        
        if tasks:
            f.write("## Initial Tasks\n")
            for task in tasks:
                f.write(f"- [ ] {task}\n")
            f.write("\n")

        f.write("## Notes & Progress\n- Project initialized.\n")

    return f"Successfully created project '{project_name}' at '{project_path}'."


def list_projects() -> str:
    """Lists all tracked host projects and their statuses."""
    base_dir = _ensure_projects_dir()
    entries = os.listdir(base_dir)
    projects = []

    for entry in entries:
        folder = os.path.join(base_dir, entry)
        meta_file = os.path.join(folder, "project.json")
        if os.path.isdir(folder) and os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    projects.append(data)
            except Exception:
                continue

    if not projects:
        return "No projects currently tracked."

    output = ["Tracked Projects:"]
    for p in projects:
        output.append(f"- **{p.get('name')}** (`{p.get('slug')}`): Status = {p.get('status', 'N/A')} | Tasks = {len(p.get('tasks', []))}")

    return "\n".join(output)


def get_project(project_name: str) -> str:
    """Retrieves metadata, file list, and overview of a specific project."""
    base_dir = _ensure_projects_dir()
    slug = _slugify(project_name)
    project_path = os.path.join(base_dir, slug)

    meta_file = os.path.join(project_path, "project.json")
    readme_file = os.path.join(project_path, "README.md")

    if not os.path.exists(meta_file):
        return f"Error: Project '{project_name}' not found."

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    readme_content = ""
    if os.path.exists(readme_file):
        with open(readme_file, "r", encoding="utf-8") as f:
            readme_content = f.read()

    # Collect project documents inventory
    doc_files = []
    for root, _, files in os.walk(project_path):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), project_path)
            if rel_path not in ["project.json"]:
                doc_files.append(rel_path)

    docs_summary = "\n".join([f"- `{f}`" for f in sorted(doc_files)]) if doc_files else "No documents created yet."

    return (
        f"=== PROJECT INFO ({meta.get('name')}) ===\n"
        f"Path: {project_path}\n"
        f"Status: {meta.get('status')}\n"
        f"Created: {meta.get('created_at')}\n\n"
        f"=== WORKSPACE DOCUMENTS ===\n"
        f"{docs_summary}\n\n"
        f"=== README.md ===\n"
        f"{readme_content}"
    )


def add_note(project_name: str, note_content: str) -> str:
    """Appends notes or progress entries to a project's README.md."""
    if not project_name or not note_content:
        return "Error: Both project_name and note_content are required."

    base_dir = _ensure_projects_dir()
    slug = _slugify(project_name)
    project_path = os.path.join(base_dir, slug)
    readme_file = os.path.join(project_path, "README.md")

    if not os.path.exists(readme_file):
        return f"Error: Project '{project_name}' not found."

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(readme_file, "a", encoding="utf-8") as f:
        f.write(f"\n### Update ({timestamp})\n{note_content}\n")

    return f"Successfully added note to project '{project_name}'."


def update_project(project_name: str, status: Optional[str] = None, tasks: Optional[List[str]] = None) -> str:
    """Updates status or tasks for an existing project."""
    base_dir = _ensure_projects_dir()
    slug = _slugify(project_name)
    project_path = os.path.join(base_dir, slug)
    meta_file = os.path.join(project_path, "project.json")

    if not os.path.exists(meta_file):
        return f"Error: Project '{project_name}' not found."

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    if status:
        meta["status"] = status
    if tasks:
        meta["tasks"] = list(dict.fromkeys(meta.get("tasks", []) + tasks))
    
    meta["updated_at"] = datetime.now().isoformat()

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return f"Successfully updated project '{project_name}'."


def run(action: str, project_name: str = "", description: str = "", status: str = "planning", note_content: str = "", tasks: Optional[List[str]] = None, **kwargs) -> str:
    """Execution dispatcher for ToolRegistry."""
    action = action.lower()
    if action == "create":
        return create_project(project_name=project_name, description=description, status=status, tasks=tasks)
    elif action == "list":
        return list_projects()
    elif action == "get":
        return get_project(project_name=project_name)
    elif action == "add_note":
        return add_note(project_name=project_name, note_content=note_content)
    elif action == "update":
        return update_project(project_name=project_name, status=status, tasks=tasks)
    else:
        return f"Error: Unknown action '{action}' for project_manager_tool."