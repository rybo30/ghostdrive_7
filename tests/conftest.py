"""Shared test setup.

Mirrors the import paths main.py sets up, so modules that use either
`core.X`, `Everything_else.X` or bare `X` imports all resolve.
"""

import os
import sys

import pytest
from cryptography.fernet import Fernet

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (os.path.join(ROOT, "core", "Everything_else"), os.path.join(ROOT, "core"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def fernet():
    return Fernet(Fernet.generate_key())
