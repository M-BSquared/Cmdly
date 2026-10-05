"""SSH interactive shell session using Paramiko."""

import threading
from typing import Optional
import paramiko
from PySide6.QtCore import QObject

from app.models import SshConnection
from app.network.ssh_manager import SshManager
from app.sessions.base_session import BaseSession


class SshSession(BaseSession):
    def __init__(
        self,
        session_id: str,
        title: str,
        connection: SshConnection,
        parent: Optional[QObject] = None,
    ):
        super().__init__(session_id, title, parent)
        self.connection_config = connection
        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_requested = False

    def start(self) -> bool:
        self._stop_requested = False
        try:
            self.client = SshManager.create_client(self.connection_config)
            self.channel = self.client.invoke_shell(term="xterm-256color", width=80, height=24)
            self._running = True

            self._reader_thread = threading.Thread(target=self._reader, daemon=True)
            self._reader_thread.start()
            return True
        except Exception as e:
            self._running = False
            self.error_occurred.emit(str(e))
            return False

    def _reader(self):
        try:
            while not self._stop_requested and self.channel and not self.channel.closed:
                if self.channel.recv_ready():
                    data = self.channel.recv(1024)
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace")
                    self.output_received.emit(text)
                else:
                    if self.channel.exit_status_ready():
                        break
                    threading.Event().wait(0.02)
        except Exception:
            pass
        finally:
            self._running = False
            self.session_closed.emit()

    def send(self, data: str):
        if not self._running or not self.channel or self.channel.closed:
            return
        try:
            self.channel.send(data.encode("utf-8"))
        except Exception as e:
            self.error_occurred.emit(str(e))

    def interrupt(self):
        """Send Ctrl-C (\\x03)."""
        self.send("\x03")

    def stop(self):
        self._stop_requested = True
        self._running = False
        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
            self.channel = None
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        self.session_closed.emit()
