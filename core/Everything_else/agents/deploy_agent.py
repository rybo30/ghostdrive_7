import os
import sys
import shutil
import logging
import platform
import traceback
from pathlib import Path
from typing import Dict, Optional, Tuple, Union, Callable

CORE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from core.paths import (
    USB_FLEET_DIR, 
    AGENT_RUNTIME_DIR, 
    AGENTS_RUNTIME_SRC_DIR,
    get_agent_runtime_dir,
    get_agents_runtime_src_dir,
    get_target_os_key,
    AGENT_TOOLS_DIR,
    USB_TOOLS_DIR,  
    HOST_MODELS_DIR, 
    MODELS_DIR,
)

try:
    from .agent_manifest import AgentManifest
except ImportError:
    from agent_manifest import AgentManifest

logger = logging.getLogger("DeployAgent")
logger.setLevel(logging.INFO)

DEFAULT_FLEET_DIR = Path(USB_FLEET_DIR)


def get_runtime_executable_name(os_key: str = None) -> str:
    key = os_key or get_target_os_key()
    names = {
        "w": "GhostDriveAgents.exe",
        "m": "GhostDriveAgents_mac",
        "l": "GhostDriveAgents"
    }
    return names[key]


def deploy_agent_artifacts(
    agent_id: str,
    target_dir: Union[Path, str],
    source_dir: Union[Path, str] = DEFAULT_FLEET_DIR,
    overwrite: bool = True
) -> Tuple[bool, str, Dict[str, Optional[Path]]]:
    dest_path = Path(target_dir)
    dest_path.mkdir(parents=True, exist_ok=True)

    manifest = AgentManifest(source_dir)
    
    is_valid, validation_msg = manifest.validate_agent_pair(agent_id)
    if not is_valid:
        logger.error(f"[DEPLOY FAILURE] Manifest check failed for '{agent_id}': {validation_msg}")
        return False, f"Manifest validation failed: {validation_msg}", {}

    source_paths = manifest.get_agent_paths(agent_id)
    deployed_paths: Dict[str, Optional[Path]] = {
        "enc_path": None,
        "key_path": None,
        "json_path": None
    }

    try:
        if source_paths["enc_path"] and source_paths["key_path"]:
            src_enc = source_paths["enc_path"]
            src_key = source_paths["key_path"]

            dest_enc = dest_path / src_enc.name
            dest_key = dest_path / src_key.name

            if not overwrite and (dest_enc.exists() or dest_key.exists()):
                return False, f"Target files already exist in {dest_path} and overwrite=False", {}

            shutil.copy2(src_enc, dest_enc)
            shutil.copy2(src_key, dest_key)

            deployed_paths["enc_path"] = dest_enc
            deployed_paths["key_path"] = dest_key

            logger.info(f"[DEPLOY SUCCESS] Transported encrypted pair for '{agent_id}' -> {dest_path}")
            return True, f"Successfully deployed encrypted agent '{agent_id}' to {dest_path}", deployed_paths

        elif source_paths["json_path"]:
            src_json = source_paths["json_path"]
            dest_json = dest_path / src_json.name

            if not overwrite and dest_json.exists():
                return False, f"Target JSON file already exists in {dest_path} and overwrite=False", {}

            shutil.copy2(src_json, dest_json)
            deployed_paths["json_path"] = dest_json

            logger.info(f"[DEPLOY SUCCESS] Transported unencrypted JSON for '{agent_id}' -> {dest_path}")
            return True, f"Successfully deployed unencrypted agent '{agent_id}' to {dest_path}", deployed_paths

        else:
            return False, "No deployable artifacts found for agent.", {}

    except Exception as e:
        err_msg = f"Transport failure during deployment: {str(e)}"
        logger.error(f"[DEPLOY ERROR] {err_msg}")
        traceback.print_exc(file=sys.stderr)
        return False, err_msg, {}


def stage_agent_tools():
    """Copies custom tool scripts from USB storage to host storage."""
    try:
        usb_tools_path = Path(USB_TOOLS_DIR)
        host_tools_path = Path(AGENT_TOOLS_DIR)
        host_tools_path.mkdir(parents=True, exist_ok=True)

        if usb_tools_path.exists():
            shutil.copytree(usb_tools_path, host_tools_path, dirs_exist_ok=True)
            logger.info(f"[DEPLOY] Synced tool scripts from {usb_tools_path} -> {host_tools_path}")
    except Exception as err:
        logger.error(f"[DEPLOY ERROR] Failed staging tool scripts: {err}")


def stage_runtime_executables(target_dir: Path, os_key: str = None):
    """Stages OS agent runtime binary and dependencies strictly into the target host directory."""
    try:
        dest_path = Path(target_dir)
        dest_path.mkdir(parents=True, exist_ok=True)

        key = os_key or get_target_os_key()
        exe_name = get_runtime_executable_name(key)
        src_runtime_dir = Path(get_agents_runtime_src_dir(key))

        if getattr(sys, 'frozen', False):
            src_exe = src_runtime_dir / exe_name
            dest_exe = dest_path / exe_name

            if not src_exe.exists():
                raise FileNotFoundError(f"Missing source runtime binary at '{src_exe}'")

            if not dest_exe.exists() or src_exe.resolve() != dest_exe.resolve():
                try:
                    shutil.copy2(src_exe, dest_exe)
                    if key != "w":
                        os.chmod(dest_exe, 0o755)
                    logger.info(f"[DEPLOY] Staged binary -> {dest_exe}")
                except PermissionError:
                    logger.warning(f"[DEPLOY] {dest_exe.name} locked. Skipping overwrite.")

            internal_dir = src_runtime_dir / "_internal"
            dest_internal = dest_path / "_internal"
            if internal_dir.exists() and internal_dir.resolve() != dest_internal.resolve():
                shutil.copytree(internal_dir, dest_internal, dirs_exist_ok=True)
                logger.info(f"[DEPLOY] Synced dependencies -> {dest_internal}")
        else:
            script_path = Path(__file__).resolve().parent / "daemon.py"
            if script_path.exists():
                shutil.copy2(script_path, dest_path / "daemon.py")
                logger.info(f"[DEPLOY] Staged script -> {dest_path / 'daemon.py'}")

    except Exception as err:
        logger.error(f"[DEPLOY ERROR] Critical failure during executable staging: {err}")
        raise err


def deploy_agent(
    agent_or_id: Union[str, dict],
    target_dir: Union[Path, str] = None,
    source_dir: Union[Path, str] = DEFAULT_FLEET_DIR,
    progress_callback: Optional[Callable[[int], None]] = None,
    os_key: str = None
) -> str:
    key = os_key or get_target_os_key()
    host_target = Path(target_dir or get_agent_runtime_dir(key))

    if progress_callback:
        progress_callback(10)

    # 1. Deploy artifacts
    success, msg, deployed_paths = deploy_agent_artifacts(
        agent_id=agent_or_id if isinstance(agent_or_id, str) else agent_or_id.get("agent_id"),
        target_dir=host_target,
        source_dir=source_dir,
        overwrite=True
    )

    if not success:
        raise RuntimeError(f"Deployment failed: {msg}")

    dest_file = deployed_paths.get("enc_path") or deployed_paths.get("json_path")

    if progress_callback:
        progress_callback(40)

    # 2. Stage tools
    stage_agent_tools()

    if progress_callback:
        progress_callback(60)

    # 3. Stage GGUF models
    try:
        from decrypt_agent import decrypt_agent_config
        cfg = decrypt_agent_config(dest_file)
        model_setting = cfg.get("model_path")

        if model_setting:
            model_filename = os.path.basename(model_setting)
            usb_source_model = os.path.join(MODELS_DIR, model_filename)
            source_model_path = usb_source_model if os.path.exists(usb_source_model) else model_setting

            if os.path.exists(source_model_path):
                os.makedirs(HOST_MODELS_DIR, exist_ok=True)
                host_model_dest = os.path.join(HOST_MODELS_DIR, model_filename)

                if not os.path.exists(host_model_dest):
                    logger.info(f"[DEPLOY] Copying model {model_filename} -> {HOST_MODELS_DIR}...")
                    shutil.copy2(source_model_path, host_model_dest)
            else:
                logger.warning(f"[DEPLOY WARNING] Model file '{model_filename}' not found at {usb_source_model}")

    except Exception as err:
        logger.warning(f"[DEPLOY] Non-fatal issue staging model dependencies: {err}")

    if progress_callback:
        progress_callback(80)

    # 4. Stage OS execution binary
    stage_runtime_executables(host_target, os_key=key)

    if progress_callback:
        progress_callback(100)

    return str(dest_file)