# [document_manager_tool.py]

import os
import re
import json
import logging
from typing import Optional, List, Dict, Any

from core.paths import HOST_HIDDEN_DIR
from core.Everything_else.agents.ram_manager import RAMManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DocumentManagerTool")

HOST_PROJECTS_DIR = getattr(
    __import__("core.paths", fromlist=["HOST_PROJECTS_DIR"]),
    "HOST_PROJECTS_DIR",
    os.path.join(HOST_HIDDEN_DIR, "projects")
)

TOOL_SPEC = {
    "name": "document_manager_tool",
    "description": "Autonomous document and workspace file manager sub-agent. Pass a natural language instruction to create, read, edit, append to, or list files within local project folders recursively in a single run.",
    "parameters": {
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": "Natural language instruction detailing what documents to create, edit, read, or manage (e.g., 'Create a technical spec in specs/networking.md and append progress notes to notes.md')."
            },
            "project_name": {
                "type": "string",
                "description": "(Optional) Target project workspace name."
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


class DocumentManagerSubAgent:
    """Encapsulates self-contained recursive file system operations and workspace management."""
    def __init__(self, ram_manager: RAMManager):
        self.ram_manager = ram_manager
        self.base_dir = _ensure_projects_dir()

    def _get_project_dir(self, project_name: str) -> Optional[str]:
        if not project_name:
            return None
        slug = _slugify(project_name)
        project_path = os.path.join(self.base_dir, slug)
        return project_path if os.path.exists(project_path) else None

    def _get_safe_filepath(self, project_path: str, filename: str) -> Optional[str]:
        if not filename:
            return None
        target_path = os.path.abspath(os.path.join(project_path, filename))
        if not target_path.startswith(os.path.abspath(project_path)):
            logger.warning(f"Directory traversal attempt blocked: {filename}")
            return None
        return target_path

    def _get_workspace_inventory(self, project_path: str) -> List[str]:
        files_list = []
        if not os.path.exists(project_path):
            return files_list
        for root, _, files in os.walk(project_path):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), project_path)
                files_list.append(rel_path)
        return files_list

    def execute_loop(self, instruction: str, target_project: str = "", max_steps: int = 4) -> str:
        """Executes a recursive multi-step planning and file-mutation loop internally."""
        action_log = []

        # Resolve available project directories for context
        available_projects = []
        if os.path.exists(self.base_dir):
            available_projects = [d for d in os.listdir(self.base_dir) if os.path.isdir(os.path.join(self.base_dir, d))]

        for step in range(max_steps):
            # Gather current workspace inventory for the targeted project if known
            current_project_dir = self._get_project_dir(target_project)
            workspace_files = self._get_workspace_inventory(current_project_dir) if current_project_dir else []

            system_prompt = """You are an autonomous Document & Workspace Management Sub-Agent.
Your job is to read user instructions, inspect available projects and workspace files, and execute file mutations (create, edit, append, read, or list files).

Available Projects on Host: {projects}
Target Project Current Files: {files}

INSTRUCTIONS:
Determine the exact file operation to execute for the current step. Operations include:
- 'create': Create a new file with text content.
- 'edit': Overwrite or append content to an existing file.
- 'read': Read content from a file.
- 'list': List all files in the workspace.
- 'done': If all requirements of the user's instruction are fulfilled.

Respond STRICTLY in JSON format:
```json
{{
  "thought": "Reasoning for this specific step",
  "operation": "create | edit | read | list | done",
  "project_name": "Target project name",
  "args": {{
    "filename": "relative/path/to/file.md",
    "content": "Full text content to write or edit",
    "mode": "overwrite | append"
  }},
  "continue_loop": true
}}
```"""

            formatted_prompt = system_prompt.format(
                projects=json.dumps(available_projects),
                files=json.dumps(workspace_files)
            )
            full_prompt = f"{formatted_prompt}\n\nUser Instruction: \"{instruction}\"\nPrevious Actions Taken: {json.dumps(action_log)}\n\nNext Action JSON:"

            try:
                response = self.ram_manager.generate_response(prompt=full_prompt, max_tokens=512)
                plan = self._parse_json(response)

                if not isinstance(plan, dict):
                    break

                operation = plan.get("operation", "done").lower()
                proj_name = plan.get("project_name", target_project).strip()
                args = plan.get("args", {})
                should_continue = plan.get("continue_loop", False)
                thought = plan.get("thought", "")

                if operation == "done" or not proj_name:
                    break

                # Execute File Mutation Locally
                result_msg = self._mutate_workspace_state(operation, proj_name, args)
                action_log.append({
                    "step": step + 1,
                    "thought": thought,
                    "operation": operation,
                    "project": proj_name,
                    "result": result_msg
                })

                if not should_continue:
                    break

            except Exception as e:
                logger.error(f"[DocumentManagerSubAgent] Error in recursive step {step + 1}: {e}")
                break

        if not action_log:
            return self._fallback_deterministic_execution(instruction, target_project)

        summary_lines = ["=== DOCUMENT MANAGER EXECUTION SUMMARY ==="]
        for act in action_log:
            summary_lines.append(f"• [{act['operation'].upper()}] Project '{act['project']}': {act['result']}")
        
        return "\n".join(summary_lines)

    def _mutate_workspace_state(self, operation: str, project_name: str, args: Dict[str, Any]) -> str:
        project_dir = self._get_project_dir(project_name)
        if not project_dir:
            # Auto-create project directory if it doesn't exist yet so documents can be housed
            slug = _slugify(project_name)
            project_dir = os.path.join(self.base_dir, slug)
            os.makedirs(project_dir, exist_ok=True)

        filename = args.get("filename", "")
        content = args.get("content", "")
        mode = args.get("mode", "overwrite").lower()

        file_path = self._get_safe_filepath(project_dir, filename)
        if not file_path:
            return f"Error: Invalid or un-sandboxed filename '{filename}'."

        if operation == "create":
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully created document '{filename}'."

        elif operation == "edit":
            write_mode = "a" if mode == "append" else "w"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, write_mode, encoding="utf-8") as f:
                if write_mode == "a":
                    f.write(f"\n{content}")
                else:
                    f.write(content)
            return f"Successfully {'appended to' if write_mode == 'a' else 'overwritten'} document '{filename}'."

        elif operation == "read":
            if not os.path.exists(file_path):
                return f"Error: Document '{filename}' not found."
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()
            return f"Read {len(data)} characters from '{filename}'."

        elif operation == "list":
            files = self._get_workspace_inventory(project_dir)
            return f"Workspace inventory: {', '.join(files) if files else 'Empty workspace'}"

        return f"Unknown operation '{operation}'."

    def _fallback_deterministic_execution(self, instruction: str, project_name: str) -> str:
        project_dir = self._get_project_dir(project_name)
        if not project_dir:
            return f"Error: Project '{project_name}' not found for document operation."
        files = self._get_workspace_inventory(project_dir)
        return f"Workspace Documents for '{project_name}': {', '.join(files) if files else 'No documents found.'}"

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        clean_text = text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0]
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0]
        
        try:
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(clean_text[start:end+1])
        except Exception:
            pass
        return None


def execute(instruction: str, project_name: str = "", **kwargs) -> str:
    """Standard tool entrypoint called by tool_runner.py."""
    ram_mgr = RAMManager()
    sub_agent = DocumentManagerSubAgent(ram_manager=ram_mgr)
    return sub_agent.execute_loop(instruction=instruction, target_project=project_name)


# Alias run for tool registry compatibility
run = execute