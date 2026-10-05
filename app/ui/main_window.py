"""Main application window coordinating all Cmdly views and services."""

import os
import subprocess
import time
from typing import Dict, Optional
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QStackedWidget,
    QLabel,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer

from app.config import ConfigManager
from app.models import (
    ButtonConfig,
    CompanionConfig,
    SshConnection,
    TARGET_LOCAL,
    TARGET_SSH,
    MODE_TERMINAL,
    MODE_BACKGROUND,
    session_name,
    companion_session_name,
    terminal_line,
    COMPANION_ID,
)
from app.network.ping_service import PingService
from app.network.ssh_manager import SshManager
from app.sessions.session_manager import SessionManager
from app.ui.widgets.companion_bar import CompanionBar
from app.ui.views.shelf_view import ShelfView
from app.ui.views.editor_view import EditorView
from app.ui.dialogs.companion_dialog import CompanionDialog
from app.ui.dialogs.terminal_window import TerminalWindow
from app.ui.styles import (
    MAIN_STYLESHEET,
    SURFACE_BG,
    TEXT_2,
    HEALTHY,
    CRITICAL,
    WARNING,
)


class MainWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Cmdly")
        self.resize(500, 620)
        self.setStyleSheet(MAIN_STYLESHEET)

        self.config_manager = config_manager
        self.session_manager = SessionManager(self)
        self.ping_service = PingService(self)
        self.terminal_window = TerminalWindow(self)

        self.errors: Dict[str, str] = {}  # button_id -> error_msg

        # Central Layout
        central = QWidget(self)
        central.setStyleSheet(f"background-color: {SURFACE_BG};")
        self.layout = QVBoxLayout(central)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(8)

        # 1. Companion Strip
        self.companion_bar = CompanionBar(central)
        self.companion_bar.clicked.connect(self._open_companion_dialog)
        self.companion_bar.open_terminal_requested.connect(self._open_companion_terminal)
        self.layout.addWidget(self.companion_bar)

        # 2. Status message strip (.schw-status)
        self.status_label = QLabel("Ready", central)
        self.status_label.setStyleSheet(f"font-size: 11.5px; color: {TEXT_2}; padding: 0 4px;")
        self.layout.addWidget(self.status_label)

        # 3. View Stack: ShelfView & EditorView
        self.stack = QStackedWidget(central)
        self.shelf_view = ShelfView(self.stack)
        self.editor_view = EditorView(self.config_manager.get_connections(), self.stack)

        self.stack.addWidget(self.shelf_view)
        self.stack.addWidget(self.editor_view)
        self.layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)

        # Connect Signals
        self._connect_signals()

        # Initialize Data
        self._refresh_shelf()
        self.ping_service.set_companion(self.config_manager.get_companion())

    def _connect_signals(self):
        # Ping Service
        self.ping_service.state_changed.connect(self._on_ping_state_changed)

        # Shelf View
        self.shelf_view.launch_requested.connect(self.launch_button)
        self.shelf_view.terminal_requested.connect(self.open_terminal)
        self.shelf_view.stop_requested.connect(self.stop_button)
        self.shelf_view.edit_requested.connect(self._open_editor)
        self.shelf_view.add_button_requested.connect(self._open_add_editor)

        # Editor View
        self.editor_view.saved.connect(self._on_editor_saved)
        self.editor_view.deleted.connect(self._on_editor_deleted)
        self.editor_view.cancelled.connect(lambda: self.stack.setCurrentWidget(self.shelf_view))

        # Session Manager
        self.session_manager.session_output.connect(self.terminal_window.append_output)
        self.session_manager.session_stopped.connect(self._on_session_stopped)
        self.session_manager.session_error.connect(self._on_session_error)

        # Terminal Window
        self.terminal_window.session_input.connect(self._send_terminal_input)
        self.terminal_window.session_interrupt.connect(self._send_terminal_interrupt)
        self.terminal_window.session_close.connect(self.session_manager.stop_session)

    def _refresh_shelf(self):
        buttons = self.config_manager.get_buttons()
        conns = self.config_manager.get_connections()
        active = {sid: True for sid, s in self.session_manager.sessions.items() if s.is_alive()}
        self.shelf_view.set_data(buttons, conns, active, self.errors)

    def _on_ping_state_changed(self, state: str, rtt_ms: Optional[float], error: str):
        self.companion_bar.set_data(self.config_manager.get_companion(), state, rtt_ms, error)

    def _set_status(self, text: str, kind: str = "info"):
        self.status_label.setText(text)
        color = HEALTHY if kind == "ok" else (CRITICAL if kind == "err" else TEXT_2)
        self.status_label.setStyleSheet(f"font-size: 11.5px; color: {color}; padding: 0 4px;")

    # ---- Companion Actions --------------------------------------------------

    def _open_companion_dialog(self):
        dlg = CompanionDialog(
            self.config_manager.get_companion(),
            self.config_manager.get_connections(),
            self,
        )
        if dlg.exec():
            if dlg.new_saved_connection:
                self.config_manager.save_connection(dlg.new_saved_connection)
            self.config_manager.set_companion(dlg.result_companion)
            self.ping_service.set_companion(dlg.result_companion)
            self._refresh_shelf()

    def _open_companion_terminal(self):
        comp = self.config_manager.get_companion()
        if not comp or not comp.connection:
            return

        conn = self.config_manager.get_connection_by_name(comp.connection)
        if not conn:
            self._set_status(f"Connection '{comp.connection}' not found", "err")
            return

        sid = companion_session_name()
        title = f"Companion: {comp.name or comp.host}"

        if not self.session_manager.is_active(sid):
            session = self.session_manager.create_ssh_session(sid, title, conn)
            if not session.start():
                self._set_status("Could not connect to companion SSH", "err")
                return

        self.terminal_window.ensure_tab(sid, title)
        self.terminal_window.show()
        self.terminal_window.raise_()

    # ---- Button Execution ----------------------------------------------------

    def launch_button(self, button: ButtonConfig):
        self.errors.pop(button.id, None)
        self.shelf_view.show_output("")

        if button.mode == MODE_BACKGROUND:
            self._launch_background(button)
        else:
            self._launch_terminal(button)

    def _launch_terminal(self, button: ButtonConfig):
        sid = session_name(button.id)
        cmd_line = terminal_line(button)

        if self.session_manager.is_active(sid):
            session = self.session_manager.get_session(sid)
            if button.restart:
                # Send Ctrl-C, wait 1000ms, then send command again
                session.interrupt()
                QTimer.singleShot(1000, lambda: session.send(cmd_line + "\n"))
                self._set_status(f"{button.label} restarted", "ok")
            else:
                session.send(cmd_line + "\n")
                self._set_status(f"{button.label} sent again to terminal", "ok")

            self.shelf_view.update_row_state(button.id, is_running=True)
            self.terminal_window.ensure_tab(sid, button.label)
            self.terminal_window.show()
            self.terminal_window.raise_()
            return

        # Start new session
        if button.target == TARGET_LOCAL:
            session = self.session_manager.create_local_session(sid, button.label)
            if not session.start():
                self.errors[button.id] = "Could not start local shell"
                self._set_status(f"Failed to launch {button.label}", "err")
                self._refresh_shelf()
                return
        else:
            conn = self.config_manager.get_connection_by_name(button.connection)
            if not conn:
                self.errors[button.id] = f"SSH connection '{button.connection}' not found"
                self._set_status(f"Missing connection for {button.label}", "err")
                self._refresh_shelf()
                return

            session = self.session_manager.create_ssh_session(sid, button.label, conn)
            if not session.start():
                self.errors[button.id] = "SSH connection failed"
                self._set_status(f"Failed to connect to {conn.name}", "err")
                self._refresh_shelf()
                return

        # Open tab and send initial command line
        self.terminal_window.ensure_tab(sid, button.label)
        self.terminal_window.show()
        self.terminal_window.raise_()

        # Send command line after slight delay so shell prompt is ready
        QTimer.singleShot(300, lambda: session.send(cmd_line + "\n"))
        self._set_status(f"{button.label} is running", "ok")
        self.shelf_view.update_row_state(button.id, is_running=True)

    def _launch_background(self, button: ButtonConfig):
        self._set_status(f"Starting {button.label} in background...", "info")

        if button.target == TARGET_LOCAL:
            try:
                cmd = button.command.strip()
                d = os.path.expanduser(button.directory.strip()) if button.directory.strip() else None
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=d,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self._set_status(f"{button.label}: running in background (pid {proc.pid})", "ok")
            except Exception as e:
                self.errors[button.id] = str(e)
                self._set_status(f"{button.label} failed", "err")
                self.shelf_view.show_output(str(e))
                self._refresh_shelf()
        else:
            conn = self.config_manager.get_connection_by_name(button.connection)
            if not conn:
                self.errors[button.id] = f"Connection '{button.connection}' not found"
                self._set_status(f"Missing SSH connection", "err")
                self._refresh_shelf()
                return

            import threading
            def bg_ssh_worker():
                ok, out, err = SshManager.run_detached(conn, button.directory, button.command)
                QTimer.singleShot(0, lambda: self._on_bg_ssh_done(button, ok, out, err))

            threading.Thread(target=bg_ssh_worker, daemon=True).start()

    def _on_bg_ssh_done(self, button: ButtonConfig, ok: bool, out: str, err: str):
        if ok:
            pid = out.strip()
            msg = f"running in background (pid {pid})" if pid else "running in background"
            self._set_status(f"{button.label}: {msg}", "ok")
        else:
            self.errors[button.id] = err or "SSH command failed"
            self._set_status(f"{button.label} failed", "err")
            self.shelf_view.show_output(err)
            self._refresh_shelf()

    def open_terminal(self, button: ButtonConfig):
        sid = session_name(button.id)
        if self.session_manager.is_active(sid):
            self.terminal_window.ensure_tab(sid, button.label)
            self.terminal_window.show()
            self.terminal_window.raise_()
        else:
            # Connect plain shell first
            self._connect_shell_only(button)

    def _connect_shell_only(self, button: ButtonConfig):
        sid = session_name(button.id)
        if button.target == TARGET_LOCAL:
            session = self.session_manager.create_local_session(sid, button.label)
            if not session.start():
                self.errors[button.id] = "Could not start local shell"
                self._refresh_shelf()
                return
        else:
            conn = self.config_manager.get_connection_by_name(button.connection)
            if not conn:
                self.errors[button.id] = f"Connection '{button.connection}' not found"
                self._refresh_shelf()
                return
            session = self.session_manager.create_ssh_session(sid, button.label, conn)
            if not session.start():
                self.errors[button.id] = "SSH connection failed"
                self._refresh_shelf()
                return

        self.terminal_window.ensure_tab(sid, button.label)
        self.terminal_window.show()
        self.terminal_window.raise_()
        self._set_status(f"{button.label}: terminal ready, press button to start", "ok")
        self.shelf_view.update_row_state(button.id, is_running=True)

    def stop_button(self, button: ButtonConfig):
        sid = session_name(button.id)
        session = self.session_manager.get_session(sid)
        if session:
            session.interrupt()
            QTimer.singleShot(600, lambda: self.session_manager.stop_session(sid))
            self._set_status(f"{button.label} stopped", "info")
            self.shelf_view.update_row_state(button.id, is_running=False)

    def _on_session_stopped(self, session_id: str):
        # Find which button this session belonged to
        for b in self.config_manager.get_buttons():
            if session_name(b.id) == session_id:
                self.shelf_view.update_row_state(b.id, is_running=False)
                break
        self.terminal_window.remove_tab(session_id)

    def _on_session_error(self, session_id: str, error: str):
        self._set_status(f"Error in {session_id}: {error}", "err")

    def _send_terminal_input(self, session_id: str, data: str):
        session = self.session_manager.get_session(session_id)
        if session:
            session.send(data)

    def _send_terminal_interrupt(self, session_id: str):
        session = self.session_manager.get_session(session_id)
        if session:
            session.interrupt()

    # ---- Editor Navigation ---------------------------------------------------

    def _open_editor(self, button: ButtonConfig):
        self.editor_view.set_button(button, self.config_manager.get_connections())
        self.stack.setCurrentWidget(self.editor_view)

    def _open_add_editor(self):
        self.editor_view.set_button(None, self.config_manager.get_connections())
        self.stack.setCurrentWidget(self.editor_view)

    def _on_editor_saved(self, button: ButtonConfig, new_conn: Optional[SshConnection]):
        if new_conn:
            self.config_manager.save_connection(new_conn)
        self.config_manager.save_button(button)
        self._refresh_shelf()
        self.stack.setCurrentWidget(self.shelf_view)

    def _on_editor_deleted(self, button_id: str):
        # Close running session if any
        sid = session_name(button_id)
        if self.session_manager.is_active(sid):
            self.session_manager.stop_session(sid)

        self.config_manager.delete_button(button_id)
        self._refresh_shelf()
        self.stack.setCurrentWidget(self.shelf_view)

    def closeEvent(self, event):
        self.ping_service.stop()
        self.session_manager.close_all()
        self.terminal_window.close()
        super().closeEvent(event)
