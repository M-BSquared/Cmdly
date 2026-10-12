"""Cmdly's settings: ``~/.cmdly/config.json``.

One file holds the shelf (buttons), the companion computers, the saved SSH
connections and the appearance. It is read once at start, kept in memory, and
written back atomically (a temporary file renamed over the old one) on every
change, so a crash mid-write leaves the previous file, never half of one.

The file is owner-only (0600): the SSH connections in it carry passwords. The
page never sees one; :meth:`Config.public` leaves them out.

Older files are read as they were written (the PySide widget build of Cmdly
saved ``theme`` and ``opacity`` at the top level, and one ``companion`` or a
``companions`` list): :func:`migrate` maps them onto this layout.

Thread-safe: the HTTP server answers on many threads, and every read and
write goes through one lock.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
from typing import Any

from . import launcher
from .paths import cmdly_path

logger = logging.getLogger("cmdly.config")

THEMES = ("auto", "green", "blue", "orange", "pink", "light", "light-orange")
DEFAULT_THEME = "blue"

DEFAULT_UI: dict[str, Any] = {
    "theme": DEFAULT_THEME,
    # The frosted window: the desktop shows through it, blurred on macOS
    # (NSVisualEffectView), tinted by the page's frost on Linux.
    "frosted_window": True,
    # Terminal windows of frosted glass rather than solid.
    "frosted_terminals": True,
    # Terminals as frames inside the Cmdly window instead of windows of their own.
    "terminals_in_app": False,
    # Hide SSH buttons whose companion computer is not online.
    "reachable_only": False,
}

DEFAULT_UPDATES: dict[str, Any] = {
    # Look for a newer release on GitHub (only once a repository is set in
    # cmdly.update_check.REPO; until then nothing is asked either way).
    "check": True,
    # The release whose notice was dismissed with "Skip this version".
    "skipped": "",
}

MIN_W, MIN_H = 260, 360
MAX_W, MAX_H = 4000, 3000


def default_config_path() -> str:
    return cmdly_path("config.json")


def _bool(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def normalize_ui(raw: Any, legacy_theme: Any = None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    theme = src.get("theme", legacy_theme)
    out = dict(DEFAULT_UI)
    out["theme"] = theme if theme in THEMES else DEFAULT_THEME
    for key in ("frosted_window", "frosted_terminals", "terminals_in_app", "reachable_only"):
        out[key] = _bool(src.get(key), DEFAULT_UI[key])
    # An older Cmdly called the frosted window "vibrancy".
    if "vibrancy" in src and "frosted_window" not in src:
        out["frosted_window"] = _bool(src.get("vibrancy"), DEFAULT_UI["frosted_window"])
    return out


def normalize_window(raw: Any, legacy: dict[str, Any] | None = None) -> dict[str, int] | None:
    src = raw if isinstance(raw, dict) else {}
    if not src and legacy:
        src = {"width": legacy.get("window_width"), "height": legacy.get("window_height")}
    try:
        w = int(src.get("width"))
        h = int(src.get("height"))
    except (TypeError, ValueError):
        return None
    if not (MIN_W <= w <= MAX_W and MIN_H <= h <= MAX_H):
        return None
    return {"width": w, "height": h}


def normalize_updates(raw: Any) -> dict[str, Any]:
    """The update check's switch and the release that was dismissed.

    ``check`` is a genuine boolean only: a hand-edited ``"false"`` must not
    read as "on". ``skipped`` is a plain version string; anything that is not
    a version is dropped rather than silencing an update forever.
    """
    # Imported here, not at module scope: config.py is pulled in by almost
    # everything, and update_check drags urllib.request behind it.
    from .update_check import parse_version

    src = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULT_UPDATES)
    out["check"] = _bool(src.get("check"), DEFAULT_UPDATES["check"])
    skipped = src.get("skipped")
    if isinstance(skipped, str) and parse_version(skipped) is not None:
        out["skipped"] = skipped.strip().removeprefix("v")
    return out


def normalize_connections(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    names: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        conn = launcher.coerce_connection(item)
        if conn is None or conn["name"] in names or len(out) >= launcher.MAX_CONNECTIONS:
            continue
        names.add(conn["name"])
        out.append(conn)
    return out


def migrate(data: Any) -> dict[str, Any]:
    """Any config this or an older Cmdly wrote, as a complete current one."""
    src = data if isinstance(data, dict) else {}
    companions = launcher.normalize_companions(src.get("companions"), src.get("companion"))
    out = {
        "buttons": launcher.normalize_buttons(src.get("buttons")),
        "companions": companions,
        "active_companion": launcher.pick_active(companions, src.get("active_companion")),
        "connections": normalize_connections(src.get("connections")),
        "ui": normalize_ui(src.get("ui"), src.get("theme")),
        "window": normalize_window(src.get("window"), src),
        "updates": normalize_updates(src.get("updates")),
    }
    return out


def starter_config() -> dict[str, Any]:
    """A first run: one button, so the shelf shows how it works."""
    cfg = migrate({})
    cfg["buttons"] = [launcher.coerce_button({
        "id": "b_welcome", "label": "System info", "target": launcher.TARGET_LOCAL,
        "directory": "~", "command": "uname -a && uptime",
    })]
    return cfg


class ConfigError(ValueError):
    """A change that cannot be stored, with the reason to show."""


class Config:
    """The live settings and the file behind them."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or default_config_path()
        self._lock = threading.RLock()
        self._data = self._load()

    # ---- file -----------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            data = starter_config()
            self._data = data
            self._write(data)
            return data
        except (OSError, ValueError) as exc:
            # Kept aside rather than overwritten: it may be one comma away
            # from every button the person had.
            logger.error("could not read %s (%s); starting with defaults", self.path, exc)
            self._keep_broken()
            return starter_config()
        return migrate(raw)

    def _keep_broken(self) -> None:
        try:
            os.replace(self.path, self.path + ".broken")
            logger.warning("the unreadable config was kept as %s.broken", self.path)
        except OSError:
            pass

    def _write(self, data: dict[str, Any]) -> None:
        folder = os.path.dirname(self.path) or "."
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".config-", suffix=".json", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def save(self) -> None:
        with self._lock:
            self._write(self._data)

    # ---- reads -----------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """A deep copy of everything, passwords included. Backend use only."""
        with self._lock:
            return copy.deepcopy(self._data)

    def public(self) -> dict[str, Any]:
        """Everything the page may see: no password, ever."""
        with self._lock:
            data = copy.deepcopy(self._data)
        data["connections"] = [launcher.public_connection(c) for c in data["connections"]]
        return data

    @property
    def ui(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data["ui"])

    @property
    def window(self) -> dict[str, int] | None:
        with self._lock:
            w = self._data.get("window")
            return dict(w) if w else None

    @property
    def updates(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data["updates"])

    def connection(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            for c in self._data["connections"]:
                if c["name"] == name:
                    return dict(c)
        return None

    # ---- writes ----------------------------------------------------------

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Apply a partial change from the page and store it.

        Takes any of ``buttons``, ``companions``, ``active_companion``, ``ui``
        and ``updates`` (both merged key by key). Connections have their own calls, because
        the page never holds their passwords and so cannot send the list back.
        """
        if not isinstance(changes, dict):
            raise ConfigError("expected an object")
        with self._lock:
            data = copy.deepcopy(self._data)
            if "buttons" in changes:
                if not isinstance(changes["buttons"], list):
                    raise ConfigError("buttons must be a list")
                data["buttons"] = launcher.normalize_buttons(changes["buttons"])
            if "companions" in changes:
                if not isinstance(changes["companions"], list):
                    raise ConfigError("companions must be a list")
                data["companions"] = launcher.normalize_companions(changes["companions"])
            if "companions" in changes or "active_companion" in changes:
                data["active_companion"] = launcher.pick_active(
                    data["companions"], changes.get("active_companion", data["active_companion"]))
            if "ui" in changes:
                if not isinstance(changes["ui"], dict):
                    raise ConfigError("ui must be an object")
                merged = dict(data["ui"])
                merged.update(changes["ui"])
                data["ui"] = normalize_ui(merged)
            if "updates" in changes:
                if not isinstance(changes["updates"], dict):
                    raise ConfigError("updates must be an object")
                merged = dict(data["updates"])
                merged.update(changes["updates"])
                data["updates"] = normalize_updates(merged)
            self._data = data
            self._write(data)
        return self.public()

    def set_window(self, width: int, height: int) -> None:
        window = normalize_window({"width": width, "height": height})
        if window is None:
            return
        with self._lock:
            if self._data.get("window") == window:
                return
            self._data["window"] = window
            self._write(self._data)

    def upsert_connection(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Save one SSH connection, by name; rename with ``original_name``.

        The page never holds a stored password, so a save without a
        ``password`` key keeps the one already stored. A rename carries the
        new name into every button and companion that used the old one.
        """
        if not isinstance(raw, dict):
            raise ConfigError("expected an object")
        if not isinstance(raw.get("host"), str) or not raw["host"].strip():
            raise ConfigError("Name the host to connect to.")
        problem = launcher.host_error(raw["host"])
        if problem:
            raise ConfigError(problem)
        if "port" in raw and launcher.coerce_port(raw["port"], 0) == 0:
            raise ConfigError("The port has to be a number between 1 and 65535.")
        original = raw.get("original_name")
        with self._lock:
            data = copy.deepcopy(self._data)
            conns = data["connections"]
            entry_raw = dict(raw)
            conn = launcher.coerce_connection(entry_raw)
            if conn is None:
                raise ConfigError("Name the host to connect to.")
            original = original if isinstance(original, str) and original else conn["name"]
            index = next((i for i, c in enumerate(conns) if c["name"] == original), None)
            if conn["name"] != original and any(c["name"] == conn["name"] for c in conns):
                raise ConfigError(f'"{conn["name"]}" is already saved. Pick another name.')
            if "password" not in raw and index is not None:
                conn["password"] = conns[index]["password"]
            if index is None:
                if len(conns) >= launcher.MAX_CONNECTIONS:
                    raise ConfigError("There are too many saved connections already.")
                conns.append(conn)
            else:
                conns[index] = conn
            if conn["name"] != original:
                for b in data["buttons"]:
                    if b["target"] == launcher.TARGET_SSH and b["connection"] == original:
                        b["connection"] = conn["name"]
                for c in data["companions"]:
                    if c["connection"] == original:
                        c["connection"] = conn["name"]
                        # An SSH computer is called what its connection is called.
                        if c["name"] == original:
                            c["name"] = conn["name"]
            # A companion on this connection pings its host: keep them one.
            for c in data["companions"]:
                if c["type"] == launcher.COMPANION_SSH and c["connection"] == conn["name"]:
                    c["host"] = conn["host"]
            self._data = data
            self._write(data)
            return launcher.public_connection(conn)

    def remove_connection(self, name: str) -> None:
        with self._lock:
            data = copy.deepcopy(self._data)
            data["connections"] = [c for c in data["connections"] if c["name"] != name]
            # A computer shown for this connection goes with it.
            data["companions"] = [c for c in data["companions"]
                                  if not (c["type"] == launcher.COMPANION_SSH and c["connection"] == name)]
            data["active_companion"] = launcher.pick_active(data["companions"], data["active_companion"])
            self._data = data
            self._write(data)
