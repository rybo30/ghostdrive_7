# GhostDrive

GhostDrive is a portable, offline-first desktop app built with PySide6 (Qt for Python). It's designed to run from a USB drive. It combines an encrypted file vault, local LLM chat through `llama.cpp`, and a set of personal tools (projects, inventory, health, games, coding help) behind one passphrase-protected login.

All user data stays on the drive. Data is encrypted with keys derived from your passphrase and a per-user salt file stored next to the vault.

## Features

| Page | What it does |
|------|--------------|
| **My Drive** | Encrypted file store. Files are encrypted with Fernet and stored as `ghost_<uuid>.dat` files, tracked in an encrypted manifest. |
| **Chat** | Local LLM chat with switchable personas and an "AI Council" mode where several expert models debate a question. Also runs operator *protocols* (see below). |
| **Vault** | Encrypted password and secret store. |
| **Projects / Inventory** | Encrypted project tracking and spreadsheet-style inventories with CSV import and export. |
| **Ollie** | Meeting recorder: records audio, transcribes it with Whisper, and summarizes it with a local model. |
| **Sync** | Peer-to-peer sync over LAN/UDP using X25519 key exchange and Ed25519 identities. |
| **Agents** | Builds and deploys background agents (Telegram bot, RSS, weather, market data, web search, document tools). |
| **Health / Games / Coding / Profile** | Health tracking with charts, built-in games, a coding assistant, and profile settings. |

## Requirements

- Python **3.12**. This is the version CI builds with. Newer versions such as 3.14 may not have wheels for `torch` or `llama-cpp-python` yet.
- macOS, Windows or Linux.
- About 5 GB of disk space for dependencies, plus space for any GGUF models you add.

## Setup

```bash
# With uv (recommended)
uv venv --python 3.12 .venv
CMAKE_ARGS="-DGGML_METAL=on" uv pip install --python .venv/bin/python -r requirements.txt   # Metal GPU build on Apple Silicon

# Or with pip
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows and Linux, CI installs CPU wheels first to avoid a long source build:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

## Running

```bash
.venv/bin/python main.py              # Login window, then the main app
.venv/bin/python main.py --daemon     # Background agent daemon
.venv/bin/python main.py --daemon --config path/to/agent.json
```

The first login with a new username creates that user's vault.

### Models

Model weights are **not** included in the repo. The app opens without them, but the Chat, Council, Coding and Ollie features need GGUF files in:

```
core/Everything_else/models/
```

`core/Everything_else/models/models.yaml` maps each persona to a GGUF filename, system prompt and sampling settings. The default persona uses `mistral-7b-instruct-v0.2.Q4_K_M.gguf`. Ollie transcription uses `whisper-large-v3-turbo-q4_0.gguf`.

> `llama-cpp-python` must import successfully. If it doesn't, `model_registry.py` exits the app when the Chat page loads.

## Data layout

| Location | Contents |
|----------|----------|
| `core/Everything_else/vault/` | Per-user salt (`salt_<user>.bin`), secret vault (`ghostvault_<user>.enc`), file manifest and encrypted files. **Never commit this folder.** |
| `core/Everything_else/inventory/<user>/` | Encrypted inventory sheets (`inv_<name>.enc`) |
| `core/Everything_else/projects/`, `health/`, `journal/` | Other per-feature data |
| `~/.ghostdrive/` | Host-side data: agent configs and runtimes, `.master.key` |

Keys are derived with PBKDF2-HMAC-SHA256 (100,000 iterations) from the passphrase and a 16-byte random salt. Peer identities are derived from SHA-256(salt + username + passphrase) and used as Ed25519 (signing) and X25519 (sync) keys. See `core/identity.py`.

## Chat protocols

Chat can run operator commands, either from a dropdown or when the model replies with `Activating <name> protocol`. Examples include `status_report`, `scan_networks`, `blackout_mode` (turns Wi-Fi off), `sweep`, `wipe` and `shred`. They're defined in `core/Everything_else/jynx_operator_ui.py`, and several are **destructive**: `shred` overwrites and permanently deletes the files you select.

## Project structure

```
main.py                    Entry point: sets import paths, then shows the login window or daemon
core/
  paths.py                 Every filesystem location (portable and host)
  identity.py              Passphrase + salt → Ed25519/X25519 identity
  network_manager.py       P2P discovery and sync (UDP)
  platform_utils.py        OS and GPU detection
  ui/                      One module per page, plus login, main window and style_config
  Everything_else/
    ghostvault.py          Secret vault and user creation
    encryption_engine.py   GhostEngine: encrypted file store
    manifest_manager.py    Encrypted index of stored files and folders
    model_registry.py      Loads and unloads llama.cpp models from models.yaml
    jynx_operator_ui.py    Chat protocols (system commands)
    agents/                Agent daemon, Telegram bot, tools
tests/                     pytest suite
GhostDrive*.spec           PyInstaller build specs
```

`main.py` adds the repo root, `core/` and `core/Everything_else/` to `sys.path`. Modules import each other in all three styles (`core.Everything_else.x`, `Everything_else.x`, `x`), so run the app through `main.py`.

## Tests

```bash
uv pip install --python .venv/bin/python pytest   # or: pip install pytest
.venv/bin/python -m pytest
```

The suite covers the parts that don't need a GUI or models: key derivation, the vault, file encryption, identities and shared secrets, the inventory and manifest stores, paths, and chat-protocol parsing. Every test runs in a temporary directory, never touches real vault data, and stubs out the real system commands.

## Building

`.github/workflows/build.yml` builds standalone apps for Windows, macOS and Linux with PyInstaller (`GhostDrive.spec`, `GhostDriveAgents.spec`) whenever a `v*` tag is pushed, or when the workflow is run manually.

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean GhostDrive.spec
pyinstaller --noconfirm --clean GhostDriveAgents.spec
```
