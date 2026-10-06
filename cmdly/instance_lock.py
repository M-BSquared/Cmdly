"""One Cmdly per machine, unless the operator says otherwise.

Cmdly owns things a second copy of itself cannot share: the terminal sessions
its buttons type into (a second window would open a second shell for the same
button, and the stop button in one would never reach the program the other
started) and ``~/.cmdly/config.json``, which both would rewrite from their own
copy. So the second launch is stopped here, before any of it is opened, and
told where the first one is listening. ``CMDLY_ALLOW_MULTI=1`` is the
deliberate way past it.

Mechanics: an advisory lock on ``~/.cmdly/cmdly.lock``, ``fcntl.flock`` on
POSIX, ``msvcrt.locking`` on Windows. Windows locks a *byte range*, and it
locks it mandatorily, so the byte taken is one far past the record
(:data:`_LOCK_BYTE`): otherwise the holder's own lock would hide the record
from the very process the record exists for.

Both locks are held by the *file handle*, so the OS drops the lock when the
process dies, however it dies: a crash or a ``kill -9`` leaves no stale lock to
clean up, which is exactly why this is a lock and not a pid file. The file's
contents (pid, port, start time) are only for the message the second instance
shows, never for deciding whether the first one is alive.

stdlib only, importable with no side effects.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from .paths import cmdly_path

logger = logging.getLogger("cmdly.instance_lock")

# Set to anything truthy to allow a second (third, ...) instance.
ALLOW_MULTI_ENV = "CMDLY_ALLOW_MULTI"

_TRUTHY = {"1", "true", "yes", "on"}

#: Offset of the byte Windows locks. Past any record the file will ever hold,
#: so the mandatory lock never covers the JSON. Locking beyond EOF is legal
#: and does not grow the file. POSIX ignores this: flock takes the whole file
#: and is advisory, so readers are unaffected either way.
_LOCK_BYTE = 1 << 30


def allow_multi() -> bool:
    """True when the operator opted into running more than one instance."""
    return str(os.environ.get(ALLOW_MULTI_ENV, "")).strip().lower() in _TRUTHY


def default_lock_path() -> str:
    """Absolute path of the lock file (``~/.cmdly/cmdly.lock``)."""
    return cmdly_path("cmdly.lock")


class InstanceLock:
    """An OS-held exclusive lock standing for "this machine's Cmdly".

    ``acquire()`` never raises: a filesystem that cannot lock (an exotic
    network mount, a read-only home) degrades to "allowed", because refusing
    to start over a locking quirk is worse than the race the
    lock was protecting against. It logs and returns True in that case.
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path or default_lock_path()
        self._fd: int | None = None
        self._held = False

    @property
    def path(self) -> str:
        return self._path

    @property
    def held(self) -> bool:
        return self._held

    def acquire(self, port: int | None = None) -> bool:
        """Take the lock. True when this process now owns it.

        False means another live Cmdly holds it — call :meth:`peer` for what
        to tell the operator. Idempotent: acquiring twice is a no-op that
        returns True and refreshes the recorded port.
        """
        if self._held:
            self.write_port(port)
            return True
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            # O_RDWR (not O_WRONLY): Windows' msvcrt.locking needs a handle
            # it can read through. peer() deliberately does not reuse this fd
            # — it is the refused process, holding no fd of its own, that has
            # to be able to read the record.
            fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        except (OSError, ValueError) as exc:
            # ValueError as well as OSError: a path the OS will not even look
            # at (an embedded null byte from a mangled HOME) fails in the
            # argument check rather than in the syscall. Both mean the same
            # thing here — there is no lock to be had — and the contract this
            # method advertises is that it never raises.
            logger.warning("instance lock unavailable at %s (%s); "
                           "not enforcing single instance", self._path, exc)
            return True
        try:
            if not _try_lock(fd):
                os.close(fd)
                return False
        except OSError as exc:
            # The platform cannot lock this file at all. Do not hold the
            # operator's launch hostage over it.
            logger.warning("instance lock not enforceable on %s (%s); "
                           "continuing without it", self._path, exc)
            os.close(fd)
            return True
        self._fd = fd
        self._held = True
        self.write_port(port)
        return True

    def write_port(self, port: int | None) -> None:
        """Record pid/port in the locked file, for the next launch to read.

        Best-effort: the lock is the contract, this is only the message.
        """
        if self._fd is None:
            return
        record = {"pid": os.getpid(), "port": port, "started": time.time()}
        try:
            os.lseek(self._fd, 0, os.SEEK_SET)
            os.truncate(self._fd, 0)
            os.write(self._fd, (json.dumps(record) + "\n").encode("utf-8"))
        except OSError as exc:  # noqa: BLE001 - never fail a launch over this
            logger.debug("could not write instance lock record: %s", exc)

    def peer(self) -> dict[str, Any]:
        """Read the holder's advertised ``{pid, port, started}``.

        Returns ``{}`` when the file is missing, empty or unreadable — the
        caller must treat every field as a hint, not a fact.
        """
        try:
            with open(self._path, encoding="utf-8") as handle:
                data = json.loads(handle.read() or "{}")
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def release(self) -> None:
        """Drop the lock and close the handle. Idempotent; never raises."""
        fd, self._fd, self._held = self._fd, None, False
        if fd is None:
            return
        try:
            _unlock(fd)
        except OSError as exc:  # noqa: BLE001 - teardown must always complete
            logger.debug("instance unlock failed: %s", exc)
        try:
            os.close(fd)
        except OSError as exc:  # noqa: BLE001 - teardown must always complete
            logger.debug("instance lock close failed: %s", exc)

    def __enter__(self) -> InstanceLock:
        self.acquire()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.release()


def _try_lock(fd: int) -> bool:
    """Non-blocking exclusive lock on *fd*. False when someone else holds it.

    Raises OSError only when the platform cannot lock this file at all, which
    the caller treats as "no enforcement" rather than "denied".
    """
    if os.name == "nt":
        import msvcrt
        try:
            os.lseek(fd, _LOCK_BYTE, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError as exc:
            # EACCES/EDEADLOCK is "another process holds it" — a real denial,
            # not a platform limitation, so report it as such.
            import errno
            if exc.errno in (errno.EACCES, errno.EDEADLOCK):
                return False
            raise
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False
    except OSError as exc:
        import errno
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            return False
        raise


def _unlock(fd: int) -> None:
    """Release the lock taken by :func:`_try_lock`."""
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, _LOCK_BYTE, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    import fcntl
    fcntl.flock(fd, fcntl.LOCK_UN)


def describe_peer(peer: dict[str, Any]) -> str:
    """One operator-facing line naming where the running instance is."""
    port = peer.get("port")
    pid = peer.get("pid")
    where = f"http://localhost:{port}/" if isinstance(port, int) and port else "(port unknown)"
    who = f" (pid {pid})" if isinstance(pid, int) and pid else ""
    return f"already running{who} at {where}"
