"""Interactive terminal emulator display widget with ANSI color support."""

import html
import re
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QTextCursor
from app.ui.icons import get_icon
from app.ui.styles import (
    PANEL_FILL,
    SURFACE_CARD,
    SURFACE_HOVER,
    BORDER_SOFT,
    TEXT_1,
    TEXT_2,
    TEXT_3,
    CRITICAL,
    RADIUS_BTN,
)

ANSI_COLOR_MAP = {
    "30": "#2e3440",  # Black
    "31": "#eb4d4b",  # Red
    "32": "#2ec971",  # Green
    "33": "#f5a623",  # Yellow
    "34": "#3b82f6",  # Blue
    "35": "#b48ead",  # Magenta
    "36": "#88c0d0",  # Cyan
    "37": "#eceff4",  # White
    "90": "#4c566a",  # Bright Black
    "91": "#ff5e57",  # Bright Red
    "92": "#a3be8c",  # Bright Green
    "93": "#ebcb8b",  # Bright Yellow
    "94": "#81a1c1",  # Bright Blue
    "95": "#b48ead",  # Bright Magenta
    "96": "#8fbcbb",  # Bright Cyan
    "97": "#ffffff",  # Bright White
}


def ansi_to_html(text: str) -> str:
    """Converts terminal output containing ANSI escape codes into safe HTML."""
    escaped = html.escape(text)
    # Match ANSI sequence e.g. \x1b[31m or \x1b[0;32m
    ansi_re = re.compile(r"\x1b\[([0-9;]*)m")

    parts = []
    last_idx = 0
    current_color = None
    is_bold = False

    for match in ansi_re.finditer(escaped):
        parts.append(escaped[last_idx:match.start()])
        last_idx = match.end()

        codes = match.group(1).split(";")
        for code in codes:
            code = code.strip()
            if code in ("0", ""):  # Reset
                if current_color or is_bold:
                    parts.append("</span>")
                current_color = None
                is_bold = False
            elif code == "1":  # Bold
                is_bold = True
            elif code in ANSI_COLOR_MAP:
                current_color = ANSI_COLOR_MAP[code]

        if current_color or is_bold:
            style = []
            if current_color:
                style.append(f"color: {current_color};")
            if is_bold:
                style.append("font-weight: bold;")
            parts.append(f'<span style="{" ".join(style)}">')

    parts.append(escaped[last_idx:])
    if current_color or is_bold:
        parts.append("</span>")

    # Replace newlines with <br>
    return "".join(parts).replace("\n", "<br>")


class TerminalWidget(QWidget):
    send_input = Signal(str)
    send_interrupt = Signal()
    close_requested = Signal()

    def __init__(self, session_title: str = "Terminal", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.session_title = session_title

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header bar
        header = QWidget(self)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(session_title, header)
        self.title_label.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {TEXT_1};")
        h_layout.addWidget(self.title_label)

        h_layout.addStretch()

        # Quick Ctrl-C button
        self.ctrl_c_btn = QPushButton("Ctrl+C", header)
        self.ctrl_c_btn.setCursor(Qt.PointingHandCursor)
        self.ctrl_c_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_HOVER};
                color: {CRITICAL};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {CRITICAL};
                color: #ffffff;
            }}
        """)
        self.ctrl_c_btn.clicked.connect(self.send_interrupt.emit)
        h_layout.addWidget(self.ctrl_c_btn)

        # Clear button
        self.clear_btn = QPushButton("Clear", header)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_HOVER};
                color: {TEXT_2};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {BORDER_SOFT};
                color: {TEXT_1};
            }}
        """)
        self.clear_btn.clicked.connect(self.clear_terminal)
        h_layout.addWidget(self.clear_btn)

        # Close session button
        self.close_btn = QPushButton(header)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setIcon(get_icon("trash-2", TEXT_3, 14))
        self.close_btn.setToolTip("Disconnect and close terminal")
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; }}
            QPushButton:hover {{ background-color: {SURFACE_HOVER}; }}
        """)
        self.close_btn.clicked.connect(self.close_requested.emit)
        h_layout.addWidget(self.close_btn)

        layout.addWidget(header)

        # Output Text Area
        self.output_area = QTextEdit(self)
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont("SF Mono", 12))
        self.output_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {PANEL_FILL};
                color: {TEXT_1};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                padding: 8px;
                font-family: "SF Mono", Menlo, Monaco, Consolas, "Courier New", monospace;
                font-size: 12px;
                line-height: 1.4;
            }}
        """)
        layout.addWidget(self.output_area, stretch=1)

        # Input Prompt Bar
        input_bar = QWidget(self)
        ib_layout = QHBoxLayout(input_bar)
        ib_layout.setContentsMargins(0, 0, 0, 0)
        ib_layout.setSpacing(6)

        self.input_line = QLineEdit(input_bar)
        self.input_line.setPlaceholderText("Type command or input...")
        self.input_line.setProperty("mono", "true")
        self.input_line.returnPressed.connect(self._handle_submit)
        ib_layout.addWidget(self.input_line, stretch=1)

        self.send_btn = QPushButton("Send", input_bar)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setProperty("class", "PrimaryBtn")
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_HOVER};
                color: {TEXT_1};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {BORDER_SOFT};
            }}
        """)
        self.send_btn.clicked.connect(self._handle_submit)
        ib_layout.addWidget(self.send_btn)

        layout.addWidget(input_bar)

    def append_output(self, text: str):
        html_content = ansi_to_html(text)
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html_content)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()

    def clear_terminal(self):
        self.output_area.clear()

    def set_title(self, title: str):
        self.session_title = title
        self.title_label.setText(title)

    def _handle_submit(self):
        text = self.input_line.text()
        self.input_line.clear()
        self.send_input.emit(text + "\n")
