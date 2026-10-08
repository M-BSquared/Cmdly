"""Cmdly's backend: the web UI, the terminals and the settings, over HTTP.

A ``ThreadingHTTPServer`` on the loopback interface serves ``src/`` (the
interface) and a small JSON API to it:

* ``/api/config``          the settings (no password ever leaves here)
* ``/api/ssh/connections`` the saved SSH connections
* ``/api/ssh/*``           terminal sessions: connect, type, resize, stream,
                           disconnect; a one-shot background run
* ``/api/local/*``         the same for this computer, plus one ICMP ping
* ``/api/update*``         is there a newer release, dismiss it, open its page

A terminal's output reaches the page over one WebSocket per terminal
(``/api/ssh/ws``), with an SSE stream and POSTs as the fallback for a client
without one (see :mod:`cmdly.websocket` for why that matters).

Who may ask: the server listens on 127.0.0.1 only, answers only requests that
name it as ``localhost``/``127.0.0.1`` in their Host header (a DNS-rebinding
page names its own domain), and refuses a state-changing request that a page
on another origin sent. What is left is a process on this computer running as
the same person, who could start these programs anyway.

stdlib only, apart from paramiko inside :mod:`cmdly.ssh_bridge`.
"""
from __future__ import annotations

import importlib.metadata
import json
import math
import logging
import mimetypes
import os
import platform
import queue
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from . import launcher, local_shell, net_probe, websocket
from .config import Config, ConfigError
from .routes.settings import SettingsRoutes
from .routing import _ROUTES, route
from .ssh_bridge import SshBridge, run_command
from .update_check import UpdateChecker, open_url
from .version import get_version

logger = logging.getLogger("cmdly.server")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(REPO_ROOT, "src")
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")

DEFAULT_PORT = 8765
PORT_SPAN = 20
MAX_BODY = 2 * 1024 * 1024
# Output chunks a slow terminal may fall behind by before the oldest go.
STREAM_CAPACITY = 2048

CLIENT_GONE = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/svg+xml", ".svg")

class _Stream:
    """A bounded FIFO between a session's reader thread and one client."""

    def __init__(self) -> None:
        self._q: queue.Queue[str] = queue.Queue(STREAM_CAPACITY)

    def put(self, text: str) -> None:
        while True:
            try:
                self._q.put_nowait(text)
                return
            except queue.Full:
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    pass

    def get(self, timeout: float) -> str:
        return self._q.get(timeout=timeout)

    def drain(self) -> list[str]:
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                return out


def _libraries() -> list[dict[str, str]]:
    """The third-party code Cmdly runs on, for the About page."""
    def version(dist: str) -> str:
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            return ""

    return [
        {"name": "Python", "version": platform.python_version(), "license": "PSF-2.0",
         "role": "The interpreter everything runs in"},
        {"name": "PySide6 (Qt for Python)", "version": version("PySide6") or version("PySide6-Essentials"),
         "license": "LGPL-3.0", "role": "The window, and QtWebEngine that draws this page"},
        {"name": "Paramiko", "version": version("paramiko"), "license": "LGPL-2.1",
         "role": "SSH connections, terminals and background runs"},
        {"name": "xterm.js", "version": "5", "license": "MIT", "role": "The terminal emulator"},
        {"name": "Lucide", "version": "", "license": "ISC", "role": "Icons"},
        {"name": "Inter, JetBrains Mono", "version": "", "license": "OFL-1.1",
         "role": "Type on Linux, and the terminal's monospace face"},
    ]


class Handler(SettingsRoutes, BaseHTTPRequestHandler):
    """One request. The shared services hang off ``self.server``."""

    server_version = "Cmdly"
    protocol_version = "HTTP/1.0"

    # ---- plumbing ----------------------------------------------------------

    @property
    def app(self) -> CmdlyServer:
        return self.server  # type: ignore[return-value]

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401 - quiet by default
        logger.debug("%s - %s", self.address_string(), fmt % args)

    def _port(self) -> int:
        return int(self.server.server_address[1])

    def _host_allowed(self) -> bool:
        """Only requests addressed to this server by its loopback name."""
        host = (self.headers.get("Host") or "").strip().lower()
        allowed = {f"localhost:{self._port()}", f"127.0.0.1:{self._port()}"}
        return host in allowed

    def _origin_allowed(self) -> bool:
        """A state-changing request from a page must be from one of ours."""
        origin = self.headers.get("Origin")
        if origin in (None, "", "null"):
            # No Origin: not sent by a page on another site (browsers attach
            # one to every cross-origin POST and WebSocket).
            return origin != "null"
        origin = origin.strip().lower()
        return origin in (f"http://localhost:{self._port()}", f"http://127.0.0.1:{self._port()}")

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except CLIENT_GONE:
            pass

    def _error(self, message: str, status: int = 400, **extra: Any) -> None:
        self._send_json({"ok": False, "error": message, **extra}, status)

    def _read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self._error("request body too large", 413)
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            self._error("request body is not JSON")
            return None
        if not isinstance(data, dict):
            self._error("request body must be a JSON object")
            return None
        return data

    def _query(self) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items() if v}

    def _local_only(self) -> bool:
        """Programs on this computer only for a client on this computer."""
        host = str(self.client_address[0]) if self.client_address else ""
        if host in ("127.0.0.1", "::1", "::ffff:127.0.0.1") or host.startswith("127."):
            return True
        self._error("Programs on this computer can only be started from this computer.", 403)
        return False

    # ---- dispatch ------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - http.server's name
        if not self._host_allowed():
            self._error("wrong host", 403)
            return
        path = urlsplit(self.path).path
        name = _ROUTES["GET"].get(path)
        if name:
            self._call(name)
            return
        self._static(path)

    def do_POST(self) -> None:  # noqa: N802 - http.server's name
        if not self._host_allowed() or not self._origin_allowed():
            self._error("refused: not from Cmdly", 403)
            return
        name = _ROUTES["POST"].get(urlsplit(self.path).path)
        if not name:
            self._error("not found", 404)
            return
        payload = self._read_json()
        if payload is None:
            return
        self._call(name, payload)

    def _call(self, name: str, *args: Any) -> None:
        try:
            getattr(self, name)(*args)
        except CLIENT_GONE:
            pass
        except Exception:  # noqa: BLE001 - one bad request must never take the server down
            logger.exception("%s %s failed", self.command, self.path)
            self._error("internal error", 500)

    # ---- static files ----------------------------------------------------------

    def _static(self, path: str) -> None:
        rel = unquote(path).lstrip("/") or "index.html"
        if rel.startswith("assets/"):
            root, rel = ASSETS_DIR, rel[len("assets/"):]
        else:
            root = WEB_DIR
        full = os.path.realpath(os.path.join(root, rel))
        if not (full == root or full.startswith(os.path.realpath(root) + os.sep)) or not os.path.isfile(full):
            self._error("not found", 404)
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        try:
            with open(full, "rb") as fh:
                body = fh.read()
        except OSError:
            self._error("not found", 404)
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            # Fonts and vendored libraries never change within a version; the
            # app's own files are revalidated so an update shows at once.
            vendor = "/vendor/" in full or rel.endswith(".woff2")
            self.send_header("Cache-Control", "max-age=86400" if vendor else "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
        except CLIENT_GONE:
            pass

    # ---- app ----------------------------------------------------------------

    @route("GET", "/api/version")
    def _api_version(self) -> None:
        self._send_json({"version": get_version()})

    @route("GET", "/api/about")
    def _api_about(self) -> None:
        self._send_json({
            "version": get_version(),
            "platform": sys.platform,
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "config": self.app.config.path,
            "libraries": _libraries(),
        })

    @route("GET", "/api/config")
    def _api_config(self) -> None:
        self._send_json({"config": self.app.config.public(), "platform": sys.platform,
                         "version": get_version(), "local": local_shell.capabilities()})

    @route("POST", "/api/config")
    def _api_config_update(self, payload: dict) -> None:
        try:
            config = self.app.config.update(payload)
        except ConfigError as exc:
            self._error(str(exc))
            return
        self._send_json({"ok": True, "config": config})

    # ---- updates ------------------------------------------------------------

    @route("GET", "/api/update")
    def _api_update(self) -> None:
        """Whether a newer Cmdly release exists on GitHub.

        Answered from the on-disk cache unless it has gone stale or
        ``?refresh=1`` is set, so a launch costs no network and no wait. A
        failed check returns 200 with the last known release and a non-empty
        ``error``: the page asks in the background, and an unreachable GitHub
        must be silent, not an alert.

        ``configured`` is false while no repository is set; nothing is then
        asked and nothing is reported, error included. ``enabled`` is false
        when the check was turned off in Settings; the network is then never
        touched and ``update_available`` is always false. ``skipped`` echoes
        the dismissed release so the page does not raise the dialog for it again.
        """
        updates_cfg = self.app.config.updates
        enabled = updates_cfg["check"]
        skipped = updates_cfg["skipped"]
        refresh = self._query().get("refresh", "0").lower() in ("1", "true", "yes")
        try:
            if enabled:
                data = self.app.updates.check(force=refresh)
            else:
                # Off means off: report what is already on disk, reach for
                # nothing. update_available stays false so no dialog can fire.
                data = self.app.updates.cached_status()
                data["update_available"] = False
        except Exception:  # noqa: BLE001 - an update check must never 500
            logger.exception("update check failed")
            data = {
                "configured": False, "current": get_version(), "latest": "",
                "update_available": False, "name": "", "url": "", "published": "",
                "notes": "", "assets": [], "checked_at": 0, "error": "update check failed",
            }
        data["enabled"] = enabled
        data["skipped"] = skipped
        self._send_json(data)

    @route("POST", "/api/update/skip")
    def _api_update_skip(self, payload: dict) -> None:
        """Remember a dismissed release, so it stops prompting.

        An empty/absent ``version`` clears the dismissal. Anything that is not
        a version clears it too, rather than silencing every later release.
        """
        raw = payload.get("version")
        version = raw.strip() if isinstance(raw, str) else ""
        try:
            public = self.app.config.update({"updates": {"skipped": version}})
        except ConfigError as exc:
            self._error(str(exc))
            return
        self._send_json({"ok": True, "skipped": public["updates"]["skipped"], "config": public})

    @route("POST", "/api/update/open")
    def _api_update_open(self, payload: dict) -> None:
        """Open the latest release's page in the system browser.

        The URL is re-derived from the cached check result and never read from
        the request. It has to be a server-side action at all because the
        desktop build shows the page inside QtWebEngine, where an external
        link goes nowhere; taking the URL from the caller would turn that
        convenience into an open redirect out of the app.
        """
        try:
            url = self.app.updates.cached_status().get("url") or ""
        except Exception:  # noqa: BLE001 - never 500 on a convenience action
            logger.exception("update page lookup failed")
            url = ""
        # Belt and braces over update_check's own derivation: whatever reaches
        # open_url is handed to the platform's URL opener, which launches
        # programs for far more schemes than http.
        if not url or urlsplit(url).scheme not in ("http", "https"):
            self._error("no release page known", 404)
            return
        if not open_url(url):
            self._send_json({"ok": False, "error": "no browser available", "url": url})
            return
        self._send_json({"ok": True, "url": url})

    # ---- saved SSH connections ---------------------------------------------

    def _connections(self) -> list[dict[str, Any]]:
        live = {s["name"] for s in self.app.ssh.list_sessions() if s["connected"]}
        out = []
        for c in self.app.config.public()["connections"]:
            c["connected"] = c["name"] in live
            out.append(c)
        return out

    @route("GET", "/api/ssh/connections")
    def _api_ssh_connections(self) -> None:
        self._send_json({"connections": self._connections()})

    @route("POST", "/api/ssh/connections")
    def _api_ssh_connections_upsert(self, payload: dict) -> None:
        try:
            saved = self.app.config.upsert_connection(payload)
        except ConfigError as exc:
            self._error(str(exc))
            return
        self._send_json({"ok": True, "connection": saved, "connections": self._connections(),
                         "config": self.app.config.public()})

    @route("POST", "/api/ssh/connections/remove")
    def _api_ssh_connections_remove(self, payload: dict) -> None:
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            self._error("name must be a non-empty string")
            return
        self.app.config.remove_connection(name)
        self._send_json({"ok": True, "connections": self._connections(),
                         "config": self.app.config.public()})

    @route("POST", "/api/ssh/connections/test")
    def _api_ssh_connections_test(self, payload: dict) -> None:
        """Log in once and run ``true``: does this connection work?

        Tests the saved one named ``name``, or the fields given (a form not
        saved yet). A form that leaves the password out of an existing entry
        is tested with the stored one.
        """
        name = payload.get("name") if isinstance(payload.get("name"), str) else ""
        saved = self.app.config.connection(payload.get("original_name") or name) if name else None
        fields = dict(saved or {})
        for key in ("host", "port", "username", "key_path", "password"):
            if key in payload and payload[key] is not None:
                fields[key] = payload[key]
        conn = launcher.coerce_connection(fields)
        if conn is None:
            self._error("Name the host to connect to.")
            return
        if not conn["username"]:
            self._send_json({"ok": False, "error": "Enter the user to log in as."})
            return
        result = run_command(host=conn["host"], command="true", port=conn["port"],
                             username=conn["username"], password=conn["password"] or None,
                             key_path=conn["key_path"] or None, timeout=8)
        self._send_json({"ok": bool(result.get("ok")), "error": result.get("error", ""),
                         "auth_failed": bool(result.get("auth_failed"))})

    # ---- terminal sessions ---------------------------------------------------

    @route("GET", "/api/ssh/sessions")
    def _api_ssh_sessions(self) -> None:
        self._send_json({"sessions": self.app.ssh.list_sessions()})

    @route("POST", "/api/ssh/connect")
    def _api_ssh_connect(self, payload: dict) -> None:
        """Open a named shell over the saved connection ``from``.

        ``name`` is the session (one per button); ``from`` the saved
        connection whose credentials it uses, which the page never holds. A
        reply that cannot connect for want of the connection or its login says
        so in ``needs``, so the page can ask for exactly that.
        """
        name = payload.get("name")
        borrow = payload.get("from")
        if not isinstance(name, str) or not name or len(name) > 128:
            self._error("name must be a non-empty string")
            return
        if not isinstance(borrow, str) or not borrow:
            self._error("from must name a saved connection")
            return
        conn = self.app.config.connection(borrow)
        if conn is None:
            self._error(f"There is no saved connection named “{borrow}”.", 400,
                        needs="connection", connection=borrow)
            return
        if not conn["username"]:
            self._error("Enter the user to log in as.", 400, needs="credentials", connection=borrow)
            return
        ok = self.app.ssh.connect(name, conn["host"], conn["port"], conn["username"],
                                  conn["password"] or None, conn["key_path"] or None)
        reply: dict[str, Any] = {"ok": ok, "connected": ok, "name": name, "host": conn["host"],
                                 "port": conn["port"], "username": conn["username"]}
        if not ok:
            reply["error"] = self.app.ssh.connect_error(name) or "Connection failed."
            if self.app.ssh.connect_auth_failed(name):
                reply.update(needs="credentials", connection=borrow)
        self._send_json(reply)

    @route("POST", "/api/ssh/send")
    def _api_ssh_send(self, payload: dict) -> None:
        name, data = payload.get("name"), payload.get("data")
        if not isinstance(name, str) or not name or not isinstance(data, str):
            self._error("name and data must be strings")
            return
        self._send_json({"ok": self.app.ssh.send(name, data)})

    @route("POST", "/api/ssh/resize")
    def _api_ssh_resize(self, payload: dict) -> None:
        name = payload.get("name")
        cols, rows = payload.get("cols"), payload.get("rows")
        if not isinstance(name, str) or not name:
            self._error("name must be a non-empty string")
            return
        if not all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 1000 for v in (cols, rows)):
            self._error("cols and rows must be integers from 1 to 1000")
            return
        self._send_json({"ok": self.app.ssh.resize(name, cols, rows)})

    @route("POST", "/api/ssh/disconnect")
    def _api_ssh_disconnect(self, payload: dict) -> None:
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            self._error("name must be a non-empty string")
            return
        self._send_json({"ok": self.app.ssh.disconnect(name)})

    @route("POST", "/api/ssh/run")
    def _api_ssh_run(self, payload: dict) -> None:
        """One command over its own short-lived connection; ``detach`` runs it
        under nohup so it outlives the connection."""
        name, command = payload.get("name"), payload.get("command")
        directory, detach = payload.get("directory", ""), payload.get("detach", False)
        if not isinstance(command, str) or not command.strip():
            self._error("command must be a non-empty string")
            return
        if not isinstance(directory, str) or not isinstance(detach, bool) or not isinstance(name, str):
            self._error("name and directory must be strings, detach a boolean")
            return
        conn = self.app.config.connection(name)
        if conn is None:
            self._error(f"There is no saved connection named “{name}”.", 400,
                        needs="connection", connection=name)
            return
        if not conn["username"]:
            self._error("Enter the user to log in as.", 400, needs="credentials", connection=name)
            return
        line = launcher.remote_command(directory, command, detach)
        result = run_command(host=conn["host"], command=line, port=conn["port"],
                             username=conn["username"], password=conn["password"] or None,
                             key_path=conn["key_path"] or None)
        result["command"] = line
        if result.pop("auth_failed", False):
            result.update(needs="credentials", connection=name)
        self._send_json(result)

    @route("POST", "/api/ssh/power")
    def _api_ssh_power(self, payload: dict) -> None:
        """Shut the connection's computer down or reboot it: one command over
        its own short-lived connection (the companion card's right-click
        menu). The line comes from the backend, never the page."""
        name, action = payload.get("name"), payload.get("action")
        if action not in launcher.POWER_ACTIONS:
            self._error("action must be one of: " + ", ".join(sorted(launcher.POWER_ACTIONS)))
            return
        if not isinstance(name, str) or not name:
            self._error("name must be a non-empty string")
            return
        conn = self.app.config.connection(name)
        if conn is None:
            self._error(f"There is no saved connection named “{name}”.", 400,
                        needs="connection", connection=name)
            return
        if not conn["username"]:
            self._error("Enter the user to log in as.", 400, needs="credentials", connection=name)
            return
        result = run_command(host=conn["host"], command=launcher.POWER_ACTIONS[action],
                             port=conn["port"], username=conn["username"],
                             password=conn["password"] or None, key_path=conn["key_path"] or None)
        if result.pop("auth_failed", False):
            result.update(needs="credentials", connection=name)
        self._send_json(result)

    @route("GET", "/api/ssh/stream")
    def _sse_ssh_stream(self) -> None:
        """One session's output as Server-Sent Events (the WebSocket's fallback)."""
        name = self._query().get("name", "")
        session = self.app.ssh.get_session(name) if name else None
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def event(kind: str, data: Any) -> None:
            self.wfile.write(f"event: {kind}\ndata: {json.dumps(data)}\n\n".encode())
            self.wfile.flush()

        if session is None or not session.connected:
            try:
                event("closed", {"name": name or None})
            except CLIENT_GONE:
                pass
            return
        stream = _Stream()
        session.add_sub(stream.put)
        idle = 0.0
        try:
            while not self.app.stopping.is_set():
                try:
                    event("output", {"text": stream.get(1.0)})
                    idle = 0.0
                    continue
                except queue.Empty:
                    pass
                live = self.app.ssh.get_session(name)
                if live is None or not live.connected:
                    for text in stream.drain():
                        event("output", {"text": text})
                    event("closed", {"name": name})
                    break
                idle += 1.0
                if idle >= 15.0:
                    idle = 0.0
                    event("ping", {})
        except CLIENT_GONE:
            pass
        finally:
            session.remove_sub(stream.put)

    @route("GET", "/api/ssh/ws")
    def _ws_ssh(self) -> None:
        """One terminal over a WebSocket: output out, keystrokes and size in.

        ``{"type": "output", "text"}`` and ``{"type": "closed"}`` to the page,
        ``{"type": "input", "data"}`` and ``{"type": "resize", "cols", "rows"}``
        from it. Input writes to a shell, so the upgrade is held to what a POST
        is held to.
        """
        if not self._origin_allowed():
            self._error("refused: not from Cmdly", 403)
            return
        problem = websocket.handshake_problem(self.headers)
        if problem:
            self._error(problem)
            return
        name = self._query().get("name", "")
        self.close_connection = True
        self.wfile.write(websocket.handshake_response(self.headers.get("Sec-WebSocket-Key", "")))
        self.wfile.flush()
        ws = websocket.WebSocket(self.connection)
        session = self.app.ssh.get_session(name) if name else None
        if session is None or not session.connected:
            try:
                ws.send_text(json.dumps({"type": "closed", "name": name or None}))
            except websocket.Closed:
                pass
            ws.close()
            return
        stream = _Stream()
        done = threading.Event()
        session.add_sub(stream.put)
        writer = threading.Thread(target=self._ws_writer, args=(ws, stream, name, done),
                                  name=f"ws-{name}", daemon=True)
        writer.start()
        try:
            while not done.is_set() and not self.app.stopping.is_set():
                try:
                    text = ws.receive(1.0)
                except websocket.Closed:
                    break
                if text is not None:
                    self._ws_input(name, text)
        finally:
            done.set()
            session.remove_sub(stream.put)
            writer.join(2.0)
            ws.close(websocket.CLOSE_GOING_AWAY if self.app.stopping.is_set() else websocket.CLOSE_NORMAL)

    def _ws_writer(self, ws: websocket.WebSocket, stream: _Stream, name: str,
                   done: threading.Event) -> None:
        idle = 0.0
        try:
            while not done.is_set():
                try:
                    ws.send_text(json.dumps({"type": "output", "text": stream.get(1.0)}))
                    idle = 0.0
                    continue
                except queue.Empty:
                    pass
                if self.app.stopping.is_set():
                    break
                live = self.app.ssh.get_session(name)
                if live is None or not live.connected:
                    # What the shell printed on its way out comes before the end.
                    for text in stream.drain():
                        ws.send_text(json.dumps({"type": "output", "text": text}))
                    ws.send_text(json.dumps({"type": "closed", "name": name}))
                    break
                idle += 1.0
                if idle >= 15.0:
                    idle = 0.0
                    ws.ping()
        except websocket.Closed:
            pass
        finally:
            done.set()

    def _ws_input(self, name: str, text: str) -> None:
        try:
            msg = json.loads(text)
        except ValueError:
            return
        if not isinstance(msg, dict):
            return
        if msg.get("type") == "input" and isinstance(msg.get("data"), str):
            self.app.ssh.send(name, msg["data"])
        elif msg.get("type") == "resize":
            cols, rows = msg.get("cols"), msg.get("rows")
            if all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 1000 for v in (cols, rows)):
                self.app.ssh.resize(name, cols, rows)

    # ---- this computer ---------------------------------------------------------

    @route("GET", "/api/local/status")
    def _api_local_status(self) -> None:
        caps = local_shell.capabilities()
        caps["running"] = self.app.local.count()
        caps["ping"] = self.app.pinger.available
        self._send_json(caps)

    @route("POST", "/api/local/connect")
    def _api_local_connect(self, payload: dict) -> None:
        """A login shell on this computer, as the session ``name``."""
        if not self._local_only():
            return
        name, directory = payload.get("name"), payload.get("directory", "")
        if not isinstance(name, str) or not name.strip() or len(name) > 128:
            self._error("name must be a non-empty string")
            return
        connected = self.app.ssh.connect_local(name, directory if isinstance(directory, str) else "")
        answer: dict[str, Any] = {"ok": connected, "connected": connected, "name": name}
        if not connected:
            answer["error"] = self.app.ssh.connect_error(name) or "The shell could not be started."
        self._send_json(answer)

    @route("POST", "/api/local/run")
    def _api_local_run(self, payload: dict) -> None:
        if not self._local_only():
            return
        command, directory = payload.get("command"), payload.get("directory", "")
        if not isinstance(command, str) or not isinstance(directory, str):
            self._error("command and directory must be strings")
            return
        result = self.app.local.run(command, directory)
        result["command"] = command
        self._send_json(result)

    @route("POST", "/api/local/ping")
    def _api_local_ping(self, payload: dict) -> None:
        if not self._local_only():
            return
        host, wait_ms = payload.get("host"), payload.get("wait_ms", 2000)
        if not isinstance(host, str) or isinstance(wait_ms, bool) \
                or not isinstance(wait_ms, (int, float)) or not math.isfinite(wait_ms):
            self._error("host must be a string and wait_ms a number")
            return
        _, problem = net_probe.clean_host(host)
        if problem:
            self._error(problem)
            return
        if getattr(self.app, "pinger", None) is None:
            self._error("Pinging is unavailable.", 503)
            return
        self._send_json(self.app.pinger.ping(host, float(wait_ms) / 1000.0))


class CmdlyServer(ThreadingHTTPServer):
    """The HTTP server and the services its handlers share."""

    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address: tuple[str, int], config: Config) -> None:
        super().__init__(address, Handler)
        self.config = config
        self.ssh = SshBridge()
        self.local = local_shell.LocalRunner()
        self.pinger = net_probe.Pinger()
        # Constructed only: it touches the network the first time the page
        # asks, never at startup, and not at all while no repository is set.
        self.updates = UpdateChecker()
        self.stopping = threading.Event()

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    def stop(self) -> None:
        """Every session closed, every program and probe ended. Never raises."""
        self.stopping.set()
        for name, step in (("http", self.shutdown), ("ssh", self.ssh.shutdown),
                           ("local", self.local.shutdown), ("ping", self.pinger.shutdown),
                           ("socket", self.server_close)):
            try:
                step()
            except Exception:  # noqa: BLE001 - teardown goes on whatever one step does
                logger.exception("stopping %s failed", name)


def create_server(port: int = DEFAULT_PORT, config: Config | None = None) -> CmdlyServer:
    """Bind the first free port from *port* on, on loopback only."""
    cfg = config or Config()
    last: OSError | None = None
    for candidate in range(port, port + PORT_SPAN):
        try:
            return CmdlyServer(("127.0.0.1", candidate), cfg)
        except OSError as exc:
            last = exc
    raise OSError(f"no free port from {port} to {port + PORT_SPAN - 1}: {last}")


def serve_in_thread(server: CmdlyServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.25},
                              name="cmdly-http", daemon=True)
    thread.start()
    return thread


def free_port_hint() -> int:
    """A port the OS says is free right now (tests)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
