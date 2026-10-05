"""Data models and pure business logic for Cmdly / Schwalby launcher."""

from dataclasses import dataclass, field, asdict
import re
import uuid
from typing import Optional, List, Dict, Any

# Constants matching original plugin specification
TARGET_LOCAL = "local"
TARGET_SSH = "ssh"

TARGETS = [
    {"value": TARGET_LOCAL, "label": "Local", "icon": "laptop", "title": "Run it on this computer"},
    {"value": TARGET_SSH, "label": "SSH", "icon": "server", "title": "Run it over an SSH connection"},
]

MODE_TERMINAL = "terminal"
MODE_BACKGROUND = "background"

COMPANION_TARGET_PING = "ping"
COMPANION_TARGET_SSH = "ssh"

COMPANION_TARGETS = [
    {"value": COMPANION_TARGET_PING, "label": "Ping", "icon": "activity", "title": "Only ping an IP address or host name"},
    {"value": COMPANION_TARGET_SSH, "label": "SSH", "icon": "server", "title": "Connect over SSH and ping its host"},
]

LOCAL_HOST = "this computer"
NEW_CONNECTION = "__new__"
COMPANION_ID = "companion"

INTERVAL_STEPS = [1, 2, 3, 5, 10]
TIMEOUT_STEPS = [3, 4, 6, 10, 15, 20, 30]
DEFAULT_INTERVAL_S = 2
DEFAULT_TIMEOUT_S = 6
MAX_COMPANION_NAME = 40
MAX_BUTTONS = 12

HOST_RE = re.compile(r"^[A-Za-z0-9:](?:[A-Za-z0-9._:%-]*[A-Za-z0-9])?$")


@dataclass
class SshConnection:
    name: str = ""
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    key_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SshConnection":
        if not isinstance(data, dict):
            return cls()
        try:
            port = int(data.get("port", 22))
        except (ValueError, TypeError):
            port = 22
        return cls(
            name=str(data.get("name", "")).strip(),
            host=str(data.get("host", "")).strip(),
            port=port if 1 <= port <= 65535 else 22,
            username=str(data.get("username", "")).strip(),
            password=str(data.get("password", "")),
            key_path=str(data.get("key_path", "")).strip(),
        )


@dataclass
class ButtonConfig:
    id: str = field(default_factory=lambda: "b" + uuid.uuid4().hex[:10])
    label: str = ""
    target: str = TARGET_LOCAL
    connection: str = ""
    directory: str = ""
    command: str = ""
    mode: str = MODE_TERMINAL
    restart: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["ButtonConfig"]:
        if not isinstance(data, dict):
            return None
        command = str(data.get("command", "")).strip()
        if not command:
            return None
        label = str(data.get("label", "")).strip()
        target = data.get("target")
        if target not in (TARGET_LOCAL, TARGET_SSH):
            target = TARGET_SSH if str(data.get("connection", "")).strip() else TARGET_LOCAL

        mode = data.get("mode")
        if mode not in (MODE_TERMINAL, MODE_BACKGROUND):
            if "detach" in data:
                mode = MODE_BACKGROUND if data.get("detach") else MODE_TERMINAL
            else:
                mode = MODE_TERMINAL

        btn_id = str(data.get("id", "")).strip() or ("b" + uuid.uuid4().hex[:10])
        conn = "" if target == TARGET_LOCAL else str(data.get("connection", "")).strip()

        return cls(
            id=btn_id,
            label=label or command,
            target=target,
            connection=conn,
            directory=str(data.get("directory", "")).strip(),
            command=command,
            mode=mode,
            restart=bool(data.get("restart", False)),
        )


@dataclass
class CompanionConfig:
    name: str = ""
    host: str = ""
    type: str = COMPANION_TARGET_PING
    connection: str = ""
    interval_s: int = DEFAULT_INTERVAL_S
    timeout_s: int = DEFAULT_TIMEOUT_S

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["CompanionConfig"]:
        if not isinstance(data, dict):
            return None
        host = str(data.get("host", "")).strip()
        if not host or validate_host(host):
            return None

        interval = nearest_step(INTERVAL_STEPS, data.get("interval_s"), DEFAULT_INTERVAL_S)
        timeout = nearest_step(TIMEOUT_STEPS, data.get("timeout_s"), DEFAULT_TIMEOUT_S)
        if timeout <= interval:
            timeout = timeout_for(interval)

        conn = str(data.get("connection", "")).strip()[:120]
        ctype = data.get("type", COMPANION_TARGET_SSH if conn else COMPANION_TARGET_PING)

        return cls(
            name=str(data.get("name", "")).strip()[:MAX_COMPANION_NAME],
            host=host,
            type=ctype,
            connection=conn,
            interval_s=interval,
            timeout_s=timeout,
        )


def nearest_step(steps: List[int], value: Any, fallback: int) -> int:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return fallback
    return min(steps, key=lambda s: abs(s - n))


def timeout_for(interval: int) -> int:
    for t in TIMEOUT_STEPS:
        if t > interval:
            return t
    return TIMEOUT_STEPS[-1]


def interval_for(timeout: int) -> int:
    fits = [i for i in INTERVAL_STEPS if i < timeout]
    return fits[-1] if fits else INTERVAL_STEPS[0]


def validate_host(host: str) -> str:
    h = (host or "").strip()
    if not h:
        return "Enter an IP address or host name."
    if len(h) > 253 or not HOST_RE.match(h):
        return "That is not an IP address or host name."
    return ""


def derived_name(conn: SshConnection) -> str:
    host = (conn.host or "").strip()
    if not host:
        return ""
    user = (conn.username or "").strip()
    return f"{user}@{host}" if user else host


def validate_new_connection(conn: SshConnection, existing_names: List[str]) -> str:
    if not (conn.host or "").strip():
        return "Name the host to connect to."
    name = (conn.name or "").strip() or derived_name(conn)
    if conn.port < 1 or conn.port > 65535:
        return "The port has to be a number between 1 and 65535."
    if name in existing_names:
        return f'"{name}" is already saved. Pick it above, or save this one as another name.'
    return ""


def shell_folder(directory: str) -> str:
    """A folder as a POSIX shell should read it: quoted, preserving leading ~."""
    def quote(text: str) -> str:
        return "'" + text.replace("'", "'\\''") + "'"

    d = directory.strip()
    if d == "~":
        return "~"
    if d.startswith("~/"):
        rest = d[2:]
        return f"~/{quote(rest)}" if rest else "~/"
    return quote(d)


def terminal_line(button: ButtonConfig) -> str:
    """The line a button sends to its interactive terminal shell."""
    cmd = button.command.strip()
    if not cmd:
        return ""
    d = button.directory.strip()
    if not d:
        return cmd
    return f"cd -- {shell_folder(d)} && {cmd}"


def preview_line(button: ButtonConfig) -> str:
    """Human-readable preview of what will run."""
    cmd = button.command.strip()
    if not cmd:
        return ""
    directory = button.directory.strip()
    local = button.target == TARGET_LOCAL
    background = button.mode == MODE_BACKGROUND

    body = f"{cmd} &" if (background and local) else (f"nohup {cmd} &" if background else cmd)
    line = f"cd {directory} && {body}" if directory else body

    if local:
        return line
    target = button.connection.strip()
    return f"ssh {target} '{line}'" if target else line


def session_name(button_id: str) -> str:
    return f"schwalby/{button_id}"


def companion_session_name() -> str:
    return f"schwalby/{COMPANION_ID}"
