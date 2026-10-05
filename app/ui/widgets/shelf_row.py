"""Launch button shelf row widget with Tesla smoked glass styling."""

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
    TESLA_CARD,
    TESLA_CARD_HOVER,
    TESLA_BORDER,
    TEXT_TITLE,
    TEXT_MUTED,
    TEXT_FAINT,
    HEALTHY,
    CRITICAL,
    TESLA_RED,
    ACCENT_CYAN,
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

        self.setFixedHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        # 1. Main Launch Button (Tesla Smoked Glass)
        self.launch_btn = QPushButton(self)
        self.launch_btn.setCursor(Qt.PointingHandCursor)
        self.launch_btn.clicked.connect(lambda: self.launch_clicked.emit(self.button))

        btn_layout = QHBoxLayout(self.launch_btn)
        btn_layout.setContentsMargins(14, 0, 14, 0)
        btn_layout.setSpacing(10)

        self.play_icon = QLabel(self.launch_btn)
        self.play_icon.setPixmap(get_icon("play", TEXT_TITLE, 11).pixmap(11, 11))
        btn_layout.addWidget(self.play_icon)

        self.label_text = QLabel(self.button.label, self.launch_btn)
        self.label_text.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {TEXT_TITLE};")
        btn_layout.addWidget(self.label_text)

        btn_layout.addStretch()

        # Target badge (Local / SSH)
        self.where_icon = QLabel(self.launch_btn)
        is_local = (self.button.target == TARGET_LOCAL)
        icon_name = "laptop" if is_local else "server"
        where_title = "Runs on this computer" if is_local else f"Runs on {self.button.connection or 'SSH'} over SSH"
        icon_color = TEXT_FAINT if is_local else ACCENT_CYAN
        self.where_icon.setPixmap(get_icon(icon_name, icon_color, 14).pixmap(14, 14))
        self.where_icon.setToolTip(where_title)
        btn_layout.addWidget(self.where_icon)

        layout.addWidget(self.launch_btn, stretch=1)

        # 2. Tools Container
        self.tools_container = QWidget(self)
        tools_layout = QHBoxLayout(self.tools_container)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(3)

        # Failure warning triangle
        self.error_btn = QPushButton(self.tools_container)
        self.error_btn.setFixedSize(26, 26)
        self.error_btn.setIcon(get_icon("triangle-alert", CRITICAL, 15))
        self.error_btn.setStyleSheet("background: transparent; border: none;")
        tools_layout.addWidget(self.error_btn)

        # Running green neon dot
        self.dot_label = QLabel("●", self.tools_container)
        self.dot_label.setStyleSheet(f"color: {HEALTHY}; font-size: 9px; margin: 0 4px;")
        self.dot_label.setToolTip("Running")
        tools_layout.addWidget(self.dot_label)

        # Terminal Arrow
        self.term_btn = QPushButton(self.tools_container)
        self.term_btn.setFixedSize(26, 26)
        self.term_btn.setCursor(Qt.PointingHandCursor)
        self.term_btn.setIcon(get_icon("chevron-right", ACCENT_CYAN if is_running else TEXT_MUTED, 13))
        self.term_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: {RADIUS_BTN}px; }}
            QPushButton:hover {{ background-color: rgba(255, 255, 255, 0.08); }}
        """)
        self.term_btn.setToolTip("Open Terminal Console")
        self.term_btn.clicked.connect(lambda: self.terminal_clicked.emit(self.button))
        tools_layout.addWidget(self.term_btn)

        # Action: Stop (Tesla Red) or Edit (Slate)
        self.action_btn = QPushButton(self.tools_container)
        self.action_btn.setFixedSize(26, 26)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: {RADIUS_BTN}px; }}
            QPushButton:hover {{ background-color: rgba(255, 255, 255, 0.08); }}
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
        preview = preview_line(self.button)
        if self.is_running:
            title = f"Restart in terminal\n{preview}" if self.button.restart else f"Run again in terminal\n{preview}"
        else:
            title = preview

        self.launch_btn.setToolTip(title)
        self.launch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TESLA_CARD};
                border: 1px solid {TESLA_BORDER};
                border-radius: {RADIUS_BTN}px;
                text-align: left;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {TESLA_CARD_HOVER};
                border-color: rgba(255, 255, 255, 0.22);
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
            self.term_btn.setIcon(get_icon("chevron-right", ACCENT_CYAN if self.is_running else TEXT_MUTED, 13))

        # Action button (Stop vs Edit)
        if self.is_running:
            self.action_btn.setIcon(get_icon("square", TESLA_RED, 12))
            self.action_btn.setToolTip("Stop program (Ctrl-C) and terminate session")
        else:
            self.action_btn.setIcon(get_icon("pencil", TEXT_MUTED, 13))
            self.action_btn.setToolTip("Edit button settings")

    def _on_action_clicked(self):
        if self.is_running:
            self.stop_clicked.emit(self.button)
        else:
            self.edit_clicked.emit(self.button)
