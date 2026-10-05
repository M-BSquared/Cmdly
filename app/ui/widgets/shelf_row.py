"""Launch button shelf row widget matching .schw-row."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Signal, Qt
from app.models import (
    ButtonConfig,
    TARGET_LOCAL,
    MODE_BACKGROUND,
    preview_line,
)
from app.ui.icons import get_icon
from app.ui.styles import (
    SURFACE_HOVER,
    SURFACE_ACTIVE,
    BORDER_SOFT,
    TEXT_1,
    TEXT_3,
    HEALTHY,
    CRITICAL,
    RADIUS_BTN,
)


class ShelfRow(QWidget):
    launch_clicked = Signal(object)
    terminal_clicked = Signal(object)
    stop_clicked = Signal(object)
    edit_clicked = Signal(object)

    def __init__(
        self,
        button: ButtonConfig,
        is_running: bool = False,
        error_msg: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.button = button
        self.is_running = is_running
        self.error_msg = error_msg

        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(6)

        # 1. Main Launch Button
        self.launch_btn = QPushButton(self)
        self.launch_btn.setCursor(Qt.PointingHandCursor)
        self.launch_btn.clicked.connect(lambda: self.launch_clicked.emit(self.button))

        btn_layout = QHBoxLayout(self.launch_btn)
        btn_layout.setContentsMargins(10, 0, 10, 0)
        btn_layout.setSpacing(8)

        self.play_icon = QLabel(self.launch_btn)
        self.play_icon.setPixmap(get_icon("play", TEXT_1, 12).pixmap(12, 12))
        btn_layout.addWidget(self.play_icon)

        self.label_text = QLabel(self.button.label, self.launch_btn)
        self.label_text.setStyleSheet(f"font-weight: 500; font-size: 13px; color: {TEXT_1};")
        btn_layout.addWidget(self.label_text)

        btn_layout.addStretch()

        # Where icon (Local / SSH)
        self.where_icon = QLabel(self.launch_btn)
        is_local = (self.button.target == TARGET_LOCAL)
        icon_name = "laptop" if is_local else "server"
        where_title = "Runs on this computer" if is_local else f"Runs on {self.button.connection or 'SSH'} over SSH"
        self.where_icon.setPixmap(get_icon(icon_name, TEXT_3, 14).pixmap(14, 14))
        self.where_icon.setToolTip(where_title)
        btn_layout.addWidget(self.where_icon)

        layout.addWidget(self.launch_btn, stretch=1)

        # 2. Tools Container
        self.tools_container = QWidget(self)
        tools_layout = QHBoxLayout(self.tools_container)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(2)

        # Failure warning triangle
        self.error_btn = QPushButton(self.tools_container)
        self.error_btn.setFixedSize(26, 26)
        self.error_btn.setIcon(get_icon("triangle-alert", CRITICAL, 15))
        self.error_btn.setStyleSheet("background: transparent; border: none;")
        tools_layout.addWidget(self.error_btn)

        # Running green dot
        self.dot_label = QLabel("●", self.tools_container)
        self.dot_label.setStyleSheet(f"color: {HEALTHY}; font-size: 10px; margin: 0 4px;")
        self.dot_label.setToolTip("Running")
        tools_layout.addWidget(self.dot_label)

        # Terminal Arrow
        self.term_btn = QPushButton(self.tools_container)
        self.term_btn.setFixedSize(26, 26)
        self.term_btn.setCursor(Qt.PointingHandCursor)
        self.term_btn.setIcon(get_icon("chevron-right", HEALTHY if is_running else TEXT_3, 14))
        self.term_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: {RADIUS_BTN}px; }}
            QPushButton:hover {{ background-color: {SURFACE_HOVER}; }}
        """)
        self.term_btn.setToolTip("Open terminal window")
        self.term_btn.clicked.connect(lambda: self.terminal_clicked.emit(self.button))
        tools_layout.addWidget(self.term_btn)

        # Action: Stop (when running) or Pencil Edit (when not running)
        self.action_btn = QPushButton(self.tools_container)
        self.action_btn.setFixedSize(26, 26)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: {RADIUS_BTN}px; }}
            QPushButton:hover {{ background-color: {SURFACE_HOVER}; }}
        """)
        self.action_btn.clicked.connect(self._on_action_clicked)
        tools_layout.addWidget(self.action_btn)

        layout.addWidget(self.tools_container)

        self._apply_state()

    def update_state(self, is_running: bool, error_msg: str = ""):
        self.is_running = is_running
        self.error_msg = error_msg
        self._apply_state()

    def _apply_state(self):
        # Update launch button style and tooltip
        preview = preview_line(self.button)
        if self.is_running:
            title = f"Restart in terminal\n{preview}" if self.button.restart else f"Run again in terminal\n{preview}"
        else:
            title = preview

        self.launch_btn.setToolTip(title)
        self.launch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_HOVER};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                text-align: left;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {SURFACE_ACTIVE};
            }}
        """)

        # Error visibility
        self.error_btn.setVisible(bool(self.error_msg))
        if self.error_msg:
            self.error_btn.setToolTip(f"{self.button.label}: {self.error_msg}")

        # Live dot visibility
        self.dot_label.setVisible(self.is_running)

        # Terminal button
        is_bg = (self.button.mode == MODE_BACKGROUND)
        self.term_btn.setVisible(not is_bg)
        if not is_bg:
            self.term_btn.setIcon(get_icon("chevron-right", HEALTHY if self.is_running else TEXT_3, 14))

        # Action button (Stop vs Edit)
        if self.is_running:
            self.action_btn.setIcon(get_icon("square", CRITICAL, 13))
            self.action_btn.setToolTip("Stop program (Ctrl-C) and close session")
        else:
            self.action_btn.setIcon(get_icon("pencil", TEXT_3, 13))
            self.action_btn.setToolTip("Edit button settings")

    def _on_action_clicked(self):
        if self.is_running:
            self.stop_clicked.emit(self.button)
        else:
            self.edit_clicked.emit(self.button)
