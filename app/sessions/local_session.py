"""Local interactive shell session using PTY on POSIX or subprocess on Windows."""

import os
import signal
import sys
import threading
import subprocess
from typing import Optional
from PySide6.QtCore import QObject

from app.sessions.base_session import BaseSession


class LocalSession(BaseSession):
    def __init__(self, session_id: str, title: str, parent: Optional[QObject] = None):
        super().__init__(session_id, title, parent)
        self.master_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_requested = False

    def start(self) -> bool:
        self._stop_requested = False

        if os.name == "posix":
            return self._start_posix()
        else:
            return self._start_windows()

    def _start_posix(self) -> bool:
        import pty
        import termios
        import struct
        import fcntl

        try:
            self.master_fd, slave_fd = pty.openpty()

            # Set terminal window size: 24 rows, 80 cols
            winsize = struct.pack("HHHH", 24, 80, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

            shell = os.environ.get("SHELL", "/bin/zsh" if sys.platform == "darwin" else "/bin/bash")
            if not os.path.exists(shell):
                shell = "/bin/sh"

            env = dict(os.environ)
            env["TERM"] = "xterm-256color"

            # Use subprocess.Popen with interactive flag
            self.proc = subprocess.Popen(
                [shell, "-i"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                env=env,
            )
            os.close(slave_fd)

            self.pid = self.proc.pid
            self._running = True

            self._reader_thread = threading.Thread(target=self._posix_reader, daemon=True)
            self._reader_thread.start()
            return True
        except Exception as e:
            self._running = False
            self.error_occurred.emit(str(e))
            return False

    def _posix_reader(self):
        try:
            while not self._stop_requested and self.master_fd is not None:
                try:
                    data = os.read(self.master_fd, 1024)
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace")
                    self.output_received.emit(text)
                except OSError:
                    break
        finally:
            self._running = False
            self.session_closed.emit()

    def _start_windows(self) -> bool:
        try:
            shell = os.environ.get("COMSPEC", "cmd.exe")
            self.proc = subprocess.Popen(
                [shell],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            self.pid = self.proc.pid
            self._running = True
            self._reader_thread = threading.Thread(target=self._windows_reader, daemon=True)
            self._reader_thread.start()
            return True
        except Exception as e:
            self._running = False
            self.error_occurred.emit(str(e))
            return False

    def _windows_reader(self):
        try:
            while not self._stop_requested and self.proc and self.proc.stdout:
                line = self.proc.stdout.read(1024)
                if not line:
                    break
                text = line.decode("utf-8", errors="replace")
                self.output_received.emit(text)
        finally:
            self._running = False
            self.session_closed.emit()

    def send(self, data: str):
        if not self._running:
            return
        try:
            b = data.encode("utf-8")
            if os.name == "posix" and self.master_fd is not None:
                os.write(self.master_fd, b)
            elif self.proc and self.proc.stdin:
                self.proc.stdin.write(b)
                self.proc.stdin.flush()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def interrupt(self):
        """Send Ctrl-C (\\x03)."""
        self.send("\x03")

    def stop(self):
        self._stop_requested = True
        self._running = False

        if self.proc:
            try:
                self.proc.terminate()
                self.proc.kill()
                self.proc.wait(timeout=0.2)
            except Exception:
                pass
            self.proc = None

        if os.name == "posix" and self.master_fd is not None:
            fd = self.master_fd
            self.master_fd = None
            try:
                os.close(fd)
            except OSError:
                pass

        self.session_closed.emit()
