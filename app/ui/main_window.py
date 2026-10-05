"""Main application window with Apple frosted glass design and in-app modals."""

import os
import subprocess
from typing import Dict, Optional
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QStackedWidget,
    QLabel,
    QFrame,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from app.config import ConfigManager
from app.models import (
    ButtonConfig,
    CompanionConfig,
    SshConnection,
    TARGET_LOCAL,
    MODE_BACKGROUND,
    session_name,
    companion_session_name,
    terminal_line,
)
from app.network.ping_service import PingService
from app.network.ssh_manager import SshManager
from app.sessions.session_manager import SessionManager
from app.ui.widgets.companion_bar import CompanionBar
from app.ui.widgets.companion_modal import CompanionModalWidget
from app.ui.widgets.modal_overlay import ModalOverlay
from app.ui.views.shelf_view import ShelfView
from app.ui.views.editor_view import EditorView
from app.ui.dialogs.terminal_window import TerminalWindow
from app.ui.styles import (
    MAIN_STYLESHEET,
    FROSTED_BG,
    FROSTED_BORDER,
    SLATE_TITLE,
    SLATE_MUTED,
    HEALTHY,
    CRITICAL,
)


class MainWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Cmdly")
        self.resize(520, 640)
        self.setStyleSheet(MAIN_STYLESHEET)

        self.config_manager = config_manager
        self.session_manager = SessionManager(self)
        self.ping_service = PingService(self)
        self.terminal_windows: Dict[str, TerminalWindow] = {}
        self.errors: Dict[str, str] = {}

        # Root Central Widget
        self.root_widget = QWidget(self)
        self.root_layout = QVBoxLayout(self.root_widget)
        self.root_layout.setContentsMargins(14, 14, 14, 14)
        self.root_layout.setSpacing(8)

        # Main Frosted Card Container
        self.main_container = QFrame(self.root_widget)
        self.main_container.setObjectName("MainContainer")
        self.main_container.setStyleSheet(f"""
            QFrame#MainContainer {{
                background-color: {FROSTED_BG};
                border: 1px solid {FROSTED_BORDER};
                border-radius: 18px;
            }}
        """)

        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)

        # 1. Companion Strip
        self.companion_bar = CompanionBar(self.main_container)
        self.companion_bar.clicked.connect(self._open_companion_modal)
        self.companion_bar.open_terminal_requested.connect(self._open_companion_terminal)
        container_layout.addWidget(self.companion_bar)

        # 2. Status message strip
        self.status_label = QLabel("Ready", self.main_container)
        self.status_label.setStyleSheet(f"font-size: 11.5px; color: {SLATE_MUTED}; padding: 0 4px;")
        container_layout.addWidget(self.status_label)

        # 3. View Stack (ShelfView & EditorView)
        self.stack = QStackedWidget(self.main_container)
        self.shelf_view = ShelfView(self.stack)
        self.editor_view = EditorView(self.config_manager.get_connections(), self.stack)

        self.stack.addWidget(self.shelf_view)
        self.stack.addWidget(self.editor_view)
        container_layout.addWidget(self.stack, stretch=1)

        self.root_layout.addWidget(self.main_container)

        # 4. In-App Modal Overlay for Companion Dialog (Image 2)
        self.modal_overlay = ModalOverlay(self.root_widget)

        self.setCentralWidget(self.root_widget)

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
        self.session_manager.session_output.connect(self._on_session_output)
        self.session_manager.session_stopped.connect(self._on_session_stopped)
        self.session_manager.session_error.connect(self._on_session_error)

    def _refresh_shelf(self):
        buttons = self.config_manager.get_buttons()
        conns = self.config_manager.get_connections()
        active = {sid: True for sid, s in self.session_manager.sessions.items() if s.is_alive()}
        self.shelf_view.set_data(buttons, conns, active, self.errors)

    def _on_ping_state_changed(self, state: str, rtt_ms: Optional[float], error: str):
        self.companion_bar.set_data(self.config_manager.get_companion(), state, rtt_ms, error)

    def _set_status(self, text: str, kind: str = "info"):
        self.status_label.setText(text)
        color = HEALTHY if kind == "ok" else (CRITICAL if kind == "err" else SLATE_MUTED)
        self.status_label.setStyleSheet(f"font-size: 11.5px; color: {color}; padding: 0 4px;")

    # ---- Companion In-App Modal (Image 2) ------------------------------------

    def _open_companion_modal(self):
        modal_content = CompanionModalWidget(
            self.config_manager.get_companion(),
            self.config_manager.get_connections(),
            self.modal_overlay,
        )
        modal_content.saved.connect(self._on_companion_modal_saved)
        modal_content.cleared.connect(self._on_companion_modal_cleared)
        modal_content.close_requested.connect(self.modal_overlay.dismiss)

        self.modal_overlay.show_content(modal_content)

    def _on_companion_modal_saved(self, companion: CompanionConfig, new_conn: Optional[SshConnection]):
        if new_conn:
            self.config_manager.save_connection(new_conn)
        self.config_manager.set_companion(companion)
        self.ping_service.set_companion(companion)
        self._refresh_shelf()
        self.modal_overlay.dismiss()

    def _on_companion_modal_cleared(self):
        self.config_manager.set_companion(None)
        self.ping_service.set_companion(None)
        self._refresh_shelf()
        self.modal_overlay.dismiss()

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

        win = self._ensure_terminal_window(sid, title, comp.host)
        win.set_connected(True)
        win.show()
        win.raise_()

    # ---- Terminal Window Management (Image 1) -------------------------------

    def _ensure_terminal_window(self, session_id: str, title: str, host: str) -> TerminalWindow:
        if session_id in self.terminal_windows:
            win = self.terminal_windows[session_id]
            win.set_info(title, host)
            return win

        win = TerminalWindow(session_id, title, host)
        win.session_input.connect(self._send_terminal_input)
        win.session_interrupt.connect(self._send_terminal_interrupt)
        win.session_close.connect(self.session_manager.stop_session)

        self.terminal_windows[session_id] = win
        return win

    def _on_session_output(self, session_id: str, text: str):
        if session_id in self.terminal_windows:
            self.terminal_windows[session_id].append_output(text)

    def _send_terminal_input(self, session_id: str, data: str):
        session = self.session_manager.get_session(session_id)
        if session:
            session.send(data)

    def _send_terminal_interrupt(self, session_id: str):
        session = self.session_manager.get_session(session_id)
        if session:
            session.interrupt()

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
        host = "this computer" if button.target == TARGET_LOCAL else (button.connection or "ssh")

        if self.session_manager.is_active(sid):
            session = self.session_manager.get_session(sid)
            if button.restart:
                session.interrupt()
                QTimer.singleShot(1000, lambda: session.send(cmd_line + "\n"))
                self._set_status(f"{button.label} restarted", "ok")
            else:
                session.send(cmd_line + "\n")
                self._set_status(f"{button.label} sent again to terminal", "ok")

            self.shelf_view.update_row_state(button.id, is_running=True)
            win = self._ensure_terminal_window(sid, button.label, host)
            win.set_connected(True)
            win.show()
            win.raise_()
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

        win = self._ensure_terminal_window(sid, button.label, host)
        win.set_connected(True)
        win.show()
        win.raise_()

        # Send command after small prompt settling delay
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
                self._set_status("Missing SSH connection", "err")
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
        host = "this computer" if button.target == TARGET_LOCAL else (button.connection or "ssh")

        if self.session_manager.is_active(sid):
            win = self._ensure_terminal_window(sid, button.label, host)
            win.set_connected(True)
            win.show()
            win.raise_()
        else:
            self._connect_shell_only(button)

    def _connect_shell_only(self, button: ButtonConfig):
        sid = session_name(button.id)
        host = "this computer" if button.target == TARGET_LOCAL else (button.connection or "ssh")

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

        win = self._ensure_terminal_window(sid, button.label, host)
        win.set_connected(True)
        win.show()
        win.raise_()
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
        for b in self.config_manager.get_buttons():
            if session_name(b.id) == session_id:
                self.shelf_view.update_row_state(b.id, is_running=False)
                break
        if session_id in self.terminal_windows:
            self.terminal_windows[session_id].set_connected(False)

    def _on_session_error(self, session_id: str, error: str):
        self._set_status(f"Error in {session_id}: {error}", "err")

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
        sid = session_name(button_id)
        if self.session_manager.is_active(sid):
            self.session_manager.stop_session(sid)

        self.config_manager.delete_button(button_id)
        self._refresh_shelf()
        self.stack.setCurrentWidget(self.shelf_view)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.modal_overlay.setGeometry(self.root_widget.rect())

    def closeEvent(self, event):
        self.ping_service.stop()
        self.session_manager.close_all()
        for win in list(self.terminal_windows.values()):
            win.close()
        super().closeEvent(event)
