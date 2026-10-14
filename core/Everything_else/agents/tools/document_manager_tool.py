# document_manager_tool.py

import os
import re
import logging
from typing import Optional, List

from core.paths import HOST_HIDDEN_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DocumentManagerTool")

HOST_PROJECTS_DIR = getattr(
    __import__("core.paths", fromlist=["HOST_PROJECTS_DIR"]),
    "HOST_PROJECTS_DIR",
    os.path.join(HOST_HIDDEN_DIR, "projects")
)

TOOL_SPEC = {
    "name": "document_manager_tool",
    "description": "Manages, creates, reads, edits, appends to, deletes, and lists documents inside a local project workspace folder.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "read", "edit", "delete", "list"],
                "description": "File action to perform inside project workspace: 'create', 'read', 'edit', 'delete', or 'list'."
            },
            "project_name": {
                "type": "string",
                "description": "Name or title of the project workspace."
            },
            "filename": {
                "type": "string",
                "description": "Relative filename or path within the project workspace (e.g. 'notes.md', 'specs/hardware.txt', 'script.py')."
            },
            "content": {
                "type": "string",
                "description": "Text content to write or append when creating/editing a file."
            },
            "mode": {
                "type": "string",
                "enum": ["overwrite", "append"],
                "description": "Edit mode: 'overwrite' replaces file content; 'append' adds content to the bottom of the file. Default is 'overwrite'."
            }
        },
        "required": ["action", "project_name"]
    }
}


def _slugify(name: str) -> str:
    """Converts a project title into a clean directory slug."""
    slug = re.sub(r'[^\w\s-]', '', name.lower()).strip()
    return re.sub(r'[-\s]+', '_', slug)


def _get_project_dir(project_name: str) -> Optional[str]:
    """Resolves and validates project directory path."""
    if not project_name:
        return None
    slug = _slugify(project_name)
    project_path = os.path.join(HOST_PROJECTS_DIR, slug)
    return project_path if os.path.exists(project_path) else None


def _get_safe_filepath(project_path: str, filename: str) -> Optional[str]:
    """Ensures requested file path stays strictly sandboxed within the project directory."""
    if not filename:
        return None
    target_path = os.path.abspath(os.path.join(project_path, filename))
    if not target_path.startswith(os.path.abspath(project_path)):
        logger.warning(f"Directory traversal attempt blocked: {filename}")
        return None
    return target_path


def create_document(project_name: str, filename: str, content: str = "") -> str:
    """Creates a new document inside the project folder."""
    project_dir = _get_project_dir(project_name)
    if not project_dir:
        return f"Error: Project '{project_name}' not found."

    file_path = _get_safe_filepath(project_dir, filename)
    if not file_path:
        return f"Error: Invalid or un-sandboxed filename '{filename}'."

    if os.path.exists(file_path):
        return f"File '{filename}' already exists in project '{project_name}'. Use action='edit' to modify it."

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Successfully created document '{filename}' in project '{project_name}'."


def read_document(project_name: str, filename: str) -> str:
    """Reads content from an existing document."""
    project_dir = _get_project_dir(project_name)
    if not project_dir:
        return f"Error: Project '{project_name}' not found."

    file_path = _get_safe_filepath(project_dir, filename)
    if not file_path or not os.path.exists(file_path):
        return f"Error: Document '{filename}' not found in project '{project_name}'."

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"=== DOCUMENT: {filename} ({project_name}) ===\n{content}"
    except Exception as e:
        return f"Error reading document '{filename}': {e}"


def edit_document(project_name: str, filename: str, content: str = "", mode: str = "overwrite") -> str:
    """Modifies or appends to an existing document."""
    project_dir = _get_project_dir(project_name)
    if not project_dir:
        return f"Error: Project '{project_name}' not found."

    file_path = _get_safe_filepath(project_dir, filename)
    if not file_path:
        return f"Error: Invalid filename '{filename}'."

    write_mode = "a" if mode.lower() == "append" else "w"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, write_mode, encoding="utf-8") as f:
        if write_mode == "a":
            f.write(f"\n{content}")
        else:
            f.write(content)

    action_word = "appended to" if mode.lower() == "append" else "overwritten"
    return f"Successfully {action_word} document '{filename}' in project '{project_name}'."


def delete_document(project_name: str, filename: str) -> str:
    """Deletes a document from the project workspace."""
    project_dir = _get_project_dir(project_name)
    if not project_dir:
        return f"Error: Project '{project_name}' not found."

    file_path = _get_safe_filepath(project_dir, filename)
    if not file_path or not os.path.exists(file_path):
        return f"Error: Document '{filename}' not found in project '{project_name}'."

    try:
        os.remove(file_path)
        return f"Successfully deleted document '{filename}' from project '{project_name}'."
    except Exception as e:
        return f"Error deleting document '{filename}': {e}"


def list_documents(project_name: str) -> str:
    """Lists all files stored in a project's workspace."""
    project_dir = _get_project_dir(project_name)
    if not project_dir:
        return f"Error: Project '{project_name}' not found."

    files_list = []
    for root, _, files in os.walk(project_dir):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), project_dir)
            files_list.append(rel_path)

    if not files_list:
        return f"No documents currently in project '{project_name}' workspace."

    output = [f"Documents in Project '{project_name}':"]
    for f in sorted(files_list):
        output.append(f"- `{f}`")

    return "\n".join(output)


def run(action: str, project_name: str = "", filename: str = "", content: str = "", mode: str = "overwrite", **kwargs) -> str:
    """Tool execution dispatcher."""
    act = action.lower()
    if act == "create":
        return create_document(project_name=project_name, filename=filename, content=content)
    elif act == "read":
        return read_document(project_name=project_name, filename=filename)
    elif act == "edit":
        return edit_document(project_name=project_name, filename=filename, content=content, mode=mode)
    elif act == "delete":
        return delete_document(project_name=project_name, filename=filename)
    elif act == "list":
        return list_documents(project_name=project_name)
    else:
        return f"Error: Unknown action '{action}' for document_manager_tool."