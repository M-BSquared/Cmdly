"""Cmdly's MCP server: what an AI agent may do with Cmdly, over stdio.

An agent app (Claude Desktop, Claude Code, any MCP client) starts this as a
command — ``python -m cmdly mcp``, or ``Cmdly.AppImage mcp`` — and speaks
JSON-RPC over its stdin and stdout: ``initialize``, ``tools/list``,
``tools/call``. Every tool is one request to the backend's HTTP API, the same
one the page sends (:mod:`cmdly.server`), so this adds no second way into
Cmdly to keep in step. Cmdly itself has to be running; its port is read from
the instance lock's record, or asked for on the ports it could be on.

What an agent may do is the person's decision, in the Settings: buttons
always (adding a button changes no computer; pressing it does), and with
Settings → Agent → "Control terminals and power" also the rest — press a
button, open terminals here and over SSH, type into them, read them, run
commands in the background, ping a computer, and shut down or reboot this
computer and its companions. The gated tools read that switch before they
act, and no tool can turn it on: an agent cannot grant itself the
permission. The gate is a capability gate, not a security boundary — the
backend answers any process of this same person — what it buys is the
person's explicit yes first.

A terminal an agent opens runs in a session named ``agent/<name>`` and the
page shows it as a terminal window like any other (``js/store.js`` keeps the
prefix in step), so nothing an agent types happens off screen.

The protocol is MCP's stdio transport: JSON-RPC 2.0, one message per line.
Implemented here rather than through the MCP SDK because the part a tool
server needs — initialize, ping, tools/list, tools/call — is small, and the
backend carries no SDK dependencies (stdlib only, like the rest of it).
Logs go to stderr; stdout carries protocol messages only.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import uuid
from http.client import HTTPConnection
from typing import Any
from urllib.parse import urlencode

from . import launcher
from .instance_lock import InstanceLock
from .server import DEFAULT_PORT, PORT_SPAN
from .version import get_version

logger = logging.getLogger("cmdly.mcp")

#: The MCP protocol version spoken when the client names none, or one this
#: does not know (a newer client degrades gracefully; the transport, JSON-RPC
#: with one message per line, is the same across versions).
PROTOCOL_VERSION = "2025-06-18"

#: A terminal an agent opens runs in a session named ``agent/<name>``, so
#: the page can tell it from its own and show it (js/store.js keeps this in
#: step, as js/launch.js keeps the button prefix).
SESSION_PREFIX = "agent/"
#: The terminal an unnamed command runs in, kept between calls so an agent
#: works in one shell as a person does.
DEFAULT_SESSION = "main"

#: How much of a terminal a tool returns by default (its last bytes).
DEFAULT_TAIL = 16384
#: The backend's replay buffer ceiling; more than this is not there to read.
MAX_TAIL = 256 * 1024
#: How long a tool waits for the shell to finish a command before returning
#: whatever it printed (it returns as soon as the command is done).
DEFAULT_WAIT_S = 10.0
MAX_WAIT_S = 30.0
#: The grace a shell gets to take its prompt back after Ctrl-C before the
#: line is typed again (launch.js gives a press the same moment).
INTERRUPT_GRACE_S = 1.0

INSTRUCTIONS = (
    "Cmdly is a shelf of one-press buttons that start programs on this computer "
    "or on companion computers over SSH, in real terminals. You can add, change, "
    "list and remove buttons at any time. Everything else — pressing a button, "
    "opening terminals, typing into them, running commands, pinging a computer, "
    "reboot or shutdown — needs the person's switch: Settings → Agent → "
    "“Control terminals and power”, in the Cmdly app. A terminal you open is "
    "shown to the person as a window. Start with the status tool to see where "
    "things stand."
)


# ---------------------------------------------------------------------------
# talking to the backend
# ---------------------------------------------------------------------------


class CmdlyError(Exception):
    """A tool cannot do what it was asked; the message goes to the agent."""


class Refused(CmdlyError):
    """The person has not allowed this in the settings."""


class Unreachable(CmdlyError):
    """Cmdly itself is not running."""


class CmdlyClient:
    """The backend's HTTP API, as the tools call it.

    The port is discovered once and remembered; a connection refused after
    that re-discovers once, because Cmdly may have restarted on another port
    in between. No Origin header is sent — a client that is not a page — so
    the backend's own rules let it through.
    """

    def __init__(self, port: int | None = None) -> None:
        self._port = port

    # ---- where the backend is ---------------------------------------------

    def _candidate_ports(self) -> list[int]:
        """The ports the backend could be on, the most likely first."""
        ports: list[int] = []
        recorded = InstanceLock().peer().get("port")
        if isinstance(recorded, int) and not isinstance(recorded, bool) and 1 <= recorded <= 65535:
            ports.append(recorded)
        ports.extend(range(DEFAULT_PORT, DEFAULT_PORT + PORT_SPAN))
        seen: set[int] = set()
        return [p for p in ports if not (p in seen or seen.add(p))]

    def _discover(self) -> int:
        """The port Cmdly's backend answers on, or 0 when none does."""
        for port in self._candidate_ports():
            try:
                self._ask(port, "GET", "/api/version")
                return port
            except (OSError, CmdlyError):
                continue
        return 0

    def port(self) -> int:
        if not self._port:
            self._port = self._discover()
        return self._port

    # ---- one request --------------------------------------------------------

    def _ask(self, port: int, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        conn = HTTPConnection("127.0.0.1", port, timeout=20)
        try:
            payload = json.dumps(body).encode("utf-8") if body is not None else None
            headers = {"Content-Type": "application/json"} if payload else {}
            conn.request(method, path, body=payload, headers=headers)
            res = conn.getresponse()
            raw = res.read()
        finally:
            conn.close()
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except ValueError as exc:
            raise CmdlyError("Cmdly's backend sent a reply that is not JSON.") from exc
        if not isinstance(data, dict):
            raise CmdlyError("Cmdly's backend sent a reply that is not an object.")
        if not 200 <= res.status < 300:
            raise CmdlyError(str(data.get("error") or f"HTTP {res.status}"))
        return data

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """One request, with one rediscovery when the port has gone stale."""
        for _attempt in (1, 2):
            port = self.port()
            if not port:
                break
            try:
                return self._ask(port, method, path, body)
            except OSError:
                # Refused: Cmdly has gone away, or moved to another port.
                self._port = None
        raise Unreachable("Cmdly is not running. Start Cmdly (the app), then try again.")

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, body)

    # ---- what the tools need ------------------------------------------------

    def config(self) -> dict[str, Any]:
        return self.get("/api/config").get("config") or {}

    def sessions(self) -> list[dict[str, Any]]:
        return self.get("/api/ssh/sessions").get("sessions") or []

    def agent_allowed(self) -> bool:
        """Whether the person lets an agent control terminals and power."""
        agent = self.config().get("agent")
        return bool(agent.get("terminal_control")) if isinstance(agent, dict) else False

    def require_permission(self) -> None:
        """Refuse, in words an agent can act on, when the switch is off."""
        if not self.agent_allowed():
            raise Refused(
                "The person has not allowed this. Ask them to turn on "
                "Settings → Agent → “Control terminals and power” in Cmdly."
            )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _clip(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number:  # NaN
        return fallback
    return max(low, min(high, number))


def session_name(name: Any) -> str:
    """A session's full name: the agent's own prefix, added when the name has
    none of its own. A name the page owns (``cmdly/…``, a button's terminal)
    passes through: an agent with the switch may reach the terminals it sees
    in list_terminals, not only its own."""
    text = _text(name).strip() or DEFAULT_SESSION
    if text.startswith(SESSION_PREFIX) or text.startswith(launcher.SESSION_PREFIX):
        return text
    return SESSION_PREFIX + text


def _read_terminal(client: CmdlyClient, name: str, tail: int) -> str:
    query = urlencode({"name": name, "tail": max(1, min(tail, MAX_TAIL))})
    return _text(client.get(f"/api/ssh/output?{query}").get("output"))


def mcp_command(env: dict[str, str] | None = None, executable: str = "") -> dict[str, Any]:
    """The command line an agent app should run to speak to THIS Cmdly's MCP
    server: the AppImage or the .app itself where Cmdly is packaged (both
    carry their Python with them), and this checkout's Python elsewhere —
    its venv when run.sh made one. *env* and *executable* are the seams the
    tests use; ``os.environ`` and ``sys.executable`` are what runs.

    The Settings' Agent page turns this into the config of an agent app
    (OpenCode, Codex): the exact command, for the Cmdly that is running.
    """
    env = os.environ if env is None else env
    sys_exe = executable or sys.executable
    image = env.get("APPIMAGE")
    if image:
        return {"command": [image, "mcp"], "env": {}}
    if sys.platform == "darwin" and ".app/Contents/" in sys_exe:
        app = sys_exe.split(".app/Contents/", 1)[0] + ".app"
        return {"command": [os.path.join(app, "Contents", "MacOS", "cmdly"), "mcp"], "env": {}}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv = os.path.join(root, ".venv", "bin", "python")
    python = venv if os.path.exists(venv) else sys_exe
    return {"command": [python, "-m", "cmdly", "mcp"], "env": {"PYTHONPATH": root}}


def self_test(timeout: float = 30.0) -> dict[str, Any]:
    """Start this Cmdly's MCP server once, exactly as an agent app starts
    it, and shake hands: does it answer ``initialize`` and list its tools?

    The Settings' test button, so nobody opens a terminal to check. Nothing
    is left running — the server ends when its input does.
    """
    spec = mcp_command()
    env = dict(os.environ)
    env.update(spec["env"])
    try:
        proc = subprocess.Popen(spec["command"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, text=True)
    except OSError as exc:
        return {"ok": False, "error": f"could not start it: {exc}", "tools": [], "version": ""}
    script = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    ]) + "\n"
    try:
        out, err = proc.communicate(script, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return {"ok": False, "error": "it did not answer in time", "tools": [], "version": ""}
    tools: list[str] = []
    version = ""
    for line in out.splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        result = msg.get("result") if isinstance(msg, dict) else None
        if not isinstance(result, dict):
            continue
        if msg.get("id") == 1:
            version = _text((result.get("serverInfo") or {}).get("version"))
        elif msg.get("id") == 2:
            tools = sorted(_text(t.get("name")) for t in result.get("tools") or []
                            if isinstance(t, dict))
    if version and tools:
        return {"ok": True, "error": "", "tools": tools, "version": version}
    return {"ok": False, "error": (err or out).strip()[-500:] or "no answer",
            "tools": tools, "version": version}


def _connection_of(config: dict[str, Any], wanted: str) -> str:
    """A saved connection by name, or the error naming what is saved."""
    known = [_text(c.get("name")) for c in config.get("connections") or []]
    if not wanted:
        raise CmdlyError("An SSH button needs `connection`, the saved connection it runs on."
                         + (f" Saved: {', '.join(known)}." if known else " None is saved yet."))
    if wanted not in known:
        raise CmdlyError(f"There is no saved connection named “{wanted}”."
                         + (f" Saved: {', '.join(known)}." if known else ""))
    return wanted


def _find_button(buttons: list[dict[str, Any]], button_id: str, label: str) -> tuple[int, dict[str, Any]]:
    """Where on the shelf a button is, named by its id or its label. Raises
    when there is none, or when a label names several."""
    if not button_id and not label:
        raise CmdlyError("Name the button: its id, or its label.")
    found = [(i, b) for i, b in enumerate(buttons)
             if (button_id and b.get("id") == button_id) or (label and b.get("label") == label)]
    if not found:
        known = ", ".join(f"{b.get('id')} “{b.get('label')}”" for b in buttons) or "the shelf is empty"
        raise CmdlyError(f"No such button. On the shelf: {known}.")
    if len(found) > 1:
        raise CmdlyError("Several buttons are called that; name its id: "
                        + ", ".join(_text(b.get("id")) for _, b in found) + ".")
    return found[0]


def _run_once(client: CmdlyClient, *, command: str, target: str, directory: str,
              detach: bool = False) -> dict[str, Any]:
    """One command, no terminal: on this computer, or over a connection."""
    if target == "local":
        return client.post("/api/local/run", {"command": command, "directory": directory})
    return client.post("/api/ssh/run", {"name": target, "command": command,
                                        "directory": directory, "detach": detach})


def _run_summary(result: dict[str, Any], target: str) -> str:
    """A one-shot's answer in words, its output attached when there is one."""
    if target == "local":
        if result.get("error"):
            raise CmdlyError(_text(result.get("error")))
        if result.get("exited"):
            text = f"Finished (exit code {result.get('code')})."
            if result.get("output"):
                text += "\n" + _text(result.get("output"))
            return text
        return f"Running in the background (pid {result.get('pid')}); it stops when Cmdly quits."
    if result.get("error") and result.get("exit_status") is None:
        raise CmdlyError(_text(result.get("error")))
    pid = _text(result.get("stdout")).strip()
    if pid.isdigit():
        return f"Running detached on {target} (pid {pid})."
    text = f"Ran on {target} (exit status {result.get('exit_status')})."
    for part in (result.get("stdout"), result.get("stderr")):
        if _text(part).strip():
            text += "\n" + _text(part).strip()
    return text


def _ensure_session(client: CmdlyClient, name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """An open session under *name*, or one opened for it.

    Returns where it runs ("this computer", or a connection's name) and
    whether this call opened it. A session that exists stays as it is: a
    re-connect would throw away its shell, and the work in it.
    """
    for row in client.sessions():
        if row.get("name") == name and row.get("connected"):
            host = _text(row.get("host"))
            return (host or "this computer"), False
    target = _text(args.get("target")).strip() or "local"
    if target == "local":
        reply = client.post("/api/local/connect",
                            {"name": name, "directory": _text(args.get("directory"))})
    else:
        reply = client.post("/api/ssh/connect", {"name": name, "from": target})
    if not reply.get("ok"):
        raise CmdlyError(_text(reply.get("error")) or "The terminal could not be opened.")
    return target, True


def _fmt_button(button: dict[str, Any]) -> str:
    """One button, as an agent reads it."""
    target = "this computer" if button.get("target") != "ssh" else f"ssh: {button.get('connection', '')}"
    mode = "terminal" if button.get("mode") != "background" else "background"
    head = f"{button.get('id', '')}  “{button.get('label', '')}” · {target} · {mode}"
    directory = button.get("directory", "")
    where = f" (in {directory})" if directory else ""
    return f"{head}{where}\n  {button.get('command', '')}"


# ---------------------------------------------------------------------------
# the tools
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = []


def tool(name: str, description: str, schema: dict[str, Any], *, gated: bool = False):
    """Register one tool: its JSON Schema and the function that runs it."""
    def register(fn):
        TOOLS.append({"name": name, "description": description,
                      "inputSchema": schema, "gated": gated, "run": fn})
        return fn
    return register


# ---- buttons: always allowed -------------------------------------------------


@tool("status",
      "Cmdly at a glance: the version, whether the person allows terminal and "
      "power control, the buttons, the saved connections, the open terminals "
      "and what this computer can do. Start here.",
      {"type": "object", "properties": {}, "additionalProperties": False})
def _status(client: CmdlyClient, args: dict[str, Any]) -> str:
    config = client.config()
    allowed = client.agent_allowed()
    buttons = config.get("buttons") or []
    connections = [_text(c.get("name")) for c in config.get("connections") or []]
    sessions = client.sessions()
    local = client.get("/api/local/status")
    lines = [
        f"Cmdly {get_version()}.",
        ("The person ALLOWS terminal and power control."
         if allowed else
         "The person does not allow terminal and power control: you can add, list "
         "and remove buttons, nothing else. It is switched on in Cmdly under "
         "Settings → Agent."),
        f"Buttons: {len(buttons)}.",
        f"Saved connections: {', '.join(connections) if connections else 'none'}.",
        "Open terminals: " + (", ".join(
            f"{s.get('name')} ({'connected' if s.get('connected') else 'closed'})"
            for s in sessions) if sessions else "none") + ".",
        _text(local.get("reason")) if not local.get("terminal") else
        "This computer: terminals available, "
        f"{local.get('running', 0)} background program(s) running.",
    ]
    return "\n".join(lines)


@tool("list_buttons",
      "The buttons on Cmdly's shelf: id, label, where each runs, its command.",
      {"type": "object", "properties": {}, "additionalProperties": False})
def _list_buttons(client: CmdlyClient, args: dict[str, Any]) -> str:
    buttons = client.config().get("buttons") or []
    if not buttons:
        return "The shelf has no buttons. add_button puts one on it."
    return "\n".join(_fmt_button(b) for b in buttons)


@tool("add_button",
      "Add a button to Cmdly's shelf. The person presses it (the arrow beside "
      "it opens its terminal); adding it changes no computer, so this needs "
      "no permission. An SSH button names one of the saved connections.",
      {"type": "object",
       "properties": {
           "label": {"type": "string", "description": "The name on the button (defaults to the command)."},
           "command": {"type": "string", "description": "The command line the button runs."},
           "target": {"type": "string", "enum": ["local", "ssh"],
                      "description": "Where it runs: this computer (default) or over SSH."},
           "connection": {"type": "string",
                          "description": "The saved SSH connection it runs on (an SSH button only)."},
           "directory": {"type": "string", "description": "The folder it runs in, if not the home folder."},
           "mode": {"type": "string", "enum": ["terminal", "background"],
                    "description": "In a terminal (the default) or once in the background."},
           "restart": {"type": "boolean",
                       "description": "Terminal mode: a second press sends Ctrl-C first."},
       },
       "required": ["command"], "additionalProperties": False})
def _add_button(client: CmdlyClient, args: dict[str, Any]) -> str:
    command = _text(args.get("command")).strip()
    if not command:
        raise CmdlyError("command is required: the line the button runs.")
    config = client.config()
    buttons = list(config.get("buttons") or [])
    if len(buttons) >= launcher.MAX_BUTTONS:
        raise CmdlyError(f"The shelf is full ({launcher.MAX_BUTTONS} buttons). Remove one first.")
    target = "ssh" if args.get("target") == "ssh" else "local"
    connection = ""
    if target == "ssh":
        connection = _connection_of(config, _text(args.get("connection")).strip())
    button = launcher.coerce_button({
        "label": args.get("label"), "command": command, "target": target,
        "connection": connection, "directory": _text(args.get("directory")),
        "mode": "background" if args.get("mode") == "background" else "terminal",
        "restart": args.get("restart") is True,
    })
    if button is None:
        raise CmdlyError("That did not make a button: a command is required.")
    reply = client.post("/api/config", {"buttons": buttons + [button]})
    saved = next((b for b in reply.get("config", {}).get("buttons", [])
                  if b.get("id") == button.get("id")), button)
    where = "this computer" if target == "local" else f"ssh on “{connection}”"
    how = "in a terminal" if saved.get("mode") != "background" else "in the background"
    return (f"Added the button “{saved.get('label')}” ({saved.get('id')}): {how} on {where}, "
            f"running “{saved.get('command')}”. It is on the shelf; the person presses it.")


@tool("remove_button",
      "Remove a button from the shelf, by its id or its label.",
      {"type": "object",
       "properties": {
           "id": {"type": "string", "description": "The button's id."},
           "label": {"type": "string", "description": "The button's label."},
       },
       "additionalProperties": False})
def _remove_button(client: CmdlyClient, args: dict[str, Any]) -> str:
    button_id = _text(args.get("id")).strip()
    label = _text(args.get("label")).strip()
    if not button_id and not label:
        raise CmdlyError("Name the button: its id, or its label.")
    buttons = list(client.config().get("buttons") or [])
    found = [b for b in buttons
             if (button_id and b.get("id") == button_id) or (label and b.get("label") == label)]
    if not found:
        known = ", ".join(f"{b.get('id')} “{b.get('label')}”" for b in buttons) or "the shelf is empty"
        raise CmdlyError(f"No such button. On the shelf: {known}.")
    if len(found) > 1:
        raise CmdlyError("Several buttons are called that; name its id: "
                        + ", ".join(_text(b.get("id")) for b in found) + ".")
    gone = found[0]
    client.post("/api/config", {"buttons": [b for b in buttons if b is not gone]})
    return f"Removed the button “{gone.get('label')}” ({gone.get('id')})."


@tool("update_button",
      "Change a button on the shelf: only the fields given, the rest stay as "
      "they are. Adding a button changes no computer, so neither does changing "
      "one; pressing it is the person's act (or the agent's, with the switch).",
      {"type": "object",
       "properties": {
           "id": {"type": "string", "description": "The button's id (as list_buttons shows)."},
           "label": {"type": "string", "description": "A new label."},
           "command": {"type": "string", "description": "A new command line."},
           "target": {"type": "string", "enum": ["local", "ssh"],
                      "description": "Where it runs: this computer, or over SSH."},
           "connection": {"type": "string",
                          "description": "The saved SSH connection it runs on (an SSH button only)."},
           "directory": {"type": "string", "description": "The folder it runs in."},
           "mode": {"type": "string", "enum": ["terminal", "background"],
                    "description": "In a terminal, or once in the background."},
           "restart": {"type": "boolean",
                       "description": "Terminal mode: a second press sends Ctrl-C first."},
       },
       "required": ["id"], "additionalProperties": False})
def _update_button(client: CmdlyClient, args: dict[str, Any]) -> str:
    button_id = _text(args.get("id")).strip()
    config = client.config()
    buttons = list(config.get("buttons") or [])
    index, button = _find_button(buttons, button_id, "")
    merged = dict(button)
    for key in ("label", "command", "directory", "connection"):
        if key in args:
            merged[key] = _text(args.get(key))
    if "target" in args:
        merged["target"] = "ssh" if args.get("target") == "ssh" else "local"
    if "mode" in args:
        merged["mode"] = "background" if args.get("mode") == "background" else "terminal"
    if "restart" in args:
        merged["restart"] = args.get("restart") is True
    if merged.get("target") == "ssh":
        merged["connection"] = _connection_of(config, _text(merged.get("connection")).strip())
    else:
        merged["connection"] = ""
    changed = [key for key in ("label", "command", "target", "connection", "directory", "mode", "restart")
               if merged.get(key) != button.get(key)]
    new = launcher.coerce_button(dict(merged, id=button_id))
    if new is None:
        raise CmdlyError("That would leave the button without a command.")
    buttons[index] = new
    client.post("/api/config", {"buttons": buttons})
    where = "this computer" if new.get("target") != "ssh" else f"ssh on “{new.get('connection')}”"
    how = "in a terminal" if new.get("mode") != "background" else "in the background"
    return (f"Updated the button “{new.get('label')}” ({new.get('id')}): {how} on {where}, "
            f"running “{new.get('command')}”."
            + (f" Changed: {', '.join(changed)}." if changed else " Nothing changed."))


@tool("list_computers",
      "The computers in this Cmdly: the companion cards (what the top of the "
      "window shows, each pinged by the app) and the saved SSH connections "
      "the buttons run over. `ping` says whether one answers right now.",
      {"type": "object", "properties": {}, "additionalProperties": False})
def _list_computers(client: CmdlyClient, args: dict[str, Any]) -> str:
    config = client.config()
    buttons = config.get("buttons") or []
    lines: list[str] = []
    companions = config.get("companions") or []
    lines.append("Companion computers (the cards at the top):"
                 if companions else "No companion computers are set up.")
    for c in companions:
        kind = "ssh" if c.get("type") == "ssh" else "ping only"
        text = (f"  {c.get('id')} “{c.get('name') or c.get('host')}” · {c.get('host')} · {kind}"
                + (f", over connection {c.get('connection')}" if c.get("connection") else "")
                + f", pinged every {c.get('interval_s')}s")
        lines.append(text)
    connections = config.get("connections") or []
    lines.append("Saved SSH connections:" if connections else "No SSH connections are saved.")
    for c in connections:
        creds = [what for what, on in (("key file", c.get("key_path")),
                                       ("password", c.get("has_password"))) if on]
        used = sum(1 for b in buttons if b.get("connection") == c.get("name"))
        lines.append(f"  {c.get('name')} → {_text(c.get('username'))}@{c.get('host')}:{c.get('port')}"
                     + (f" · {', '.join(creds)}" if creds else " · no credentials saved")
                     + (f" · {used} button{'s' if used > 1 else ''}" if used else ""))
    return "\n".join(lines)


@tool("press_button",
      "Press a button of the shelf, exactly as the person's press does: a "
      "terminal button types its line into its own session (one is opened "
      "when it has none; Ctrl-C first when the button says restart), a "
      "background button runs once. While it runs the shelf row shows it.",
      {"type": "object",
       "properties": {
           "id": {"type": "string", "description": "The button's id (as list_buttons shows)."},
           "label": {"type": "string", "description": "The button's label, when its id is unknown."},
       },
       "additionalProperties": False},
      gated=True)
def _press_button(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    config = client.config()
    button = _find_button(list(config.get("buttons") or []),
                          _text(args.get("id")).strip(), _text(args.get("label")).strip())[1]
    label = button.get("label", "")
    if button.get("mode") == "background":
        target = "local" if button.get("target") != "ssh" else _text(button.get("connection"))
        result = _run_once(client, command=_text(button.get("command")), target=target,
                           directory=_text(button.get("directory")), detach=True)
        return f"Pressed “{label}”. " + _run_summary(result, target)
    line = launcher.terminal_line(button)
    session = launcher.session_name(button.get("id", ""))
    if button.get("restart") is True:
        client.post("/api/ssh/send", {"name": session, "data": "\x03"})
        time.sleep(INTERRUPT_GRACE_S)
    reply = client.post("/api/ssh/send", {"name": session, "data": line + "\n"})
    if not reply.get("ok"):
        # No session yet: open one the way a press does, then type the line.
        if button.get("target") == "ssh":
            connect = client.post("/api/ssh/connect",
                                  {"name": session, "from": _text(button.get("connection"))})
        else:
            connect = client.post("/api/local/connect",
                                  {"name": session, "directory": _text(button.get("directory"))})
        if not connect.get("ok"):
            raise CmdlyError(_text(connect.get("error")) or "Could not open the button's terminal.")
        client.post("/api/ssh/send", {"name": session, "data": line + "\n"})
    where = "this computer" if button.get("target") != "ssh" else _text(button.get("connection"))
    return (f"Pressed “{label}”: “{line}” now runs in its terminal on {where} "
            f"(session {session}). The row on the shelf shows it while it runs; "
            r"Ctrl-C (\u0003 through send_to_terminal) stops it.")


@tool("ping",
      "Send one ICMP echo to a computer and wait for the reply — the same "
      "reachability the companion cards show, as one ask.",
      {"type": "object",
       "properties": {
           "host": {"type": "string", "description": "IP address or host name."},
           "wait_ms": {"type": "integer",
                       "description": "How long to wait for the reply (default 2000)."},
       },
       "required": ["host"], "additionalProperties": False},
      gated=True)
def _ping(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    host = _text(args.get("host")).strip()
    if not host:
        raise CmdlyError("host is required.")
    raw_wait = args.get("wait_ms")
    wait_ms = raw_wait if isinstance(raw_wait, (int, float)) and not isinstance(raw_wait, bool) else 2000
    reply = client.post("/api/local/ping", {"host": host, "wait_ms": wait_ms})
    if not reply.get("ok"):
        raise CmdlyError(_text(reply.get("error")) or "The ping could not be made.")
    if reply.get("reachable"):
        rtt = reply.get("rtt_ms")
        return f"{host} is up ({rtt:g} ms)." if isinstance(rtt, (int, float)) else f"{host} is up."
    return f"{host} did not answer within {_clip(wait_ms, 1, 60000, 2000) / 1000:g} seconds."


# ---- terminals: the person's switch -------------------------------------------


@tool("list_terminals",
      "The open terminal sessions (theirs and an agent's), with where each "
      "runs and whether it is connected.",
      {"type": "object", "properties": {}, "additionalProperties": False},
      gated=True)
def _list_terminals(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    sessions = client.sessions()
    if not sessions:
        return "No terminal sessions are open. open_terminal opens one."
    return "\n".join(
        f"{s.get('name')} · {_text(s.get('username'))}@{_text(s.get('host'))}"
        f"{' connected' if s.get('connected') else ' closed'}"
        for s in sessions)


@tool("open_terminal",
      "Open a terminal: a login shell on this computer, or one over a saved "
      "SSH connection. The person sees it as a terminal window in Cmdly, as "
      "any terminal. One that is already open stays as it is.",
      {"type": "object",
       "properties": {
           "name": {"type": "string",
                    "description": "The session's name; default “main”. Shown as the window's title."},
           "target": {"type": "string",
                      "description": "“local” (the default), or the name of a saved SSH connection."},
           "directory": {"type": "string",
                         "description": "Where the shell starts (local terminals only)."},
       },
       "additionalProperties": False},
      gated=True)
def _open_terminal(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    name = session_name(args.get("name"))
    where, opened = _ensure_session(client, name, args)
    if not opened:
        return (f"The terminal {name} is already open ({where}). Type into it with "
                "send_to_terminal, or run_in_terminal to run a command in it.")
    return (f"The terminal {name} is open on {where}. The person sees it as a terminal "
            "window in Cmdly. Type into it with send_to_terminal, or run_in_terminal "
            "to run a command in it.")


@tool("run_in_terminal",
      "Type a command into a terminal and return what it printed — the one "
      "an agent works in, kept between calls unless you name another. It "
      "returns as soon as the shell has finished the command (the completion "
      "is marked in a way the wait sees and the person's window does not); "
      "a command still running past `wait_s` is read later with read_terminal.",
      {"type": "object",
       "properties": {
           "command": {"type": "string", "description": "The command line to run."},
           "name": {"type": "string",
                    "description": "The session's name; default “main”. One that exists is reused."},
           "target": {"type": "string",
                      "description": "For a terminal opened here: “local” (the default), or a saved SSH connection."},
           "directory": {"type": "string", "description": "Where a new local shell starts."},
           "wait_s": {"type": "number",
                      "description": f"How long to wait for the command to finish before "
                                     f"returning what it printed so far (0-{int(MAX_WAIT_S)}s, "
                                     f"default {int(DEFAULT_WAIT_S)})."},
       },
       "required": ["command"], "additionalProperties": False},
      gated=True)
def _run_in_terminal(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    command = _text(args.get("command")).strip()
    if not command:
        raise CmdlyError("command is required.")
    name = session_name(args.get("name"))
    _ensure_session(client, name, args)
    # The printf prints a unique marker, then erases its own line twice: the
    # person's window shows nothing of it, while the raw stream keeps the
    # marker, which is what the wait below looks for.
    marker = f"__CMDLY_DONE_{uuid.uuid4().hex[:8]}__"
    line = f"{command} ; printf '\\033[2K\\r{marker}\\r\\033[2K'"
    client.post("/api/ssh/send", {"name": name, "data": line + "\n"})
    # The pty echoes the typed line, the marker's text included; what says the
    # command is done is the printf's output — the escape byte the echo can
    # only ever show as the text "\033[2K".
    done_at = f"\x1b[2K\r{marker}"
    budget = _clip(args.get("wait_s"), 0.1, MAX_WAIT_S, DEFAULT_WAIT_S)
    deadline = time.monotonic() + budget
    while True:
        raw = _read_terminal(client, name, MAX_TAIL)
        if done_at in raw or time.monotonic() >= deadline:
            break
        time.sleep(0.25)
    if done_at in raw:
        done = raw.split(done_at)[0][-DEFAULT_TAIL:]
        return done.strip("\r\n") if done.strip() else "(the command printed nothing)"
    note = (f"(no completion within {budget:g} seconds — the command may still be running; "
            "read_terminal shows more, send_to_terminal types into it)")
    raw = raw[-DEFAULT_TAIL:]
    return (raw.strip("\r\n") + "\n" + note) if raw.strip() else note


@tool("send_to_terminal",
      "Type raw keys into an open terminal: what an interactive program asks "
      "for, or Ctrl-C (\\u0003) to stop what runs. Enter is \\n.",
      {"type": "object",
       "properties": {
           "name": {"type": "string", "description": "The session's name, as open_terminal returned."},
           "data": {"type": "string", "description": "The keys to type."},
           "wait_s": {"type": "number",
                      "description": "How long to wait before reading what it printed (default 1)."},
       },
       "required": ["name", "data"], "additionalProperties": False},
      gated=True)
def _send_to_terminal(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    name = session_name(args.get("name"))
    data = args.get("data")
    if not isinstance(data, str) or data == "":
        raise CmdlyError("data is required: the keys to type.")
    reply = client.post("/api/ssh/send", {"name": name, "data": data})
    if not reply.get("ok"):
        raise CmdlyError(f"There is no open terminal named {name}. "
                         "open_terminal or run_in_terminal opens one.")
    wait = _clip(args.get("wait_s"), 0.0, MAX_WAIT_S, 1.0)
    if wait:
        time.sleep(wait)
    output = _read_terminal(client, name, DEFAULT_TAIL)
    return output if output else f"Sent to {name}. Nothing new was printed."


@tool("read_terminal",
      "What a terminal has printed so far: its scrollback, the last `tail` "
      "bytes (16 KiB by default).",
      {"type": "object",
       "properties": {
           "name": {"type": "string", "description": "The session's name."},
           "tail": {"type": "integer", "description": "How many bytes of the end to return."},
       },
       "required": ["name"], "additionalProperties": False},
      gated=True)
def _read_terminal_tool(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    name = session_name(args.get("name"))
    tail = args.get("tail") if isinstance(args.get("tail"), int) \
        and not isinstance(args.get("tail"), bool) else DEFAULT_TAIL
    try:
        output = _read_terminal(client, name, tail)
    except CmdlyError as exc:
        raise CmdlyError(f"There is no terminal named {name}.") from exc
    return output if output else f"{name} has printed nothing so far."


@tool("close_terminal",
      "Close a terminal session. What it was running is stopped by that.",
      {"type": "object",
       "properties": {"name": {"type": "string", "description": "The session's name."}},
       "required": ["name"], "additionalProperties": False},
      gated=True)
def _close_terminal(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    name = session_name(args.get("name"))
    reply = client.post("/api/ssh/disconnect", {"name": name})
    if not reply.get("ok"):
        raise CmdlyError(f"There is no open terminal named {name}.")
    return f"Closed {name} (what it was running is stopped by that)."


@tool("run_command",
      "Run one command without a terminal, once: on this computer (a child "
      "of Cmdly, stopped when Cmdly quits), or over a saved SSH connection "
      "(detached under nohup it outlives Cmdly there). Returns the exit "
      "status and the output.",
      {"type": "object",
       "properties": {
           "command": {"type": "string", "description": "The command line to run."},
           "target": {"type": "string",
                      "description": "“local” (the default), or the name of a saved SSH connection."},
           "directory": {"type": "string", "description": "The folder to run it in, if any."},
           "detach": {"type": "boolean",
                      "description": "SSH only: let it outlive the connection (background one-shot)."},
       },
       "required": ["command"], "additionalProperties": False},
      gated=True)
def _run_command(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    command = _text(args.get("command")).strip()
    if not command:
        raise CmdlyError("command is required.")
    target = _text(args.get("target")).strip() or "local"
    result = _run_once(client, command=command, target=target,
                       directory=_text(args.get("directory")), detach=args.get("detach") is True)
    return _run_summary(result, target)


@tool("power",
      "Shut a computer down or reboot it: this computer, or a companion over "
      "its saved SSH connection. On this computer there is no password to "
      "give sudo: it needs the person's own privileges (sudoers, a root "
      "shell), and a refusal says so.",
      {"type": "object",
       "properties": {
           "action": {"type": "string", "enum": ["shutdown", "reboot"]},
           "target": {"type": "string",
                      "description": "“local” (the default), or the name of a saved SSH connection."},
       },
       "required": ["action"], "additionalProperties": False},
      gated=True)
def _power(client: CmdlyClient, args: dict[str, Any]) -> str:
    client.require_permission()
    action = args.get("action")
    if action not in launcher.POWER_ACTIONS:
        raise CmdlyError("action must be “shutdown” or “reboot”.")
    target = _text(args.get("target")).strip() or "local"
    if target == "local":
        r = client.post("/api/local/power", {"action": action})
        where = "this computer"
    else:
        r = client.post("/api/ssh/power", {"name": target, "action": action})
        where = target
    if not r.get("ok"):
        detail = _text(r.get("output")) or _text(r.get("stderr")) or _text(r.get("error"))
        raise CmdlyError(f"{where} was not {'shut down' if action == 'shutdown' else 'rebooted'}."
                         + (f"\n{detail}" if detail else ""))
    verb = "shutting down" if action == "shutdown" else "rebooting"
    return f"{where} is {verb}."


# ---------------------------------------------------------------------------
# the protocol
# ---------------------------------------------------------------------------


def _result(id_: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _tool_specs(client: CmdlyClient) -> list[dict[str, Any]]:
    """The tools, each gated one saying where the switch stands right now."""
    allowed: bool | None = None  # unknown until the backend has been asked
    out: list[dict[str, Any]] = []
    for spec in TOOLS:
        description = spec["description"]
        if spec["gated"]:
            if allowed is None:
                try:
                    allowed = client.agent_allowed()
                except CmdlyError:
                    allowed = None  # Cmdly is not running; the plain text stays
            if allowed is True:
                description += "\n\nAllowed: the person has turned on terminal and power control."
            elif allowed is False:
                description += ("\n\nRefused right now: the person has not allowed terminal and "
                                "power control (Settings → Agent in Cmdly).")
        out.append({"name": spec["name"], "description": description,
                    "inputSchema": spec["inputSchema"]})
    return out


def _call_tool(client: CmdlyClient, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """One tool call. Its refusals and failures are tool answers (``isError``),
    not protocol errors: the agent is meant to read them and go on."""
    spec = next(t for t in TOOLS if t["name"] == name)
    try:
        return {"content": [{"type": "text", "text": str(spec["run"](client, arguments))}],
                "isError": False}
    except CmdlyError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    except Exception:  # noqa: BLE001 - one bad call must not take the server down
        logger.exception("tool %s failed", name)
        return {"content": [{"type": "text",
                             "text": "The tool failed with an internal error; the log (stderr) says why."}],
                "isError": True}


def handle_message(msg: Any, client: CmdlyClient) -> dict[str, Any] | None:
    """One client message; its reply, or None when it wants none.

    Tests drive this directly; :func:`serve` is the loop around it.
    """
    if not isinstance(msg, dict):
        return _error(None, -32600, "invalid request: expected an object")
    method = msg.get("method")
    if not isinstance(method, str):
        return _error(msg.get("id"), -32600, "invalid request: no method")
    if "id" not in msg:
        return None  # a notification: never answered
    id_ = msg["id"]
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if isinstance(requested, str) and requested else PROTOCOL_VERSION
        return _result(id_, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "cmdly", "version": get_version()},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _result(id_, {})
    if method == "tools/list":
        return _result(id_, {"tools": _tool_specs(client)})
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return _error(id_, -32602, "tools/call: name must be a string")
        if not any(t["name"] == name for t in TOOLS):
            return _error(id_, -32602, f"unknown tool: {name}")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return _error(id_, -32602, "tools/call: arguments must be an object")
        return _result(id_, _call_tool(client, name, arguments))
    return _error(id_, -32601, f"method not found: {method}")


def serve(reader, write, client: CmdlyClient) -> None:
    """The protocol loop: lines in, replies out, until the input ends.

    *reader* yields one message per line; *write* sends one reply however
    the caller wants (``run`` writes it to stdout, the tests collect them).
    A message that is not JSON is answered, not fatal.
    """
    for line in reader:
        try:
            msg = json.loads(line)
        except ValueError:
            write(_error(None, -32700, "parse error"))
            continue
        try:
            reply = handle_message(msg, client)
        except Exception:  # noqa: BLE001 - the loop outlives any one message
            logger.exception("handling a message failed")
            reply = _error(None, -32603, "internal error")
        if reply is not None:
            write(reply)


def run() -> int:
    """``python -m cmdly mcp``: the MCP server on this process's stdio."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%H:%M:%S")
    client = CmdlyClient()

    def write(msg: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    try:
        serve(sys.stdin, write, client)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    return 0
