"""In-app Frosted Companion Computer Modal with Tesla styling."""

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
    timeout_for,
    interval_for,
    validate_host,
    validate_new_connection,
    derived_name,
)
from app.ui.widgets.ticked_slider import TickedSlider
from app.ui.widgets.segmented_control import SegmentedControl
from app.ui.icons import get_icon
from app.ui.styles import (
    TESLA_MODAL,
    TESLA_BORDER,
    TESLA_INPUT,
    TEXT_TITLE,
    TEXT_BODY,
    TEXT_MUTED,
    TEXT_FAINT,
    HAIRLINE,
    ACCENT_CYAN,
    RADIUS_MODAL,
    RADIUS_BTN,
    CRITICAL,
)


class CompanionModalWidget(QFrame):
    saved = Signal(object, object)
    cleared = Signal()
    close_requested = Signal()

    def __init__(
        self,
        current_companion: Optional[CompanionConfig],
        saved_connections: List[SshConnection],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.companion = current_companion
        self.saved_connections = saved_connections

        self.setMinimumWidth(410)
        self.setMaximumWidth(470)

        # Style: Tesla Dark Smoked Glass Modal
        self.setStyleSheet(f"""
            CompanionModalWidget {{
                background-color: {TESLA_MODAL};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: {RADIUS_MODAL}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)

        # 1. Header (Title + Close [x] button)
        header = QWidget(self)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("COMPANION COMPUTER", header)
        title_label.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {TEXT_TITLE}; letter-spacing: 0.8px;")
        h_layout.addWidget(title_label)

        h_layout.addStretch()

        self.close_btn = QPushButton(header)
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setIcon(get_icon("x", TEXT_MUTED, 14))
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.14);
                color: {TEXT_TITLE};
            }}
        """)
        self.close_btn.clicked.connect(self.close_requested.emit)
        h_layout.addWidget(self.close_btn)

        layout.addWidget(header)

        # 2. Segmented Control [Ping | SSH]
        initial_mode = (
            COMPANION_TARGET_SSH
            if (self.companion and self.companion.connection)
            else COMPANION_TARGET_PING
        )
        self.kind_seg = SegmentedControl(COMPANION_TARGETS, initial_mode, self)
        self.kind_seg.value_changed.connect(self._on_mode_changed)
        layout.addWidget(self.kind_seg)

        # 3. Connection / Host Field Section
        self.ssh_section = QWidget(self)
        ss_layout = QVBoxLayout(self.ssh_section)
        ss_layout.setContentsMargins(0, 0, 0, 0)
        ss_layout.setSpacing(6)

        ssh_lbl_row = QWidget(self.ssh_section)
        slr_layout = QHBoxLayout(ssh_lbl_row)
        slr_layout.setContentsMargins(0, 0, 0, 0)
        slr_layout.setSpacing(4)
        sl_title = QLabel("SSH CONNECTION", ssh_lbl_row)
        sl_title.setStyleSheet(f"font-size: 10.5px; font-weight: 800; color: {TEXT_MUTED}; letter-spacing: 1px;")
        slr_layout.addWidget(sl_title)
        sl_info = QLabel(ssh_lbl_row)
        sl_info.setPixmap(get_icon("info", TEXT_FAINT, 13).pixmap(13, 13))
        sl_info.setToolTip("Select a saved connection or add a new one")
        slr_layout.addWidget(sl_info)
        slr_layout.addStretch()
        ss_layout.addWidget(ssh_lbl_row)

        self.conn_combo = QComboBox(self.ssh_section)
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
        ss_layout.addWidget(self.conn_combo)
        layout.addWidget(self.ssh_section)

        # Ping Host Field
        self.ping_section = QWidget(self)
        ps_layout = QVBoxLayout(self.ping_section)
        ps_layout.setContentsMargins(0, 0, 0, 0)
        ps_layout.setSpacing(6)

        ping_lbl_row = QWidget(self.ping_section)
        plr_layout = QHBoxLayout(ping_lbl_row)
        plr_layout.setContentsMargins(0, 0, 0, 0)
        plr_layout.setSpacing(4)
        pl_title = QLabel("IP ADDRESS / HOSTNAME", ping_lbl_row)
        pl_title.setStyleSheet(f"font-size: 10.5px; font-weight: 800; color: {TEXT_MUTED}; letter-spacing: 1px;")
        plr_layout.addWidget(pl_title)
        pl_info = QLabel(ping_lbl_row)
        pl_info.setPixmap(get_icon("info", TEXT_FAINT, 13).pixmap(13, 13))
        plr_layout.addWidget(pl_info)
        plr_layout.addStretch()
        ps_layout.addWidget(ping_lbl_row)

        self.host_input = QLineEdit(self.ping_section)
        self.host_input.setPlaceholderText("192.168.1.99")
        self.host_input.setProperty("mono", "true")
        if self.companion:
            self.host_input.setText(self.companion.host)
        self.host_input.textChanged.connect(self._validate)
        ps_layout.addWidget(self.host_input)
        layout.addWidget(self.ping_section)

        # New Connection Form Box
        self.new_conn_box = QFrame(self)
        self.new_conn_box.setStyleSheet(f"""
            QFrame {{
                background-color: {TESLA_INPUT};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        nc_layout = QVBoxLayout(self.new_conn_box)
        nc_layout.setSpacing(6)

        self.nc_host = QLineEdit(self.new_conn_box)
        self.nc_host.setPlaceholderText("Host (e.g. 192.168.1.99)")
        self.nc_host.setProperty("mono", "true")
        self.nc_host.textChanged.connect(self._validate)
        nc_layout.addWidget(self.nc_host)

        self.nc_name = QLineEdit(self.new_conn_box)
        self.nc_name.setPlaceholderText("Name (optional, user@host)")
        self.nc_name.textChanged.connect(self._validate)
        nc_layout.addWidget(self.nc_name)

        nc_row = QWidget(self.new_conn_box)
        ncr_layout = QHBoxLayout(nc_row)
        ncr_layout.setContentsMargins(0, 0, 0, 0)
        ncr_layout.setSpacing(6)
        self.nc_port = QLineEdit("22", nc_row)
        self.nc_port.setFixedWidth(60)
        self.nc_port.setProperty("mono", "true")
        ncr_layout.addWidget(self.nc_port)
        self.nc_user = QLineEdit(nc_row)
        self.nc_user.setPlaceholderText("User (e.g. root)")
        self.nc_user.textChanged.connect(self._validate)
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

        layout.addWidget(self.new_conn_box)

        # 4. Hairline Divider
        hairline = QFrame(self)
        hairline.setObjectName("Hairline")
        hairline.setFixedHeight(1)
        hairline.setStyleSheet(f"background-color: {HAIRLINE};")
        layout.addWidget(hairline)

        # 5. Slider: PING EVERY
        interval_row = QWidget(self)
        ir_layout = QHBoxLayout(interval_row)
        ir_layout.setContentsMargins(0, 0, 0, 0)
        ir_layout.setSpacing(4)
        ir_title = QLabel("PING INTERVAL", interval_row)
        ir_title.setStyleSheet(f"font-size: 10.5px; font-weight: 800; color: {TEXT_MUTED}; letter-spacing: 1px;")
        ir_layout.addWidget(ir_title)
        ir_info = QLabel(interval_row)
        ir_info.setPixmap(get_icon("info", TEXT_FAINT, 13).pixmap(13, 13))
        ir_layout.addWidget(ir_info)
        ir_layout.addStretch()
        layout.addWidget(interval_row)

        init_interval = self.companion.interval_s if self.companion else DEFAULT_INTERVAL_S
        self.interval_slider = TickedSlider(INTERVAL_STEPS, init_interval, self)
        self.interval_slider.value_changed.connect(self._on_interval_changed)
        layout.addWidget(self.interval_slider)

        # 6. Slider: OFFLINE TIMEOUT
        timeout_row = QWidget(self)
        tr_layout = QHBoxLayout(timeout_row)
        tr_layout.setContentsMargins(0, 0, 0, 0)
        tr_layout.setSpacing(4)
        tr_title = QLabel("OFFLINE TIMEOUT", timeout_row)
        tr_title.setStyleSheet(f"font-size: 10.5px; font-weight: 800; color: {TEXT_MUTED}; letter-spacing: 1px;")
        tr_layout.addWidget(tr_title)
        tr_info = QLabel(timeout_row)
        tr_info.setPixmap(get_icon("info", TEXT_FAINT, 13).pixmap(13, 13))
        tr_layout.addWidget(tr_info)
        tr_layout.addStretch()
        layout.addWidget(timeout_row)

        init_timeout = self.companion.timeout_s if self.companion else DEFAULT_TIMEOUT_S
        self.timeout_slider = TickedSlider(TIMEOUT_STEPS, init_timeout, self)
        self.timeout_slider.value_changed.connect(self._on_timeout_changed)
        layout.addWidget(self.timeout_slider)

        # Error label
        self.error_label = QLabel("", self)
        self.error_label.setStyleSheet(f"font-size: 11px; color: {CRITICAL};")
        layout.addWidget(self.error_label)

        # 7. Action Buttons (Tesla Cyber Styling)
        actions_bar = QWidget(self)
        ab_layout = QHBoxLayout(actions_bar)
        ab_layout.setContentsMargins(0, 6, 0, 0)
        ab_layout.setSpacing(10)

        # SAVE (Tesla Electric Cyan)
        self.save_btn = QPushButton("SAVE CONFIG", actions_bar)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setIcon(get_icon("check", "#080c14", 14))
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_CYAN};
                color: #080c14;
                border: none;
                border-radius: {RADIUS_BTN}px;
                padding: 10px 22px;
                font-weight: 800;
                font-size: 12px;
                letter-spacing: 0.8px;
            }}
            QPushButton:hover {{
                background-color: #7dd3fc;
            }}
            QPushButton:disabled {{
                background-color: rgba(255, 255, 255, 0.08);
                color: {TEXT_FAINT};
            }}
        """)
        self.save_btn.clicked.connect(self._save)
        ab_layout.addWidget(self.save_btn)

        # CLEAR (Smoked pill)
        self.clear_btn = QPushButton("CLEAR", actions_bar)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setIcon(get_icon("eraser", TEXT_TITLE, 14))
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.08);
                color: {TEXT_TITLE};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: {RADIUS_BTN}px;
                padding: 10px 20px;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 0.8px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.15);
            }}
        """)
        self.clear_btn.clicked.connect(self.cleared.emit)
        ab_layout.addWidget(self.clear_btn)

        ab_layout.addStretch()

        # EXIT (Ghost link)
        self.exit_btn = QPushButton("EXIT", actions_bar)
        self.exit_btn.setCursor(Qt.PointingHandCursor)
        self.exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_MUTED};
                border: none;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 0.8px;
                padding: 10px 14px;
            }}
            QPushButton:hover {{
                color: {TEXT_TITLE};
            }}
        """)
        self.exit_btn.clicked.connect(self.close_requested.emit)
        ab_layout.addWidget(self.exit_btn)

        layout.addWidget(actions_bar)

        self._on_mode_changed(initial_mode)
        self._validate()

    def _on_mode_changed(self, mode: str):
        is_ping = (mode == COMPANION_TARGET_PING)
        self.ping_section.setVisible(is_ping)
        self.ssh_section.setVisible(not is_ping)
        self._on_conn_changed()
        self._validate()

    def _on_conn_changed(self):
        is_ssh = (self.kind_seg.get_value() == COMPANION_TARGET_SSH)
        is_new = (self.conn_combo.currentData() == NEW_CONNECTION)
        self.new_conn_box.setVisible(is_ssh and is_new)
        self._validate()

    def _on_interval_changed(self, val: int):
        if self.timeout_slider.value() <= val:
            new_t = timeout_for(val)
            self.timeout_slider.setValue(new_t)

    def _on_timeout_changed(self, val: int):
        if self.interval_slider.value() >= val:
            new_i = interval_for(val)
            self.interval_slider.setValue(new_i)

    def _get_active_host(self) -> str:
        if self.kind_seg.get_value() == COMPANION_TARGET_PING:
            return self.host_input.text().strip()
        if self.conn_combo.currentData() == NEW_CONNECTION:
            return self.nc_host.text().strip()
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

        self.error_label.setText(err if (host and err != "Enter host") else "")
        self.save_btn.setEnabled(not bool(err))

    def _save(self):
        mode = self.kind_seg.get_value()
        interval = self.interval_slider.value()
        timeout = self.timeout_slider.value()

        if mode == COMPANION_TARGET_PING:
            cfg = CompanionConfig(
                name="Companion computer",
                host=self.host_input.text().strip(),
                type=COMPANION_TARGET_PING,
                connection="",
                interval_s=interval,
                timeout_s=timeout,
            )
            self.saved.emit(cfg, None)
        else:
            conn_data = self.conn_combo.currentData()
            new_conn = None
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
                conn_name = new_conn.name
                host = new_conn.host
            else:
                conn_name = conn_data
                c = next((x for x in self.saved_connections if x.name == conn_name), None)
                host = c.host if c else ""

            cfg = CompanionConfig(
                name=conn_name,
                host=host,
                type=COMPANION_TARGET_SSH,
                connection=conn_name,
                interval_s=interval,
                timeout_s=timeout,
            )
            self.saved.emit(cfg, new_conn)
