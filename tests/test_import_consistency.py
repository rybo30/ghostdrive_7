"""model_registry keeps the loaded model in module globals (ACTIVE_LLM / ACTIVE_MODEL_ID).

Because main.py puts the repo root, core/ and core/Everything_else/ on sys.path,
the same file can be imported as `model_registry`, `Everything_else.model_registry`
or `core.Everything_else.model_registry` — and Python treats each name as a
separate module with its own globals. Then Chat, the AI Council and Ollie each
track (and load) their own model, doubling RAM use.

This test scans the source (no imports, so it runs without llama.cpp) and
requires every import of model_registry to use the canonical name.
"""

import ast
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANONICAL = "core.Everything_else.model_registry"
SHARED_STATE_MODULES = ["model_registry"]


def _python_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", ".venv", "venv", "build", "dist", "__pycache__", "tests"}]
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _resolve(path, node):
    """Return the absolute dotted module name an ImportFrom/Import refers to."""
    if isinstance(node, ast.ImportFrom):
        if node.level:  # relative import: resolve against the file's package
            pkg = os.path.relpath(os.path.dirname(path), ROOT).split(os.sep)
            base = pkg[: len(pkg) - (node.level - 1)]
            return ".".join(base + ([node.module] if node.module else []))
        return node.module or ""
    return None


def _imports_of(target):
    hits = []
    for path in _python_files():
        with open(path, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=path)
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [_resolve(path, node)]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            for name in names:
                if name and name.split(".")[-1] == target:
                    hits.append((os.path.relpath(path, ROOT), node.lineno, name))
    return hits


@pytest.mark.parametrize("module", SHARED_STATE_MODULES)
def test_shared_state_module_imported_by_one_name(module):
    hits = _imports_of(module)
    assert hits, f"expected at least one import of {module}"
    bad = [h for h in hits if h[2] != f"core.Everything_else.{module}"]
    assert not bad, (
        f"{module} must be imported as core.Everything_else.{module} everywhere; "
        f"other names load a second copy with separate state:\n"
        + "\n".join(f"  {p}:{line} imports {name}" for p, line, name in bad)
    )
