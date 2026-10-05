"""Companion Computer telemetry status strip with Tesla styling."""

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
    TESLA_CARD,
    TESLA_CARD_HOVER,
    TESLA_BORDER,
    TEXT_TITLE,
    TEXT_MUTED,
    TEXT_FAINT,
    HEALTHY,
    WARNING,
    CRITICAL,
    ACCENT_CYAN,
    RADIUS_BTN,
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
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 10, 4)
        layout.setSpacing(10)

        # Telemetry CPU Icon
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(18, 18)
        layout.addWidget(self.icon_label)

        # Name & Host text
        self.name_label = QLabel("COMPANION COMPUTER", self)
        self.name_label.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {TEXT_TITLE}; letter-spacing: 0.6px;")
        layout.addWidget(self.name_label)

        self.host_label = QLabel("PRESS TO CONFIGURE", self)
        self.host_label.setStyleSheet(
            f'font-family: "SF Mono", Menlo, Monaco, monospace; font-size: 11px; color: {TEXT_MUTED};'
        )
        layout.addWidget(self.host_label)

        layout.addStretch()

        # Telemetry State Pill
        self.state_container = QWidget(self)
        state_layout = QHBoxLayout(self.state_container)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(6)

        self.dot_label = QLabel("●", self.state_container)
        self.dot_label.setStyleSheet(f"font-size: 9px; color: {TEXT_FAINT};")
        state_layout.addWidget(self.dot_label)

        self.state_text = QLabel("NOT SET", self.state_container)
        self.state_text.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {TEXT_MUTED}; letter-spacing: 0.8px;")
        state_layout.addWidget(self.state_text)

        layout.addWidget(self.state_container)

        # Arrow button for terminal (Electric Cyan)
        self.arrow_btn = QPushButton(self)
        self.arrow_btn.setFixedSize(26, 26)
        self.arrow_btn.setCursor(Qt.PointingHandCursor)
        self.arrow_btn.setIcon(get_icon("chevron-right", ACCENT_CYAN, 14))
        self.arrow_btn.setToolTip("Open SSH Terminal Shell")
        self.arrow_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(56, 189, 248, 0.08);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: {RADIUS_BTN}px;
            }}
            QPushButton:hover {{
                background-color: rgba(56, 189, 248, 0.22);
            }}
        """)
        self.arrow_btn.clicked.connect(self.open_terminal_requested.emit)
        self.arrow_btn.hide()
        layout.addWidget(self.arrow_btn)

        self._update_appearance()

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
        self._update_appearance()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.arrow_btn.geometry().contains(event.pos()) or not self.arrow_btn.isVisible():
                self.clicked.emit()
        super().mousePressEvent(event)

    def _update_appearance(self):
        if self.companion and self.companion.host:
            self.name_label.setText((self.companion.name or "COMPANION COMPUTER").upper())
            self.host_label.setText(self.companion.host)
        else:
            self.name_label.setText("COMPANION COMPUTER")
            self.host_label.setText("PRESS TO CONFIGURE")

        # Telemetry State Styling
        if self.state == "online":
            border_color = HEALTHY
            icon_color = HEALTHY
            dot_color = HEALTHY
            rtt_str = f" · {self.rtt_ms:.1f} MS" if self.rtt_ms is not None else ""
            state_str = f"ONLINE{rtt_str}"
            tooltip = f"Pinged every {self.companion.interval_s}s, online" if self.companion else ""
            show_arrow = bool(self.companion and self.companion.connection)
        elif self.state == "offline":
            border_color = CRITICAL
            icon_color = CRITICAL
            dot_color = CRITICAL
            state_str = "OFFLINE"
            tooltip = "No reply received before timeout"
            show_arrow = False
        elif self.state == "checking":
            border_color = WARNING
            icon_color = TEXT_MUTED
            dot_color = WARNING
            state_str = "CHECKING"
            tooltip = "Pinging companion..."
            show_arrow = False
        elif self.state == "error":
            border_color = WARNING
            icon_color = CRITICAL
            dot_color = WARNING
            state_str = "CANNOT PING"
            tooltip = self.error_msg or "Cannot ping host"
            show_arrow = False
        else:  # unset
            border_color = TESLA_BORDER
            icon_color = TEXT_FAINT
            dot_color = TEXT_FAINT
            state_str = "NOT SET"
            tooltip = "Click to configure companion computer"
            show_arrow = False

        self.setStyleSheet(f"""
            CompanionBar {{
                background-color: {TESLA_CARD};
                border: 1px solid {border_color};
                border-radius: {RADIUS_BTN + 2}px;
            }}
            CompanionBar:hover {{
                background-color: {TESLA_CARD_HOVER};
            }}
        """)

        self.icon_label.setPixmap(get_icon("cpu", icon_color, 18).pixmap(18, 18))
        self.dot_label.setStyleSheet(f"font-size: 9px; color: {dot_color};")
        self.state_text.setText(state_str)
        self.state_text.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {dot_color if self.state != 'unset' else TEXT_MUTED}; letter-spacing: 0.8px;")
        self.setToolTip(tooltip)
        self.arrow_btn.setVisible(show_arrow)
