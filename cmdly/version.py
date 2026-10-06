"""Version module: the single source of truth for the Cmdly version.

Reads the repository-root ``VERSION`` file at import time. No other module
may contain a literal version string; it imports from here.
"""
from __future__ import annotations

import pathlib

_VERSION_FILE = pathlib.Path(__file__).resolve().parent.parent / "VERSION"


def _read_version() -> str:
    try:
        return _VERSION_FILE.read_text().strip()
    except OSError:
        return "0.0.0-unknown"


VERSION = _read_version()
__version__ = VERSION


def get_version() -> str:
    """Return the running Cmdly version string."""
    return VERSION
