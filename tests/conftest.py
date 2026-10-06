"""Shared pytest setup for the Cmdly test suite."""
from __future__ import annotations

import os
import sys

import pytest

# The tests import ``cmdly`` from this checkout, wherever pytest is run from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def cmdly_home(tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Every test gets its own ``~/.cmdly``; none may touch the real one."""
    home = tmp_path / "cmdly-home"
    monkeypatch.setenv("CMDLY_HOME", str(home))
    return str(home)
