"""Settings export and import (``cmdly/settings_bundle.py``).

``cmdly.server.Handler`` inherits SettingsRoutes, and the @route registry
(``cmdly/routing.py``) wires them like the handlers in the server itself.
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import tempfile
import time
from typing import Any

from .. import settings_bundle
from ..routing import route

logger = logging.getLogger("cmdly.server")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9-]+", "-", text).strip("-").lower()[:40]


def settings_export_dir() -> str:
    """Where a settings export goes by default: Downloads, else the home folder.

    Not under ``~/.cmdly``: this file is made to be carried to another
    computer, and a hidden folder is where it gets lost.
    """
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")
    return downloads if os.path.isdir(downloads) else home


def default_settings_filename() -> str:
    """``cmdly-settings_<host>_<YYYY-MM-DD_HH-MM>.json``: which computer, and when."""
    stamp = time.strftime("%Y-%m-%d_%H-%M")
    try:
        host = _slug(socket.gethostname().split(".")[0])
    except OSError:
        host = ""
    return f"cmdly-settings_{host}_{stamp}.json" if host else f"cmdly-settings_{stamp}.json"


def safe_filename(raw: Any, fallback: str, suffix: str = ".json") -> str:
    """Reduce *raw* to a single safe filename ending in *suffix*, or *fallback*.

    Any directory part is stripped, so ``../../x`` cannot leave the folder.
    """
    if not isinstance(raw, str):
        return fallback
    name = os.path.basename(raw.strip().replace("\\", "/"))
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "", name).strip()
    if not name or name in (".", ".."):
        return fallback
    if name.lower().endswith(suffix.lower()):
        name = name[: -len(suffix)]
    name = name[:115].rstrip() or fallback
    return name + suffix


def write_private(path: str, text: str) -> None:
    """Write *text* to *path* atomically, readable by the owner only.

    mkstemp creates the file 0600, which the replace keeps: with the
    passwords in it, the file is as sensitive as the config itself.
    """
    folder = os.path.dirname(path) or "."
    fd, tmp_name = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class SettingsRoutes:
    """Mixed into ``cmdly.server.Handler``; uses its ``app``, ``_send_json`` and ``_error``."""

    @route("GET", "/api/settings/export/target")
    def _api_settings_export_target(self) -> None:
        """Where a settings export would be written, and a filename. Always 200."""
        self._send_json({"dir": settings_export_dir(), "filename": default_settings_filename()})

    @route("POST", "/api/settings/export")
    def _api_settings_export(self, payload: dict) -> None:
        """Write the chosen settings to one file and return its path.

        Written here rather than as a browser download: the desktop window
        (QtWebEngine) drops downloads. It is also what lets the file carry the
        passwords when ``include_secrets`` asks for them: they go from the
        config straight to disk and never through an HTTP response.
        ``sections`` picks the parts (every one when absent); ``browser`` is
        what the page keeps in localStorage, carried through untouched.
        """
        include_secrets = payload.get("include_secrets", False)
        if not isinstance(include_secrets, bool):
            self._error("include_secrets must be true or false")
            return
        browser = payload.get("browser", {})
        if not isinstance(browser, dict):
            self._error("browser must be an object")
            return
        try:
            sections = settings_bundle.normalize_sections(payload.get("sections"))
        except ValueError as exc:
            self._error(str(exc))
            return
        if not sections:
            self._error("Choose at least one part to export.")
            return
        raw_dir = payload.get("dir")
        target_dir = raw_dir if isinstance(raw_dir, str) and raw_dir.strip() else settings_export_dir()
        target_dir = os.path.expanduser(target_dir.strip())
        filename = safe_filename(payload.get("filename"), default_settings_filename())

        bundle = settings_bundle.build(self.app.config.snapshot(), sections=sections,
                                       browser=browser, include_secrets=include_secrets)
        path = os.path.join(target_dir, filename)
        try:
            os.makedirs(target_dir, exist_ok=True)
            write_private(path, json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
        except OSError as exc:
            self._error(f"Could not write to {target_dir}: {exc.strerror or exc}")
            return
        logger.info("exported settings (%s) to %s (passwords %s)", ", ".join(bundle["sections"]),
                    path, "included" if include_secrets else "left out")
        self._send_json({"ok": True, "path": path, "dir": target_dir, "filename": filename,
                         "secrets": include_secrets, "sections": bundle["sections"]})

    @route("POST", "/api/settings/import")
    def _api_settings_import(self, payload: dict) -> None:
        """Apply a settings file written by ``POST /api/settings/export``.

        ``bundle`` is the parsed file and ``sections`` the section ids to take
        from it (every one the file carries when absent); a section the file
        does not carry is never taken from it. Everything is checked before
        anything is written. The browser block is the page's to apply.
        """
        try:
            bundle = settings_bundle.parse(payload.get("bundle"))
            sections = settings_bundle.normalize_sections(payload.get("sections"))
        except ValueError as exc:
            self._error(str(exc))
            return
        sections &= set(bundle["sections"])
        if not sections:
            self._error("Choose at least one part to import.")
            return

        cfg = self.app.config
        warnings: list[str] = []
        with cfg._lock:
            merged = settings_bundle.merge(cfg.snapshot(), bundle["config"], sections,
                                           secrets=bundle["secrets"])
            cfg._data = merged
            try:
                cfg._write(merged)
            except OSError as exc:
                logger.error("settings import: config not saved: %s", exc)
                warnings.append("Applied for this session but not saved.")
        missing = settings_bundle.missing_connections(merged)
        if missing:
            warnings.append("No saved SSH connection named " + ", ".join(f'"{n}"' for n in missing)
                            + ". Cmdly asks for it on the first press.")
        logger.info("imported settings (%s) from a file written by %s",
                    ", ".join(sorted(sections)), bundle["version"] or "an unknown version")
        self._send_json({
            "ok": True,
            "config": cfg.public(),
            "sections": [s for s in settings_bundle.SECTIONS if s in sections],
            "counts": {
                "buttons": len(merged["buttons"]),
                "companions": len(merged["companions"]),
                "connections": len(merged["connections"]),
            },
            "missing_connections": missing,
            "warnings": warnings,
        })
