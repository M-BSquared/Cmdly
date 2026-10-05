"""Companion Computer telemetry status strip with frosted glass styling."""

from typing import Optional
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from PySide6.QtCore import Signal, Qt
from app.models import CompanionConfig
from app.ui.icons import get_icon
from app.ui.styles import (
    theme_manager,
    RADIUS_BTN,
    FONT_FAMILY,
    MONO_FONT,
)


class CompanionBar(QFrame):
    clicked = Signal()
    open_terminal_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.companion: Optional[CompanionConfig] = None
        self.state: str = "unset"
        self.rtt_ms: Optional[float] = None
        self.error_msg: str = ""

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 10, 4)
        layout.setSpacing(10)

        # Telemetry CPU Icon inside subtle container
        self.icon_badge = QLabel(self)
        self.icon_badge.setFixedSize(26, 26)
        self.icon_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_badge)

        # Name & Host text container
        text_box = QWidget(self)
        tb_layout = QHBoxLayout(text_box)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(8)

        self.name_label = QLabel("Companion Computer", text_box)
        self.name_label.setStyleSheet(
            f"font-weight: 600; font-size: 13px; font-family: {FONT_FAMILY};"
        )
        tb_layout.addWidget(self.name_label)

        self.host_label = QLabel("Click to configure", text_box)
        self.host_label.setStyleSheet(
            f'font-family: {MONO_FONT}; font-size: 11px;'
        )
        tb_layout.addWidget(self.host_label)
        layout.addWidget(text_box)

        layout.addStretch()

        # Telemetry State Pill
        self.state_pill = QFrame(self)
        sp_layout = QHBoxLayout(self.state_pill)
        sp_layout.setContentsMargins(8, 3, 8, 3)
        sp_layout.setSpacing(5)

        self.dot_label = QLabel("●", self.state_pill)
        self.dot_label.setStyleSheet("font-size: 8px;")
        sp_layout.addWidget(self.dot_label)

        self.state_text = QLabel("Not Set", self.state_pill)
        self.state_text.setStyleSheet(
            f"font-size: 11px; font-weight: 600; font-family: {FONT_FAMILY};"
        )
        sp_layout.addWidget(self.state_text)

        layout.addWidget(self.state_pill)

        # Quick SSH shell button
        self.arrow_btn = QPushButton(self)
        self.arrow_btn.setFixedSize(26, 26)
        self.arrow_btn.setCursor(Qt.PointingHandCursor)
        self.arrow_btn.setToolTip("Open Companion SSH Shell")
        self.arrow_btn.clicked.connect(self.open_terminal_requested.emit)
        self.arrow_btn.hide()
        layout.addWidget(self.arrow_btn)

        self._render_state()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_data(
        self,
        companion: Optional[CompanionConfig],
        state: str,
        rtt_ms: Optional[float] = None,
        error_msg: str = "",
    ):
        self.companion = companion
        self.state = state
        self.rtt_ms = rtt_ms
        self.error_msg = error_msg
        self._render_state()

    def _render_state(self):
        t = theme_manager.current_theme

        # Determine state styling
        if not self.companion or not self.companion.host:
            status_text = "Not Set"
            dot_color = t["text_faint"]
            border_color = t["border"]
            can_ssh = False
            badge_icon_color = t["text_muted"]
            host_text = "Click to configure"
        elif self.state == "online":
            rtt_str = f" · {self.rtt_ms:.1f} ms" if self.rtt_ms is not None else ""
            status_text = f"Online{rtt_str}"
            dot_color = t["healthy"]
            border_color = t["healthy"]
            can_ssh = bool(self.companion.connection)
            badge_icon_color = t["healthy"]
            host_text = self.companion.host
        elif self.state == "offline":
            status_text = "Offline"
            dot_color = t["stop"]
            border_color = t["stop"]
            can_ssh = False
            badge_icon_color = t["stop"]
            host_text = self.companion.host
        elif self.state == "checking":
            status_text = "Checking…"
            dot_color = t["warning"]
            border_color = t["warning"]
            can_ssh = False
            badge_icon_color = t["warning"]
            host_text = self.companion.host
        else:
            status_text = "Error"
            dot_color = t["stop"]
            border_color = t["stop"]
            can_ssh = False
            badge_icon_color = t["stop"]
            host_text = self.companion.host

        display_name = self.companion.name if (self.companion and self.companion.name) else "Companion Computer"
        self.name_label.setText(display_name)
        self.name_label.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {t['text_title']}; font-family: {FONT_FAMILY};"
        )

        self.host_label.setText(host_text)
        self.host_label.setStyleSheet(
            f'font-family: {MONO_FONT}; font-size: 11px; color: {t["text_muted"]};'
        )

        self.dot_label.setStyleSheet(f"color: {dot_color}; font-size: 8px;")
        self.state_text.setText(status_text)
        self.state_text.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {t['text_title']}; font-family: {FONT_FAMILY};"
        )

        self.icon_badge.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        self.icon_badge.setPixmap(get_icon("cpu", badge_icon_color, 14).pixmap(14, 14))

        self.state_pill.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)

        self.setStyleSheet(f"""
            CompanionBar {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            CompanionBar:hover {{
                background-color: rgba(255, 255, 255, 0.09);
            }}
        """)

        # Quick SSH Arrow
        self.arrow_btn.setVisible(can_ssh)
        if can_ssh:
            self.arrow_btn.setIcon(get_icon("chevron-right", t["healthy"], 14))
            self.arrow_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(16, 185, 129, 0.12);
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: rgba(16, 185, 129, 0.25);
                }}
            """)
