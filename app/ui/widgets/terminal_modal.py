"""In-app Frosted Terminal Modal matching Image 1."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QFrame,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QTextCursor
from app.ui.icons import get_icon
from app.ui.widgets.terminal_widget import ansi_to_html
from app.ui.styles import (
    FROSTED_MODAL,
    FROSTED_BORDER,
    FROSTED_INPUT,
    SLATE_TITLE,
    SLATE_TEXT,
    SLATE_MUTED,
    SLATE_FAINT,
    HEALTHY,
    ACCENT_ORANGE,
    RADIUS_MODAL,
    RADIUS_BTN,
)


class TerminalModalWidget(QFrame):
    send_input = Signal(str)
    send_interrupt = Signal()
    close_requested = Signal()
    pin_toggled = Signal(bool)

    def __init__(
        self,
        title: str = "ls",
        host: str = "this computer",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.session_title = title
        self.session_host = host
        self.is_pinned = False
        self.is_expanded = False

        self.setMinimumSize(480, 360)
        self.resize(600, 420)

        # Style matching Image 1: Light frosted glass with subtle border and rounded corners
        self.setStyleSheet(f"""
            TerminalModalWidget {{
                background-color: {FROSTED_MODAL};
                border: 1px solid {FROSTED_BORDER};
                border-radius: {RADIUS_MODAL}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)

        # 1. Header Bar matching Image 1
        header = QWidget(self)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        # [>_] Terminal icon
        term_icon = QLabel(header)
        term_icon.setPixmap(get_icon("terminal-box", SLATE_TITLE, 18).pixmap(18, 18))
        h_layout.addWidget(term_icon)

        # Title (e.g. "ls")
        self.title_label = QLabel(title, header)
        self.title_label.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {SLATE_TITLE};")
        h_layout.addWidget(self.title_label)

        # Subtitle (e.g. "this computer")
        self.host_label = QLabel(host, header)
        self.host_label.setStyleSheet(
            f'font-family: "SF Mono", Menlo, Monaco, monospace; font-size: 11px; color: {SLATE_MUTED};'
        )
        h_layout.addWidget(self.host_label)

        h_layout.addStretch()

        # ● CONNECTED badge
        self.status_container = QWidget(header)
        sc_layout = QHBoxLayout(self.status_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(5)

        self.dot_label = QLabel("●", self.status_container)
        self.dot_label.setStyleSheet(f"color: {HEALTHY}; font-size: 9px;")
        sc_layout.addWidget(self.dot_label)

        self.status_text = QLabel("CONNECTED", self.status_container)
        self.status_text.setStyleSheet(
            f"color: {HEALTHY}; font-size: 11px; font-weight: 700; letter-spacing: 0.6px;"
        )
        sc_layout.addWidget(self.status_text)
        h_layout.addWidget(self.status_container)

        h_layout.addSpacing(6)

        # Action Buttons matching Image 1 (Pin, Expand, Power/Restart, Close)
        # Pin
        self.pin_btn = QPushButton(header)
        self.pin_btn.setFixedSize(24, 24)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setIcon(get_icon("pin", SLATE_MUTED, 14))
        self.pin_btn.setToolTip("Pin window (keep open on click outside)")
        self.pin_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background: rgba(0, 0, 0, 0.05); }}
        """)
        self.pin_btn.clicked.connect(self._toggle_pin)
        h_layout.addWidget(self.pin_btn)

        # Expand / Contract
        self.expand_btn = QPushButton(header)
        self.expand_btn.setFixedSize(24, 24)
        self.expand_btn.setCursor(Qt.PointingHandCursor)
        self.expand_btn.setIcon(get_icon("expand", SLATE_MUTED, 14))
        self.expand_btn.setToolTip("Expand / Compact size")
        self.expand_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background: rgba(0, 0, 0, 0.05); }}
        """)
        self.expand_btn.clicked.connect(self._toggle_expand)
        h_layout.addWidget(self.expand_btn)

        # Power / Restart (Ctrl-C)
        self.power_btn = QPushButton(header)
        self.power_btn.setFixedSize(24, 24)
        self.power_btn.setCursor(Qt.PointingHandCursor)
        self.power_btn.setIcon(get_icon("power", SLATE_MUTED, 14))
        self.power_btn.setToolTip("Interrupt / Restart (Ctrl-C)")
        self.power_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background: rgba(0, 0, 0, 0.05); color: {ACCENT_ORANGE}; }}
        """)
        self.power_btn.clicked.connect(self.send_interrupt.emit)
        h_layout.addWidget(self.power_btn)

        # Close
        self.close_btn = QPushButton(header)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setIcon(get_icon("x", SLATE_MUTED, 14))
        self.close_btn.setToolTip("Close terminal modal")
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background: rgba(239, 68, 68, 0.1); }}
        """)
        self.close_btn.clicked.connect(self.close_requested.emit)
        h_layout.addWidget(self.close_btn)

        layout.addWidget(header)

        # 2. Terminal Text Area
        self.output_area = QTextEdit(self)
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont("SF Mono", 12))
        self.output_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                color: {SLATE_TITLE};
                border: none;
                font-family: "SF Mono", Menlo, Monaco, Consolas, "Courier New", monospace;
                font-size: 12.5px;
                line-height: 1.45;
                padding: 4px 0;
            }}
        """)
        layout.addWidget(self.output_area, stretch=1)

        # 3. Quick Input Prompt Line
        input_box = QWidget(self)
        ib_layout = QHBoxLayout(input_box)
        ib_layout.setContentsMargins(0, 0, 0, 0)
        ib_layout.setSpacing(6)

        self.input_line = QLineEdit(input_box)
        self.input_line.setPlaceholderText("Type command or input...")
        self.input_line.setProperty("mono", "true")
        self.input_line.setStyleSheet(f"""
            QLineEdit {{
                background-color: {FROSTED_INPUT};
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: {RADIUS_BTN}px;
                padding: 6px 10px;
                font-size: 12px;
                color: {SLATE_TITLE};
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_ORANGE};
            }}
        """)
        self.input_line.returnPressed.connect(self._handle_submit)
        ib_layout.addWidget(self.input_line, stretch=1)

        self.send_btn = QPushButton("Send", input_box)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_ORANGE};
                color: #ffffff;
                border: none;
                border-radius: {RADIUS_BTN}px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #f97316;
            }}
        """)
        self.send_btn.clicked.connect(self._handle_submit)
        ib_layout.addWidget(self.send_btn)

        layout.addWidget(input_box)

    def append_output(self, text: str):
        html_content = ansi_to_html(text)
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html_content)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()

    def set_connected(self, connected: bool):
        if connected:
            self.dot_label.setStyleSheet(f"color: {HEALTHY}; font-size: 9px;")
            self.status_text.setText("CONNECTED")
            self.status_text.setStyleSheet(
                f"color: {HEALTHY}; font-size: 11px; font-weight: 700; letter-spacing: 0.6px;"
            )
        else:
            self.dot_label.setStyleSheet(f"color: {SLATE_MUTED}; font-size: 9px;")
            self.status_text.setText("DISCONNECTED")
            self.status_text.setStyleSheet(
                f"color: {SLATE_MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 0.6px;"
            )

    def set_info(self, title: str, host: str):
        self.session_title = title
        self.session_host = host
        self.title_label.setText(title)
        self.host_label.setText(host)

    def _handle_submit(self):
        text = self.input_line.text()
        self.input_line.clear()
        self.send_input.emit(text + "\n")

    def _toggle_pin(self):
        self.is_pinned = not self.is_pinned
        color = ACCENT_ORANGE if self.is_pinned else SLATE_MUTED
        self.pin_btn.setIcon(get_icon("pin", color, 14))
        self.pin_toggled.emit(self.is_pinned)

    def _toggle_expand(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.resize(720, 520)
            self.expand_btn.setIcon(get_icon("shrink", SLATE_MUTED, 14))
        else:
            self.resize(600, 420)
            self.expand_btn.setIcon(get_icon("expand", SLATE_MUTED, 14))
