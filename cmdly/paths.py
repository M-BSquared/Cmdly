"""Where Cmdly keeps its state, spelled the way the host spells paths.

Every default location is under ``~/.cmdly``. Built with ``os.path.join``
rather than ``expanduser("~/.cmdly/...")``, which on Windows comes out with
mixed separators.
"""
from __future__ import annotations

import os

CMDLY_DIR_NAME = ".cmdly"
# Overrides the state folder as a whole: the tests, and a second instance
# that should not share the first one's buttons.
HOME_ENV = "CMDLY_HOME"


def cmdly_home() -> str:
    """Absolute path of ``~/.cmdly`` (or ``$CMDLY_HOME``), with the host's separators."""
    override = os.environ.get(HOME_ENV, "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(os.path.expanduser("~"), CMDLY_DIR_NAME)


def cmdly_path(*parts: str) -> str:
    """``~/.cmdly`` joined with *parts*."""
    return os.path.join(cmdly_home(), *parts)
