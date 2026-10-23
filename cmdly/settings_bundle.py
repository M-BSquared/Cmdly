"""One file that carries a whole Cmdly setup: settings export and import.

The Data page of the settings writes it and reads it back, so a setup can be
backed up, restored after a reinstall, or copied to the next computer. It
holds:

* ``config``: the settings (``~/.cmdly/config.json``), exactly as
  :class:`cmdly.config.Config` keeps them, minus the window size, which
  belongs to this screen and not to the setup;
* ``browser``: what the page keeps in localStorage for itself. This module
  never reads it. It is carried through so the backup is one file rather than
  two, and ``src/js/settings-transfer.js`` owns what goes into it.

The SSH passwords stay out unless the person asks for them, because the file
is the kind of thing that gets passed on. A file without them never erases
the ones already stored here: a connection that is still the same connection
(same name, host and user) keeps its stored password, and a password is never
handed to a host it was not stored for.

Export and import are both by section, so a file can carry only the buttons,
or an import can take the companion computers from a full file and leave the
connections of this computer alone. ``sections`` names what a file carries; a
section it does not carry is never imported from it, because importing a
section resets every key the file leaves out. Every key of the config belongs
to exactly one section (or is left out on purpose, in ``EXCLUDED_KEYS``); the
test suite fails when a new key is added without one.

A setup written by the first Cmdly export (``{"cmdly": <version>, ...}``,
without ``kind``) is read too, as carrying the sections it has keys for.

stdlib only.
"""
from __future__ import annotations

import copy
import time
from collections.abc import Iterable
from typing import Any

from . import config as config_mod
from . import launcher
from .version import get_version

KIND = "cmdly-settings"
FORMAT = 1

# Section id -> the config keys it carries.
SECTIONS: dict[str, tuple[str, ...]] = {
    "buttons": ("buttons",),
    "companions": ("companions", "active_companion"),
    "connections": ("connections",),
    "appearance": ("ui", "updates"),
}

# Config keys a bundle never carries. ``window`` is the size of the window on
# this screen: on another computer's screen it means nothing. ``agent`` is
# this computer's yes to what an AI agent may do — a setup moved to another
# computer does not carry its permissions along.
EXCLUDED_KEYS: frozenset[str] = frozenset({"window", "agent"})

# The keys a legacy setup carries for each section, the PySide build's
# spellings included (see cmdly.config.migrate).
_LEGACY_KEYS: dict[str, tuple[str, ...]] = {
    "buttons": ("buttons",),
    "companions": ("companions", "companion", "active_companion"),
    "connections": ("connections",),
    "appearance": ("ui", "theme"),
}

BROWSER_PREFIX = "cmdly."


def section_of(key: str) -> str | None:
    """The section a config key is imported with, or None for none."""
    for section, keys in SECTIONS.items():
        if key in keys:
            return section
    return None


def redact(config: dict[str, Any]) -> dict[str, Any]:
    """A deep copy of *config* with every SSH password taken out."""
    out = copy.deepcopy(config)
    for entry in out.get("connections") or []:
        if isinstance(entry, dict):
            entry.pop("password", None)
    return out


def build(config: dict[str, Any], *, sections: Iterable[str] | None = None,
          browser: dict[str, Any] | None = None,
          include_secrets: bool = False) -> dict[str, Any]:
    """Assemble the bundle written to disk by an export.

    *config* is the whole config (passwords included, as
    :meth:`cmdly.config.Config.snapshot` returns it) and *sections* the parts
    to write (every one when None). Only the config keys of those sections go
    in. The result is plain JSON data; the caller writes it.
    """
    chosen = set(SECTIONS) if sections is None else set(sections) & set(SECTIONS)
    cfg = {k: v for k, v in config.items()
           if k not in EXCLUDED_KEYS and section_of(k) in chosen}
    if not include_secrets:
        cfg = redact(cfg)
    return {
        "kind": KIND,
        "format": FORMAT,
        "product": "Cmdly",
        "version": get_version(),
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "secrets": bool(include_secrets),
        "sections": [s for s in SECTIONS if s in chosen],
        "config": copy.deepcopy(cfg),
        "browser": _clean_browser(browser),
    }


def _clean_browser(raw: Any) -> dict[str, str]:
    """Browser entries as ``{key: string}``, anything else dropped."""
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items()
            if isinstance(k, str) and k.startswith(BROWSER_PREFIX) and isinstance(v, str)}


def is_legacy(data: Any) -> bool:
    """Whether *data* is a setup the first Cmdly export wrote."""
    return (isinstance(data, dict) and "kind" not in data
            and any(k in data for keys in _LEGACY_KEYS.values() for k in keys))


def _parse_legacy(data: dict[str, Any]) -> dict[str, Any]:
    sections = {s for s, keys in _LEGACY_KEYS.items() if any(k in data for k in keys)}
    migrated = config_mod.migrate(data)
    # A connection the file names without a password: no key at all, so the
    # merge can tell it from one whose password is deliberately empty.
    given = {c.get("name"): c for c in data.get("connections") or [] if isinstance(c, dict)} \
        if isinstance(data.get("connections"), list) else {}
    for conn in migrated["connections"]:
        if "password" not in given.get(conn["name"], {}):
            conn.pop("password", None)
    version = data.get("cmdly")
    return {
        "version": version if isinstance(version, str) else "",
        "exported_at": "",
        "secrets": False,
        "sections": [s for s in SECTIONS if s in sections],
        "config": {k: v for k, v in migrated.items()
                   if k not in EXCLUDED_KEYS and section_of(k) in sections},
        "browser": {},
    }


def parse(data: Any) -> dict[str, Any]:
    """Check that *data* is a settings bundle and return it normalized.

    Raises ValueError with a sentence a person can act on. A bundle from a
    newer format is refused rather than half applied: whatever that version
    added, this one would silently drop.
    """
    if is_legacy(data):
        return _parse_legacy(data)
    if not isinstance(data, dict) or data.get("kind") != KIND:
        raise ValueError("This is not a Cmdly settings file.")
    fmt = data.get("format")
    if isinstance(fmt, bool) or not isinstance(fmt, int) or fmt < 1:
        raise ValueError("The settings file has no valid format number.")
    if fmt > FORMAT:
        raise ValueError("The settings file was written by a newer Cmdly. Update Cmdly first.")
    config = data.get("config")
    if not isinstance(config, dict):
        raise ValueError("The settings file carries no settings.")
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, list):
        raise ValueError("The settings file does not say which settings it carries.")
    sections = {s for s in raw_sections if isinstance(s, str) and s in SECTIONS}
    return {
        "version": data.get("version") if isinstance(data.get("version"), str) else "",
        "exported_at": data.get("exported_at") if isinstance(data.get("exported_at"), str) else "",
        "secrets": data.get("secrets") is True,
        "sections": [s for s in SECTIONS if s in sections],
        "config": {k: v for k, v in config.items()
                   if k not in EXCLUDED_KEYS and section_of(k) in sections},
        "browser": _clean_browser(data.get("browser")),
    }


def normalize_sections(raw: Any) -> set[str]:
    """The known section ids in *raw*; every section when *raw* is None."""
    if raw is None:
        return set(SECTIONS)
    if not isinstance(raw, list):
        raise ValueError("sections must be a list")
    return {s for s in raw if isinstance(s, str) and s in SECTIONS}


def merge(current: dict[str, Any], imported: dict[str, Any],
          sections: Iterable[str], *, secrets: bool) -> dict[str, Any]:
    """The config that results from importing *imported* over *current*.

    Both are whole configs. For every key of a chosen section the imported
    value replaces the current one, and a key the file leaves out goes back
    to its default, so the result matches the computer that wrote the file.
    Keys of sections not chosen are left exactly as they are. The result is
    normalized the way a config read from disk is (:func:`cmdly.config.migrate`).

    With ``secrets`` false the file was written without the passwords, and the
    stored ones are carried over where the connection is unchanged (see
    :func:`_keep_secrets`).
    """
    out = copy.deepcopy(current)
    chosen = set(sections)
    for section in chosen:
        for key in SECTIONS.get(section, ()):
            if key in imported:
                out[key] = copy.deepcopy(imported[key])
            else:
                out.pop(key, None)
    # Normalized first, so a connection the file names only by host and user
    # is matched under the name it is stored with.
    out = config_mod.migrate(out)
    out["window"] = copy.deepcopy(current.get("window"))
    if not secrets:
        _keep_secrets(out, current, chosen)
    _sync_companion_hosts(out)
    return out


def _keep_secrets(out: dict[str, Any], current: dict[str, Any], chosen: set[str]) -> None:
    """Put the stored passwords back into connections that are still the same.

    Matched on what the password is sent to, never on a name alone: a password
    stored for one host must not follow a renamed entry to another.
    """
    if "connections" not in chosen:
        return
    stored = {
        (e.get("name"), e.get("host"), e.get("username")): e.get("password")
        for e in current.get("connections") or [] if isinstance(e, dict)
    }
    for entry in out.get("connections") or []:
        if not isinstance(entry, dict) or entry.get("password"):
            continue
        password = stored.get((entry.get("name"), entry.get("host"), entry.get("username")))
        if password:
            entry["password"] = password


def _sync_companion_hosts(cfg: dict[str, Any]) -> None:
    """A companion on an SSH connection pings that connection's host.

    The same rule :meth:`cmdly.config.Config.upsert_connection` keeps, here for
    an import that brings the companions and the connections from different
    places.
    """
    hosts = {c["name"]: c["host"] for c in cfg.get("connections") or []}
    for comp in cfg.get("companions") or []:
        if comp.get("type") == launcher.COMPANION_SSH and comp.get("connection") in hosts:
            comp["host"] = hosts[comp["connection"]]


def missing_connections(cfg: dict[str, Any]) -> list[str]:
    """Connection names a button or companion uses that *cfg* does not have.

    Not an error: launch.js asks for such a connection on the first press.
    The import says so, because a file with only the buttons is the usual way
    to end up here.
    """
    have = {c["name"] for c in cfg.get("connections") or []}
    used: list[str] = []
    for b in cfg.get("buttons") or []:
        if b.get("target") == launcher.TARGET_SSH and b.get("connection"):
            used.append(b["connection"])
    for c in cfg.get("companions") or []:
        if c.get("connection"):
            used.append(c["connection"])
    return sorted({name for name in used if name not in have})
