"""Button configuration editor view with Apple frosted design."""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Signal, Qt
from app.models import (
    ButtonConfig,
    SshConnection,
    TARGETS,
    TARGET_LOCAL,
    TARGET_SSH,
    MODE_TERMINAL,
    MODE_BACKGROUND,
    NEW_CONNECTION,
    preview_line,
    validate_new_connection,
    derived_name,
)
from app.ui.widgets.segmented_control import SegmentedControl
from app.ui.widgets.toggle_switch import ToggleSwitch
from app.ui.icons import get_icon
from app.ui.styles import (
    FROSTED_CARD,
    FROSTED_BORDER,
    FROSTED_INPUT,
    SLATE_TITLE,
    SLATE_TEXT,
    SLATE_MUTED,
    ACCENT_ORANGE,
    CRITICAL,
    RADIUS_BTN,
    RADIUS_CARD,
)


class EditorView(QWidget):
    saved = Signal(object, object)  # (ButtonConfig, Optional[SshConnection])
    deleted = Signal(str)           # (button_id)
    cancelled = Signal()

    def __init__(
        self,
        saved_connections: List[SshConnection],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.saved_connections = saved_connections
        self.button: Optional[ButtonConfig] = None
        self.is_new: bool = True

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 6, 12, 12)
        main_layout.setSpacing(12)

        self.card = QFrame(self)
        self.card.setObjectName("Card")
        self.card.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {FROSTED_CARD};
                border: 1px solid {FROSTED_BORDER};
                border-radius: {RADIUS_CARD}px;
            }}
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(14)

        # 1. Label Input
        lbl_box = QWidget(self.card)
        lb_layout = QVBoxLayout(lbl_box)
        lb_layout.setContentsMargins(0, 0, 0, 0)
        lb_layout.setSpacing(4)
        lb_title = QLabel("Button", lbl_box)
        lb_title.setStyleSheet(f"font-weight: 700; font-size: 12.5px; color: {SLATE_TITLE};")
        lb_layout.addWidget(lb_title)

        self.label_input = QLineEdit(lbl_box)
        self.label_input.setPlaceholderText("Start mission")
        self.label_input.textChanged.connect(self._update_preview)
        lb_layout.addWidget(self.label_input)

        lb_hint = QLabel("What the button says. Leave empty to use the command itself.", lbl_box)
        lb_hint.setStyleSheet(f"font-size: 11px; color: {SLATE_MUTED};")
        lb_layout.addWidget(lb_hint)
        card_layout.addWidget(lbl_box)

        # 2. Target Segment (Local / SSH)
        target_box = QWidget(self.card)
        tb_layout = QVBoxLayout(target_box)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(4)
        tb_title = QLabel("Runs on", target_box)
        tb_title.setStyleSheet(f"font-weight: 700; font-size: 12.5px; color: {SLATE_TITLE};")
        tb_layout.addWidget(tb_title)

        self.target_seg = SegmentedControl(TARGETS, TARGET_LOCAL, target_box)
        self.target_seg.value_changed.connect(self._on_target_changed)
        tb_layout.addWidget(self.target_seg)
        card_layout.addWidget(target_box)

        # 3. SSH Connection Fields Container
        self.ssh_container = QWidget(self.card)
        sc_layout = QVBoxLayout(self.ssh_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(10)

        conn_box = QWidget(self.ssh_container)
        cb_layout = QVBoxLayout(conn_box)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        cb_layout.setSpacing(4)
        cb_title = QLabel("Connection", conn_box)
        cb_title.setStyleSheet(f"font-weight: 700; font-size: 12.5px; color: {SLATE_TITLE};")
        cb_layout.addWidget(cb_title)

        self.conn_combo = QComboBox(conn_box)
        self._populate_connections()
        self.conn_combo.currentIndexChanged.connect(self._on_conn_changed)
        cb_layout.addWidget(self.conn_combo)
        sc_layout.addWidget(conn_box)

        # New Connection Form Box
        self.new_conn_box = QFrame(self.ssh_container)
        self.new_conn_box.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 12px;
                padding: 10px;
            }}
        """)
        nc_layout = QVBoxLayout(self.new_conn_box)
        nc_layout.setSpacing(8)

        self.nc_host = QLineEdit(self.new_conn_box)
        self.nc_host.setPlaceholderText("Host (e.g. 192.168.2.10)")
        self.nc_host.setProperty("mono", "true")
        self.nc_host.textChanged.connect(self._update_preview)
        nc_layout.addWidget(self.nc_host)

        self.nc_name = QLineEdit(self.new_conn_box)
        self.nc_name.setPlaceholderText("Name (optional, user@host)")
        self.nc_name.textChanged.connect(self._update_preview)
        nc_layout.addWidget(self.nc_name)

        nc_row = QWidget(self.new_conn_box)
        ncr_layout = QHBoxLayout(nc_row)
        ncr_layout.setContentsMargins(0, 0, 0, 0)
        ncr_layout.setSpacing(6)

        self.nc_port = QLineEdit("22", nc_row)
        self.nc_port.setFixedWidth(60)
        self.nc_port.setProperty("mono", "true")
        self.nc_port.textChanged.connect(self._update_preview)
        ncr_layout.addWidget(self.nc_port)

        self.nc_user = QLineEdit(nc_row)
        self.nc_user.setPlaceholderText("User (e.g. pilot)")
        self.nc_user.textChanged.connect(self._update_preview)
        ncr_layout.addWidget(self.nc_user)
        nc_layout.addWidget(nc_row)

        self.nc_pass = QLineEdit(self.new_conn_box)
        self.nc_pass.setEchoMode(QLineEdit.Password)
        self.nc_pass.setPlaceholderText("Password (optional)")
        nc_layout.addWidget(self.nc_pass)

        self.nc_key = QLineEdit(self.new_conn_box)
        self.nc_key.setPlaceholderText("Key file (~/.ssh/id_rsa)")
        self.nc_key.setProperty("mono", "true")
        nc_layout.addWidget(self.nc_key)

        sc_layout.addWidget(self.new_conn_box)
        card_layout.addWidget(self.ssh_container)

        # 4. Folder (working directory)
        folder_box = QWidget(self.card)
        fb_layout = QVBoxLayout(folder_box)
        fb_layout.setContentsMargins(0, 0, 0, 0)
        fb_layout.setSpacing(4)
        fb_title = QLabel("Folder", folder_box)
        fb_title.setStyleSheet(f"font-weight: 700; font-size: 12.5px; color: {SLATE_TITLE};")
        fb_layout.addWidget(fb_title)

        self.dir_input = QLineEdit(folder_box)
        self.dir_input.setProperty("mono", "true")
        self.dir_input.textChanged.connect(self._update_preview)
        fb_layout.addWidget(self.dir_input)

        self.dir_hint = QLabel("Entered before the program starts. Leave empty for home folder.", folder_box)
        self.dir_hint.setStyleSheet(f"font-size: 11px; color: {SLATE_MUTED};")
        fb_layout.addWidget(self.dir_hint)
        card_layout.addWidget(folder_box)

        # 5. Program (command)
        cmd_box = QWidget(self.card)
        cb2_layout = QVBoxLayout(cmd_box)
        cb2_layout.setContentsMargins(0, 0, 0, 0)
        cb2_layout.setSpacing(4)
        cb2_title = QLabel("Program", cmd_box)
        cb2_title.setStyleSheet(f"font-weight: 700; font-size: 12.5px; color: {SLATE_TITLE};")
        cb2_layout.addWidget(cb2_title)

        self.cmd_input = QLineEdit(cmd_box)
        self.cmd_input.setPlaceholderText("./start.sh")
        self.cmd_input.setProperty("mono", "true")
        self.cmd_input.textChanged.connect(self._update_preview)
        cb2_layout.addWidget(self.cmd_input)
        card_layout.addWidget(cmd_box)

        # 6. Toggles: Terminal & Restart
        switches_box = QWidget(self.card)
        sb_layout = QVBoxLayout(switches_box)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(8)

        # Run in terminal switch
        term_row = QWidget(switches_box)
        tr_layout = QHBoxLayout(term_row)
        tr_layout.setContentsMargins(0, 0, 0, 0)
        tr_lbl = QLabel("Run in a terminal", term_row)
        tr_lbl.setStyleSheet(f"font-weight: 600; font-size: 12.5px; color: {SLATE_TITLE};")
        tr_layout.addWidget(tr_lbl)
        tr_layout.addStretch()
        self.terminal_switch = ToggleSwitch(True, term_row)
        self.terminal_switch.toggled.connect(self._on_terminal_toggled)
        tr_layout.addWidget(self.terminal_switch)
        sb_layout.addWidget(term_row)

        # Restart switch
        self.restart_row = QWidget(switches_box)
        rr_layout = QHBoxLayout(self.restart_row)
        rr_layout.setContentsMargins(0, 0, 0, 0)
        rr_lbl = QLabel("Restart on press", self.restart_row)
        rr_lbl.setStyleSheet(f"font-weight: 600; font-size: 12.5px; color: {SLATE_TITLE};")
        rr_layout.addWidget(rr_lbl)
        rr_layout.addStretch()
        self.restart_switch = ToggleSwitch(False, self.restart_row)
        rr_layout.addWidget(self.restart_switch)
        sb_layout.addWidget(self.restart_row)

        card_layout.addWidget(switches_box)

        # 7. Preview Box
        self.preview_box = QFrame(self.card)
        self.preview_box.setStyleSheet(f"""
            QFrame {{
                background-color: {FROSTED_INPUT};
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: {RADIUS_BTN}px;
                padding: 10px;
            }}
        """)
        pb_layout = QVBoxLayout(self.preview_box)
        pb_layout.setContentsMargins(6, 6, 6, 6)
        self.preview_text = QLabel("Name a program to see the command.", self.preview_box)
        self.preview_text.setWordWrap(True)
        self.preview_text.setStyleSheet(f'font-family: "SF Mono", Menlo, Monaco, monospace; font-size: 12px; color: {SLATE_TEXT};')
        pb_layout.addWidget(self.preview_text)
        card_layout.addWidget(self.preview_box)

        # Error notification line
        self.error_label = QLabel("", self.card)
        self.error_label.setStyleSheet(f"color: {CRITICAL}; font-size: 11px;")
        card_layout.addWidget(self.error_label)

        # 8. Action Buttons (Save, Delete, Cancel)
        actions_bar = QWidget(self.card)
        ab_layout = QHBoxLayout(actions_bar)
        ab_layout.setContentsMargins(0, 8, 0, 0)
        ab_layout.setSpacing(10)

        self.save_btn = QPushButton("Save", actions_bar)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setIcon(get_icon("check", "#ffffff", 14))
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_ORANGE};
                color: #ffffff;
                border: none;
                border-radius: {RADIUS_BTN}px;
                padding: 10px 22px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #f97316; }}
            QPushButton:disabled {{ background-color: rgba(203, 213, 225, 0.6); color: {SLATE_MUTED}; }}
        """)
        self.save_btn.clicked.connect(self._handle_save)
        ab_layout.addWidget(self.save_btn)

        self.delete_btn = QPushButton("Delete", actions_bar)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setIcon(get_icon("trash-2", CRITICAL, 14))
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CRITICAL};
                border: 1px solid {CRITICAL};
                border-radius: {RADIUS_BTN}px;
                padding: 9px 16px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {CRITICAL}; color: #ffffff; }}
        """)
        self.delete_btn.clicked.connect(self._handle_delete)
        ab_layout.addWidget(self.delete_btn)

        ab_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel", actions_bar)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {SLATE_MUTED};
                border: none;
                padding: 10px 14px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{ color: {SLATE_TITLE}; }}
        """)
        self.cancel_btn.clicked.connect(self.cancelled.emit)
        ab_layout.addWidget(self.cancel_btn)

        card_layout.addWidget(actions_bar)
        main_layout.addWidget(self.card)

    def set_button(self, button: Optional[ButtonConfig], connections: List[SshConnection]):
        self.saved_connections = connections
        self._populate_connections()
        self.button = button
        self.is_new = (button is None)

        if self.is_new:
            self.label_input.clear()
            self.target_seg.set_value(TARGET_LOCAL)
            self.dir_input.clear()
            self.cmd_input.clear()
            self.terminal_switch.setChecked(True)
            self.restart_switch.setChecked(False)
            self.delete_btn.hide()
        else:
            self.label_input.setText(button.label)
            self.target_seg.set_value(button.target)
            self.dir_input.setText(button.directory)
            self.cmd_input.setText(button.command)
            self.terminal_switch.setChecked(button.mode == MODE_TERMINAL)
            self.restart_switch.setChecked(button.restart)

            idx = self.conn_combo.findData(button.connection)
            if idx >= 0:
                self.conn_combo.setCurrentIndex(idx)
            self.delete_btn.show()

        self._on_target_changed(self.target_seg.get_value())
        self._update_preview()

    def _populate_connections(self):
        self.conn_combo.clear()
        for c in self.saved_connections:
            addr = f"{c.username}@{c.host}" if c.username else c.host
            lbl = f"{c.name} ({addr})" if addr and addr != c.name else c.name
            self.conn_combo.addItem(lbl, c.name)
        self.conn_combo.addItem("New connection…", NEW_CONNECTION)

    def _on_target_changed(self, target: str):
        is_ssh = (target == TARGET_SSH)
        self.ssh_container.setVisible(is_ssh)
        self.dir_input.setPlaceholderText("/home/pilot/mission" if is_ssh else "~/mission")
        self._on_conn_changed()
        self._update_preview()

    def _on_conn_changed(self):
        is_ssh = (self.target_seg.get_value() == TARGET_SSH)
        is_new = (self.conn_combo.currentData() == NEW_CONNECTION)
        self.new_conn_box.setVisible(is_ssh and is_new)
        self._update_preview()

    def _on_terminal_toggled(self, checked: bool):
        self.restart_row.setVisible(checked)
        self._update_preview()

    def _get_target_connection_name(self) -> str:
        if self.target_seg.get_value() != TARGET_SSH:
            return ""
        if self.conn_combo.currentData() == NEW_CONNECTION:
            return self.nc_name.text().strip() or derived_name(
                SshConnection(host=self.nc_host.text().strip(), username=self.nc_user.text().strip())
            )
        return self.conn_combo.currentData() or ""

    def _update_preview(self):
        dummy_btn = ButtonConfig(
            label=self.label_input.text().strip(),
            target=self.target_seg.get_value(),
            connection=self._get_target_connection_name(),
            directory=self.dir_input.text().strip(),
            command=self.cmd_input.text().strip(),
            mode=MODE_TERMINAL if self.terminal_switch.isChecked() else MODE_BACKGROUND,
            restart=self.restart_switch.isChecked(),
        )

        preview = preview_line(dummy_btn)
        self.preview_text.setText(preview or "Name a program to see the command.")

        # Validation
        err = ""
        if not dummy_btn.command:
            err = "Command cannot be empty."
        elif dummy_btn.target == TARGET_SSH:
            if self.conn_combo.currentData() == NEW_CONNECTION:
                try:
                    port = int(self.nc_port.text().strip() or "22")
                except ValueError:
                    port = -1
                new_c = SshConnection(
                    name=self.nc_name.text().strip(),
                    host=self.nc_host.text().strip(),
                    port=port,
                    username=self.nc_user.text().strip(),
                )
                err = validate_new_connection(new_c, [c.name for c in self.saved_connections])
            elif not dummy_btn.connection:
                err = "Pick an SSH connection."

        self.error_label.setText(err if dummy_btn.command else "")
        self.save_btn.setEnabled(bool(dummy_btn.command and not err))

    def _handle_save(self):
        new_conn = None
        target = self.target_seg.get_value()
        conn_name = ""

        if target == TARGET_SSH:
            if self.conn_combo.currentData() == NEW_CONNECTION:
                try:
                    port = int(self.nc_port.text().strip() or "22")
                except ValueError:
                    port = 22
                new_conn = SshConnection(
                    name=self.nc_name.text().strip() or derived_name(
                        SshConnection(host=self.nc_host.text().strip(), username=self.nc_user.text().strip())
                    ),
                    host=self.nc_host.text().strip(),
                    port=port,
                    username=self.nc_user.text().strip(),
                    password=self.nc_pass.text(),
                    key_path=self.nc_key.text().strip(),
                )
                conn_name = new_conn.name
            else:
                conn_name = self.conn_combo.currentData()

        btn_id = self.button.id if (self.button and not self.is_new) else ""
        saved_btn = ButtonConfig(
            id=btn_id or ("b" + ButtonConfig().id[1:]),
            label=self.label_input.text().strip() or self.cmd_input.text().strip(),
            target=target,
            connection=conn_name,
            directory=self.dir_input.text().strip(),
            command=self.cmd_input.text().strip(),
            mode=MODE_TERMINAL if self.terminal_switch.isChecked() else MODE_BACKGROUND,
            restart=self.restart_switch.isChecked(),
        )

        self.saved.emit(saved_btn, new_conn)

    def _handle_delete(self):
        if self.button and not self.is_new:
            self.deleted.emit(self.button.id)
