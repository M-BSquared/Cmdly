"""Registry and lifecycle manager for all terminal sessions."""

from typing import Dict, Optional
from PySide6.QtCore import QObject, Signal

from app.models import SshConnection
from app.sessions.base_session import BaseSession
from app.sessions.local_session import LocalSession
from app.sessions.ssh_session import SshSession


class SessionManager(QObject):
    session_started = Signal(str)          # (session_id)
    session_stopped = Signal(str)          # (session_id)
    session_output = Signal(str, str)      # (session_id, chunk)
    session_error = Signal(str, str)       # (session_id, error)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.sessions: Dict[str, BaseSession] = {}

    def get_session(self, session_id: str) -> Optional[BaseSession]:
        return self.sessions.get(session_id)

    def is_active(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        return bool(session and session.is_alive())

    def create_local_session(self, session_id: str, title: str) -> LocalSession:
        if session_id in self.sessions:
            self.stop_session(session_id)

        session = LocalSession(session_id, title, self)
        self._register_session(session_id, session)
        return session

    def create_ssh_session(self, session_id: str, title: str, conn: SshConnection) -> SshSession:
        if session_id in self.sessions:
            self.stop_session(session_id)

        session = SshSession(session_id, title, conn, self)
        self._register_session(session_id, session)
        return session

    def _register_session(self, session_id: str, session: BaseSession):
        self.sessions[session_id] = session

        session.output_received.connect(
            lambda text, sid=session_id: self.session_output.emit(sid, text)
        )
        session.error_occurred.connect(
            lambda err, sid=session_id: self.session_error.emit(sid, err)
        )
        session.session_closed.connect(
            lambda sid=session_id: self._on_session_closed(sid)
        )

    def _on_session_closed(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
        self.session_stopped.emit(session_id)

    def stop_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if session:
            session.stop()
            if session_id in self.sessions:
                del self.sessions[session_id]
            self.session_stopped.emit(session_id)

    def close_all(self):
        for sid in list(self.sessions.keys()):
            self.stop_session(sid)
