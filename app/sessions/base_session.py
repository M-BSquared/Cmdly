"""Base class for interactive terminal sessions."""

from abc import abstractmethod
from PySide6.QtCore import QObject, Signal


class BaseSession(QObject):
    output_received = Signal(str)  # Emits terminal stream output
    session_closed = Signal()      # Emitted when shell terminates
    error_occurred = Signal(str)   # Emitted on connection/execution error

    def __init__(self, session_id: str, title: str, parent: QObject = None):
        super().__init__(parent)
        self.session_id = session_id
        self.title = title
        self._running = False

    @abstractmethod
    def start(self) -> bool:
        """Start the interactive shell session."""
        pass

    @abstractmethod
    def send(self, data: str):
        """Send input characters/command to the shell."""
        pass

    @abstractmethod
    def interrupt(self):
        """Send Ctrl-C (\\x03) to the shell."""
        pass

    @abstractmethod
    def stop(self):
        """Terminate and disconnect the session."""
        pass

    def is_alive(self) -> bool:
        return self._running
