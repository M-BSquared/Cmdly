"""Companion computer configuration dialog matching Schwalby popup."""

from typing import Optional, List
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QSlider,
    QPushButton,
    QWidget,
    QFrame,
)
from PySide6.QtCore import Qt
from app.models import (
    CompanionConfig,
    SshConnection,
    COMPANION_TARGETS,
    COMPANION_TARGET_PING,
    COMPANION_TARGET_SSH,
    NEW_CONNECTION,
    INTERVAL_STEPS,
    TIMEOUT_STEPS,
    DEFAULT_INTERVAL_S,
    DEFAULT_TIMEOUT_S,
    nearest_step,
    timeout_for,
    interval_for,
    validate_host,
    validate_new_connection,
    derived_name,
)
from app.ui.widgets.segmented_control import SegmentedControl
from app.ui.styles import (
    SURFACE_CARD,
    PANEL_FILL,
    BORDER_SOFT,
    TEXT_1,
    TEXT_2,
    TEXT_3,
    CRITICAL,
    RADIUS_BTN,
    RADIUS_CARD,
)


class CompanionDialog(QDialog):
    def __init__(
        self,
        current_companion: Optional[CompanionConfig],
        saved_connections: List[SshConnection],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Companion computer")
        self.setMinimumWidth(440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.companion = current_companion
        self.saved_connections = saved_connections
        self.result_companion: Optional[CompanionConfig] = None
        self.new_saved_connection: Optional[SshConnection] = None

        initial_mode = (
            COMPANION_TARGET_SSH
            if (self.companion and self.companion.connection)
            else COMPANION_TARGET_PING
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Kind Segment (Ping / SSH)
        self.kind_seg = SegmentedControl(COMPANION_TARGETS, initial_mode, self)
        self.kind_seg.value_changed.connect(self._on_mode_changed)
        layout.addWidget(self.kind_seg)

        # 2. Name Field
        self.name_field = QWidget(self)
        nf_layout = QVBoxLayout(self.name_field)
        nf_layout.setContentsMargins(0, 0, 0, 0)
        nf_layout.setSpacing(4)
        nf_label = QLabel("Name", self.name_field)
        nf_label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {TEXT_1};")
        nf_layout.addWidget(nf_label)

        self.name_input = QLineEdit(self.name_field)
        self.name_input.setPlaceholderText("Companion computer")
        if self.companion:
            self.name_input.setText(self.companion.name)
        nf_layout.addWidget(self.name_input)

        nf_hint = QLabel("Optional. Shown at the top of Cmdly.", self.name_field)
        nf_hint.setStyleSheet(f"font-size: 11px; color: {TEXT_3};")
        nf_layout.addWidget(nf_hint)
        layout.addWidget(self.name_field)

        # 3. Host Field (for Ping mode)
        self.host_field = QWidget(self)
        hf_layout = QVBoxLayout(self.host_field)
        hf_layout.setContentsMargins(0, 0, 0, 0)
        hf_layout.setSpacing(4)
        hf_label = QLabel("IP address", self.host_field)
        hf_label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {TEXT_1};")
        hf_layout.addWidget(hf_label)

        self.host_input = QLineEdit(self.host_field)
        self.host_input.setPlaceholderText("192.168.2.10")
        self.host_input.setProperty("mono", "true")
        if self.companion:
            self.host_input.setText(self.companion.host)
        self.host_input.textChanged.connect(self._validate)
        hf_layout.addWidget(self.host_input)

        self.host_error_label = QLabel("", self.host_field)
        self.host_error_label.setStyleSheet(f"font-size: 11px; color: {CRITICAL};")
        hf_layout.addWidget(self.host_error_label)
        layout.addWidget(self.host_field)

        # 4. SSH Connection Field (for SSH mode)
        self.ssh_field = QWidget(self)
        sf_layout = QVBoxLayout(self.ssh_field)
        sf_layout.setContentsMargins(0, 0, 0, 0)
        sf_layout.setSpacing(4)

        sf_label = QLabel("SSH connection", self.ssh_field)
        sf_label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {TEXT_1};")
        sf_layout.addWidget(sf_label)

        self.conn_combo = QComboBox(self.ssh_field)
        for c in self.saved_connections:
            addr = f"{c.username}@{c.host}" if c.username else c.host
            lbl = f"{c.name} ({addr})" if addr and addr != c.name else c.name
            self.conn_combo.addItem(lbl, c.name)
        self.conn_combo.addItem("New connection…", NEW_CONNECTION)

        if self.companion and self.companion.connection:
            idx = self.conn_combo.findData(self.companion.connection)
            if idx >= 0:
                self.conn_combo.setCurrentIndex(idx)
        self.conn_combo.currentIndexChanged.connect(self._on_conn_changed)
        sf_layout.addWidget(self.conn_combo)

        layout.addWidget(self.ssh_field)

        # 5. Ad-hoc New Connection Box (hidden by default)
        self.new_conn_box = QFrame(self)
        self.new_conn_box.setStyleSheet(f"""
            QFrame {{
                background-color: {PANEL_FILL};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_CARD}px;
                padding: 10px;
            }}
        """)
        nc_layout = QVBoxLayout(self.new_conn_box)
        nc_layout.setSpacing(8)

        self.nc_host = QLineEdit(self.new_conn_box)
        self.nc_host.setPlaceholderText("Host (e.g. 192.168.2.10)")
        self.nc_host.setProperty("mono", "true")
        self.nc_host.textChanged.connect(self._validate)
        nc_layout.addWidget(self.nc_host)

        self.nc_name = QLineEdit(self.new_conn_box)
        self.nc_name.setPlaceholderText("Name (optional, defaults to user@host)")
        self.nc_name.textChanged.connect(self._validate)
        nc_layout.addWidget(self.nc_name)

        port_user_box = QWidget(self.new_conn_box)
        pu_layout = QHBoxLayout(port_user_box)
        pu_layout.setContentsMargins(0, 0, 0, 0)
        pu_layout.setSpacing(6)

        self.nc_port = QLineEdit("22", port_user_box)
        self.nc_port.setFixedWidth(70)
        self.nc_port.setProperty("mono", "true")
        self.nc_port.textChanged.connect(self._validate)
        pu_layout.addWidget(self.nc_port)

        self.nc_user = QLineEdit(port_user_box)
        self.nc_user.setPlaceholderText("User (e.g. pilot)")
        self.nc_user.textChanged.connect(self._validate)
        pu_layout.addWidget(self.nc_user)
        nc_layout.addWidget(port_user_box)

        self.nc_pass = QLineEdit(self.new_conn_box)
        self.nc_pass.setEchoMode(QLineEdit.Password)
        self.nc_pass.setPlaceholderText("Password (optional)")
        nc_layout.addWidget(self.nc_pass)

        self.nc_key = QLineEdit(self.new_conn_box)
        self.nc_key.setPlaceholderText("Key file (e.g. ~/.ssh/id_rsa)")
        self.nc_key.setProperty("mono", "true")
        nc_layout.addWidget(self.nc_key)

        layout.addWidget(self.new_conn_box)

        # 6. Ping Interval Slider
        self.interval_val = self.companion.interval_s if self.companion else DEFAULT_INTERVAL_S
        self.interval_label = QLabel(f"Ping every: {self.interval_val} s", self)
        self.interval_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_1};")
        layout.addWidget(self.interval_label)

        self.interval_slider = QSlider(Qt.Horizontal, self)
        self.interval_slider.setRange(0, len(INTERVAL_STEPS) - 1)
        self.interval_slider.setValue(INTERVAL_STEPS.index(self.interval_val) if self.interval_val in INTERVAL_STEPS else 1)
        self.interval_slider.valueChanged.connect(self._on_interval_slider)
        layout.addWidget(self.interval_slider)

        # 7. Offline Timeout Slider
        self.timeout_val = self.companion.timeout_s if self.companion else DEFAULT_TIMEOUT_S
        self.timeout_label = QLabel(f"Offline after: {self.timeout_val} s", self)
        self.timeout_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_1};")
        layout.addWidget(self.timeout_label)

        self.timeout_slider = QSlider(Qt.Horizontal, self)
        self.timeout_slider.setRange(0, len(TIMEOUT_STEPS) - 1)
        self.timeout_slider.setValue(TIMEOUT_STEPS.index(self.timeout_val) if self.timeout_val in TIMEOUT_STEPS else 2)
        self.timeout_slider.valueChanged.connect(self._on_timeout_slider)
        layout.addWidget(self.timeout_slider)

        # Error / Status note
        self.dialog_status = QLabel("", self)
        self.dialog_status.setStyleSheet(f"font-size: 12px; color: {CRITICAL};")
        layout.addWidget(self.dialog_status)

        # 8. Buttons (Save, Clear, Exit)
        btn_bar = QWidget(self)
        bb_layout = QHBoxLayout(btn_bar)
        bb_layout.setContentsMargins(0, 8, 0, 0)
        bb_layout.setSpacing(8)

        self.save_btn = QPushButton("Save", btn_bar)
        self.save_btn.setProperty("class", "PrimaryBtn")
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: {RADIUS_BTN}px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #60a5fa; }}
            QPushButton:disabled {{ background-color: {BORDER_SOFT}; color: {TEXT_3}; }}
        """)
        self.save_btn.clicked.connect(self._save)
        bb_layout.addWidget(self.save_btn)

        self.clear_btn = QPushButton("Clear", btn_bar)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_CARD};
                color: {TEXT_1};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                padding: 8px 14px;
            }}
            QPushButton:hover {{ background-color: {PANEL_FILL}; }}
        """)
        self.clear_btn.clicked.connect(self._clear)
        bb_layout.addWidget(self.clear_btn)

        bb_layout.addStretch()

        self.exit_btn = QPushButton("Exit", btn_bar)
        self.exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_2};
                border: none;
                padding: 8px 14px;
            }}
            QPushButton:hover {{ color: {TEXT_1}; }}
        """)
        self.exit_btn.clicked.connect(self.reject)
        bb_layout.addWidget(self.exit_btn)

        layout.addWidget(btn_bar)

        self._on_mode_changed(initial_mode)
        self._validate()

    def _on_mode_changed(self, mode: str):
        is_ping = (mode == COMPANION_TARGET_PING)
        self.name_field.setVisible(is_ping)
        self.host_field.setVisible(is_ping)
        self.ssh_field.setVisible(not is_ping)
        self._on_conn_changed()
        self._validate()

    def _on_conn_changed(self):
        is_ssh = (self.kind_seg.get_value() == COMPANION_TARGET_SSH)
        is_new = (self.conn_combo.currentData() == NEW_CONNECTION)
        self.new_conn_box.setVisible(is_ssh and is_new)
        self._validate()

    def _on_interval_slider(self, idx: int):
        self.interval_val = INTERVAL_STEPS[idx]
        self.interval_label.setText(f"Ping every: {self.interval_val} s")
        if self.timeout_val <= self.interval_val:
            self.timeout_val = timeout_for(self.interval_val)
            self.timeout_slider.setValue(TIMEOUT_STEPS.index(self.timeout_val))
            self.timeout_label.setText(f"Offline after: {self.timeout_val} s")

    def _on_timeout_slider(self, idx: int):
        self.timeout_val = TIMEOUT_STEPS[idx]
        self.timeout_label.setText(f"Offline after: {self.timeout_val} s")
        if self.interval_val >= self.timeout_val:
            self.interval_val = interval_for(self.timeout_val)
            self.interval_slider.setValue(INTERVAL_STEPS.index(self.interval_val))
            self.interval_label.setText(f"Ping every: {self.interval_val} s")

    def _get_active_host(self) -> str:
        if self.kind_seg.get_value() == COMPANION_TARGET_PING:
            return self.host_input.text().strip()
        if self.conn_combo.currentData() == NEW_CONNECTION:
            return self.nc_host.text().strip()
        # Saved connection
        conn_name = self.conn_combo.currentData()
        c = next((x for x in self.saved_connections if x.name == conn_name), None)
        return c.host if c else ""

    def _validate(self):
        host = self._get_active_host()
        err = validate_host(host) if host else "Enter host"

        if self.kind_seg.get_value() == COMPANION_TARGET_SSH and self.conn_combo.currentData() == NEW_CONNECTION:
            try:
                port = int(self.nc_port.text().strip() or "22")
            except ValueError:
                port = -1
            dummy = SshConnection(
                name=self.nc_name.text().strip(),
                host=self.nc_host.text().strip(),
                port=port,
                username=self.nc_user.text().strip(),
            )
            err = validate_new_connection(dummy, [c.name for c in self.saved_connections]) or err

        self.host_error_label.setText(err if (host and err != "Enter host") else "")
        self.save_btn.setEnabled(not bool(err))

    def _save(self):
        mode = self.kind_seg.get_value()
        if mode == COMPANION_TARGET_PING:
            self.result_companion = CompanionConfig(
                name=self.name_input.text().strip(),
                host=self.host_input.text().strip(),
                type=COMPANION_TARGET_PING,
                connection="",
                interval_s=self.interval_val,
                timeout_s=self.timeout_val,
            )
        else:
            conn_data = self.conn_combo.currentData()
            if conn_data == NEW_CONNECTION:
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
                self.new_saved_connection = new_conn
                conn_name = new_conn.name
                host_to_ping = new_conn.host
            else:
                conn_name = conn_data
                c = next((x for x in self.saved_connections if x.name == conn_name), None)
                host_to_ping = c.host if c else ""

            self.result_companion = CompanionConfig(
                name=conn_name,
                host=host_to_ping,
                type=COMPANION_TARGET_SSH,
                connection=conn_name,
                interval_s=self.interval_val,
                timeout_s=self.timeout_val,
            )

        self.accept()

    def _clear(self):
        self.result_companion = None
        self.accept()
