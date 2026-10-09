"""The shelf's rules: what a button, a companion computer and a saved SSH
connection are, and what a button runs.

Everything here is pure: it reads dictionaries a person may have edited by
hand (``~/.cmdly/config.json``, or a file imported from another computer) and
returns complete, valid ones, dropping what cannot be repaired. A half-written
entry costs that entry, never the whole shelf.

The frontend (``src/js/shelf.js``) keeps a copy of the few rules it needs
while a form is being typed in (the preview line, the host check); the backend
is where a value is decided before it is stored.

stdlib only.
"""
from __future__ import annotations

import re
import shlex
import uuid
from typing import Any

TARGET_LOCAL = "local"
TARGET_SSH = "ssh"
TARGETS = (TARGET_LOCAL, TARGET_SSH)

MODE_TERMINAL = "terminal"
MODE_BACKGROUND = "background"
MODES = (MODE_TERMINAL, MODE_BACKGROUND)

COMPANION_PING = "ping"
COMPANION_SSH = "ssh"

# Bounded so the shelf stays a shelf: past this, a person wants a script on
# the far end, not more buttons.
MAX_BUTTONS = 24
MAX_COMPANIONS = 12
MAX_CONNECTIONS = 64
MAX_LABEL = 60
MAX_COMMAND = 4096
MAX_DIRECTORY = 1024
MAX_COMPANION_NAME = 40
MAX_CONNECTION_NAME = 120

# The slider stops, in seconds. Timeouts start above the shortest interval,
# because a timeout no longer than the interval calls every reply late.
INTERVAL_STEPS = (1, 2, 3, 5, 10)
TIMEOUT_STEPS = (3, 4, 6, 10, 15, 20, 30)
DEFAULT_INTERVAL_S = 2
DEFAULT_TIMEOUT_S = 6

# The same rule net_probe applies, so nothing is stored that cannot be pinged.
HOST_RE = re.compile(r"^[A-Za-z0-9:](?:[A-Za-z0-9._:%-]*[A-Za-z0-9])?$")

# The session a button's terminal runs in, apart from every other button's.
SESSION_PREFIX = "cmdly/"


def new_id(prefix: str) -> str:
    """A short, collision-free id. Never shown."""
    return prefix + uuid.uuid4().hex[:10]


def _text(value: Any, limit: int, strip: bool = True) -> str:
    if value is None:
        return ""
    text = str(value)
    if strip:
        text = text.strip()
    return text[:limit]


# ---- hosts and steps ------------------------------------------------------


def host_error(host: Any) -> str:
    """Why *host* cannot be pinged or connected to, or ``""`` when it can."""
    h = _text(host, 1000)
    if not h:
        return "Enter an IP address or host name."
    if len(h) > 253 or not HOST_RE.match(h):
        return "That is not an IP address or host name."
    return ""


def nearest_step(steps: tuple[int, ...], value: Any, fallback: int) -> int:
    """The stop in *steps* closest to *value*, or *fallback* for a non-number."""
    if isinstance(value, bool):
        return fallback
    try:
        n = float(value)
    except (TypeError, ValueError):
        return fallback
    if n != n:  # NaN
        return fallback
    return min(steps, key=lambda s: abs(s - n))


def timeout_for(interval: int) -> int:
    """The shortest timeout that is still longer than *interval*."""
    return next((t for t in TIMEOUT_STEPS if t > interval), TIMEOUT_STEPS[-1])


def interval_for(timeout: int) -> int:
    """The longest interval that is still shorter than *timeout*."""
    fits = [i for i in INTERVAL_STEPS if i < timeout]
    return fits[-1] if fits else INTERVAL_STEPS[0]


# ---- SSH connections --------------------------------------------------------


def derived_name(username: Any, host: Any) -> str:
    """``user@host``, the name a connection is saved under when none is typed."""
    h = _text(host, 253)
    if not h:
        return ""
    u = _text(username, 64)
    return f"{u}@{h}" if u else h


def coerce_port(value: Any, fallback: int = 22) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        port = int(value)
    except (TypeError, ValueError):
        return fallback
    return port if 1 <= port <= 65535 else fallback


def coerce_connection(raw: Any) -> dict[str, Any] | None:
    """One saved SSH connection, complete, or None when it has no host."""
    if not isinstance(raw, dict):
        return None
    host = _text(raw.get("host"), 253)
    if not host:
        return None
    username = _text(raw.get("username"), 64)
    name = _text(raw.get("name"), MAX_CONNECTION_NAME) or derived_name(username, host)
    return {
        "name": name,
        "host": host,
        "port": coerce_port(raw.get("port")),
        "username": username,
        # Not stripped: a password may begin or end with a space.
        "password": _text(raw.get("password"), 1024, strip=False),
        "key_path": _text(raw.get("key_path"), 1024),
    }


def public_connection(conn: dict[str, Any]) -> dict[str, Any]:
    """A connection as the page may see it: never the password itself."""
    out = {k: v for k, v in conn.items() if k != "password"}
    out["has_password"] = bool(conn.get("password"))
    return out


# ---- buttons ------------------------------------------------------------


def coerce_target(raw: dict[str, Any]) -> str:
    """Where a saved button runs: on this computer unless it says SSH."""
    target = raw.get("target")
    return target if target in TARGETS else TARGET_LOCAL


def coerce_mode(raw: dict[str, Any]) -> str:
    """A button's run mode: in a terminal unless it says background."""
    mode = raw.get("mode")
    return mode if mode in MODES else MODE_TERMINAL


def coerce_button(raw: Any) -> dict[str, Any] | None:
    """One saved button, complete, or None to drop it (no command)."""
    if not isinstance(raw, dict):
        return None
    command = _text(raw.get("command"), MAX_COMMAND)
    if not command:
        return None
    target = coerce_target(raw)
    button_id = _text(raw.get("id"), 40)
    if not button_id or not re.match(r"^[A-Za-z0-9_-]+$", button_id):
        button_id = new_id("b")
    return {
        "id": button_id,
        "label": _text(raw.get("label"), MAX_LABEL) or command[:MAX_LABEL],
        "target": target,
        # A button here names no connection; one left from when it ran
        # elsewhere would only mislead whoever reads the file.
        "connection": "" if target == TARGET_LOCAL else _text(raw.get("connection"), MAX_CONNECTION_NAME),
        "directory": _text(raw.get("directory"), MAX_DIRECTORY),
        "command": command,
        "mode": coerce_mode(raw),
        "restart": raw.get("restart") is True,
    }


def normalize_buttons(raw: Any) -> list[dict[str, Any]]:
    """The shelf from whatever was saved: complete buttons, unique ids, capped."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        button = coerce_button(item)
        if button is None or len(out) >= MAX_BUTTONS:
            continue
        if button["id"] in seen:
            button["id"] = new_id("b")
        seen.add(button["id"])
        out.append(button)
    return out


def session_name(button_id: str) -> str:
    """The terminal session a button (or a companion) runs in."""
    return SESSION_PREFIX + str(button_id or "")


def shell_folder(directory: str) -> str:
    """A folder as a POSIX shell should read it: quoted, except a leading ``~``."""
    def quote(text: str) -> str:
        return "'" + text.replace("'", "'\\''") + "'"

    d = directory.strip()
    if d == "~":
        return "~"
    if d.startswith("~/"):
        rest = d[2:]
        return f"~/{quote(rest)}" if rest else "~/"
    return quote(d)


def terminal_line(button: dict[str, Any]) -> str:
    """The line a button types into its terminal: ``cd -- <folder> && <command>``."""
    command = _text(button.get("command"), MAX_COMMAND)
    if not command:
        return ""
    directory = _text(button.get("directory"), MAX_DIRECTORY)
    if not directory:
        return command
    return f"cd -- {shell_folder(directory)} && {command}"


def remote_command(directory: str, command: str, detach: bool) -> str:
    """The line a background run sends to the remote shell.

    With *detach* the program is started under ``nohup`` in the background and
    its pid echoed, so it outlives the SSH connection and Cmdly itself.
    *command* is passed through as typed: it is a command line for that
    machine, and the SSH account's own permissions are the boundary.
    """
    command = command.strip()
    body = f"{{ nohup {command} >/dev/null 2>&1 & }}; echo $!" if detach else command
    directory = directory.strip()
    if directory:
        return f"cd -- {shlex.quote(directory)} && {body}"
    return body


#: What the companion card's power menu (right-click) may ask for, and the
#: line each runs over the companion's saved SSH connection: ``sudo`` first —
#: a companion is usually logged in as a user with passwordless sudo — and
#: the bare command as the fallback for a root login. Whichever runs takes
#: the computer down, and the connection with it.
POWER_ACTIONS = {
    "shutdown": "sudo shutdown -h now || shutdown -h now",
    "reboot": "sudo reboot || reboot",
}


# ---- companion computers -------------------------------------------------


def coerce_companion(raw: Any) -> dict[str, Any] | None:
    """One companion computer, complete, or None when its host is unusable."""
    if not isinstance(raw, dict):
        return None
    host = _text(raw.get("host"), 253)
    if host_error(host):
        return None
    interval = nearest_step(INTERVAL_STEPS, raw.get("interval_s"), DEFAULT_INTERVAL_S)
    timeout = nearest_step(TIMEOUT_STEPS, raw.get("timeout_s"), DEFAULT_TIMEOUT_S)
    if timeout <= interval:
        timeout = timeout_for(interval)
    connection = _text(raw.get("connection"), MAX_CONNECTION_NAME)
    kind = raw.get("type")
    if kind not in (COMPANION_PING, COMPANION_SSH):
        kind = COMPANION_SSH if connection else COMPANION_PING
    if kind == COMPANION_PING:
        connection = ""
    elif not connection:
        kind = COMPANION_PING
    companion_id = _text(raw.get("id"), 40)
    if not companion_id or not re.match(r"^[A-Za-z0-9_-]+$", companion_id):
        companion_id = new_id("c")
    return {
        "id": companion_id,
        "name": _text(raw.get("name"), MAX_COMPANION_NAME),
        "host": host,
        "type": kind,
        "connection": connection,
        "interval_s": interval,
        "timeout_s": timeout,
    }


def normalize_companions(raw: Any, legacy: Any = None) -> list[dict[str, Any]]:
    """Every companion computer. *legacy* is the single ``companion`` an older
    config kept, used only when there is no list."""
    items = raw if isinstance(raw, list) else []
    if not items and isinstance(legacy, dict):
        items = [legacy]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        companion = coerce_companion(item)
        if companion is None or len(out) >= MAX_COMPANIONS:
            continue
        if companion["id"] in seen:
            companion["id"] = new_id("c")
        seen.add(companion["id"])
        out.append(companion)
    return out


def pick_active(companions: list[dict[str, Any]], wanted: Any) -> str:
    """The id of the companion the indicator watches: *wanted* when it is one
    of them (by id, or by name for older configs), else the first, else ``""``."""
    key = _text(wanted, 80)
    for c in companions:
        if key and (c["id"] == key or c["name"] == key):
            return c["id"]
    return companions[0]["id"] if companions else ""


def button_reachable(button: dict[str, Any], companion: dict[str, Any] | None,
                     online: bool, connections: list[dict[str, Any]]) -> bool:
    """Whether a button can run right now, for the "reachable only" filter.

    A local button always can. An SSH button can when the companion computer
    it runs on is online: its connection is the companion's own, or names the
    companion's host.
    """
    if button.get("target") != TARGET_SSH:
        return True
    if not companion or not online:
        return False
    name = button.get("connection", "")
    if companion.get("connection") and name == companion["connection"]:
        return True
    host = str(companion.get("host", "")).lower()
    conn = next((c for c in connections if c.get("name") == name), None)
    return bool(conn and str(conn.get("host", "")).lower() == host)
