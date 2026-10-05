"""Launch button shelf row widget with frosted glass styling and Apple SF Pro typography."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
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
    theme_manager,
    RADIUS_BTN,
    FONT_FAMILY,
    MONO_FONT,
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

        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        # 1. Main Frosted Launch Button
        self.launch_btn = QPushButton(self)
        self.launch_btn.setCursor(Qt.PointingHandCursor)
        self.launch_btn.clicked.connect(lambda: self.launch_clicked.emit(self.button))

        btn_layout = QHBoxLayout(self.launch_btn)
        btn_layout.setContentsMargins(12, 6, 12, 6)
        btn_layout.setSpacing(10)

        # Play / Status Circle Badge
        self.badge = QLabel(self.launch_btn)
        self.badge.setFixedSize(26, 26)
        self.badge.setAlignment(Qt.AlignCenter)
        btn_layout.addWidget(self.badge)

        # Title Label
        self.label_text = QLabel(self.button.label, self.launch_btn)
        self.label_text.setStyleSheet(
            f'font-weight: 600; font-size: 13px; font-family: {FONT_FAMILY};'
        )
        btn_layout.addWidget(self.label_text)

        btn_layout.addStretch()

        # Target badge (Local / SSH tag)
        self.tag_container = QFrame(self.launch_btn)
        tc_layout = QHBoxLayout(self.tag_container)
        tc_layout.setContentsMargins(6, 2, 8, 2)
        tc_layout.setSpacing(5)

        self.where_icon = QLabel(self.tag_container)
        self.where_icon.setFixedSize(14, 14)
        tc_layout.addWidget(self.where_icon)

        self.where_text = QLabel(self.tag_container)
        self.where_text.setStyleSheet(
            f'font-size: 11px; font-weight: 500; font-family: {FONT_FAMILY};'
        )
        tc_layout.addWidget(self.where_text)

        btn_layout.addWidget(self.tag_container)
        layout.addWidget(self.launch_btn, stretch=1)

        # 2. Tools Container on the right
        self.tools_container = QWidget(self)
        tools_layout = QHBoxLayout(self.tools_container)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(4)

        # Failure warning triangle
        self.error_btn = QPushButton(self.tools_container)
        self.error_btn.setFixedSize(28, 28)
        self.error_btn.setStyleSheet("background: transparent; border: none;")
        tools_layout.addWidget(self.error_btn)

        # Live Running dot
        self.dot_label = QLabel("●", self.tools_container)
        self.dot_label.setStyleSheet("font-size: 9px; margin: 0 4px;")
        self.dot_label.setToolTip("Running")
        tools_layout.addWidget(self.dot_label)

        # Terminal Arrow Button
        self.term_btn = QPushButton(self.tools_container)
        self.term_btn.setFixedSize(28, 28)
        self.term_btn.setCursor(Qt.PointingHandCursor)
        self.term_btn.setToolTip("Open Terminal Console")
        self.term_btn.clicked.connect(lambda: self.terminal_clicked.emit(self.button))
        tools_layout.addWidget(self.term_btn)

        # Action: Stop (■) or Edit (✏) Button
        self.action_btn = QPushButton(self.tools_container)
        self.action_btn.setFixedSize(28, 28)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self._on_action_clicked)
        tools_layout.addWidget(self.action_btn)

        layout.addWidget(self.tools_container)

        self._apply_state()

    def update_state(self, is_running: bool, error_msg: str = ""):
        self.is_running = is_running
        self.error_msg = error_msg
        self._apply_state()

    def _apply_state(self):
        t = theme_manager.current_theme
        preview = preview_line(self.button)
        if self.is_running:
            title = f"Restart in terminal\n{preview}" if self.button.restart else f"Run again in terminal\n{preview}"
        else:
            title = preview

        self.launch_btn.setToolTip(title)

        # Play / Status badge
        is_local = (self.button.target == TARGET_LOCAL)
        badge_bg = "rgba(16, 185, 129, 0.16)" if self.is_running else "rgba(255, 255, 255, 0.08)"
        self.badge.setStyleSheet(f"""
            QLabel {{
                background-color: {badge_bg};
                border-radius: 13px;
                border: 1px solid rgba(255, 255, 255, 0.10);
            }}
        """)
        play_color = t["healthy"] if self.is_running else t["text_title"]
        self.badge.setPixmap(get_icon("play", play_color, 12).pixmap(12, 12))

        # Launch Button Styling
        bg_col = "rgba(255, 255, 255, 0.06)"
        hover_col = "rgba(255, 255, 255, 0.12)"
        border_col = t["border"]
        self.launch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 10px;
                text-align: left;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {hover_col};
                border-color: {t['accent']};
            }}
            QPushButton:pressed {{
                background-color: {t['card_active']};
            }}
        """)

        # Label
        self.label_text.setStyleSheet(
            f'font-weight: 600; font-size: 13px; color: {t["text_title"]}; font-family: {FONT_FAMILY};'
        )

        # Target badge (Local vs SSH)
        tag_text = "Local" if is_local else (self.button.connection or "SSH")
        icon_name = "laptop" if is_local else "server"
        tag_color = t["text_muted"] if is_local else t["accent"]
        self.where_icon.setPixmap(get_icon(icon_name, tag_color, 12).pixmap(12, 12))
        self.where_text.setText(tag_text)
        self.where_text.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {tag_color};")
        self.tag_container.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
            }
        """)

        # Error indicator
        self.error_btn.setVisible(bool(self.error_msg))
        if self.error_msg:
            self.error_btn.setIcon(get_icon("triangle-alert", t["stop"], 15))
            self.error_btn.setToolTip(f"{self.button.label}: {self.error_msg}")

        # Live dot
        self.dot_label.setVisible(self.is_running)
        self.dot_label.setStyleSheet(f"color: {t['healthy']}; font-size: 9px; margin: 0 4px;")

        # Terminal button
        is_bg = (self.button.mode == MODE_BACKGROUND)
        self.term_btn.setVisible(not is_bg)
        if not is_bg:
            term_color = t["accent"] if self.is_running else t["text_muted"]
            self.term_btn.setIcon(get_icon("chevron-right", term_color, 14))
            self.term_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.04);
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 7px;
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.12);
                    border-color: {t['border_hover']};
                }}
            """)

        # Action button (Stop vs Edit)
        if self.is_running:
            self.action_btn.setIcon(get_icon("square", t["stop"], 12))
            self.action_btn.setToolTip("Stop program (Ctrl-C)")
            self.action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(232, 33, 39, 0.12);
                    border: 1px solid rgba(232, 33, 39, 0.35);
                    border-radius: 7px;
                }}
                QPushButton:hover {{
                    background: {t['stop']};
                }}
            """)
        else:
            self.action_btn.setIcon(get_icon("pencil", t["text_muted"], 13))
            self.action_btn.setToolTip("Edit profile settings")
            self.action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.04);
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 7px;
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.12);
                    border-color: {t['border_hover']};
                }}
            """)

    def _on_action_clicked(self):
        if self.is_running:
            self.stop_clicked.emit(self.button)
        else:
            self.edit_clicked.emit(self.button)
