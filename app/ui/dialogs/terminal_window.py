"""Standalone Tesla Smoked Frosted Glass Terminal Window."""

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
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QTextCursor, QColor, QMouseEvent
from app.ui.icons import get_icon
from app.ui.widgets.terminal_widget import ansi_to_html
from app.ui.styles import (
    TESLA_MODAL,
    TESLA_BORDER,
    TESLA_INPUT,
    TEXT_TITLE,
    TEXT_BODY,
    TEXT_MUTED,
    HEALTHY,
    ACCENT_CYAN,
    TESLA_RED,
    RADIUS_CARD,
    RADIUS_BTN,
)


class TerminalWindow(QWidget):
    session_input = Signal(str, str)        # (session_id, data)
    session_interrupt = Signal(str)         # (session_id)
    session_close = Signal(str)             # (session_id)

    def __init__(
        self,
        session_id: str,
        title: str = "ls",
        host: str = "this computer",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(None)  # Standalone floating window
        self.session_id = session_id
        self.session_title = title
        self.session_host = host
        self.is_pinned = False
        self.is_maximized_custom = False
        self._drag_pos = QPoint()

        # Frameless and translucent window with custom dark smoked glass frame
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(700, 450)
        self.setMinimumSize(460, 300)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)

        # Tesla Smoked Obsidian Glass Frame
        self.frame = QFrame(self)
        self.frame.setObjectName("TerminalFrame")
        self.frame.setStyleSheet(f"""
            QFrame#TerminalFrame {{
                background-color: {TESLA_MODAL};
                border: 1px solid rgba(255, 255, 255, 0.13);
                border-radius: {RADIUS_CARD + 4}px;
            }}
        """)

        # Ambient Dark Drop Shadow
        shadow = QGraphicsDropShadowEffect(self.frame)
        shadow.setBlurRadius(36)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 10)
        self.frame.setGraphicsEffect(shadow)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(16, 12, 16, 14)
        frame_layout.setSpacing(8)

        # 1. Header Bar (Telemetry HUD style)
        self.header = QWidget(self.frame)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        # [>_] Terminal icon
        term_icon = QLabel(self.header)
        term_icon.setPixmap(get_icon("terminal-box", ACCENT_CYAN, 18).pixmap(18, 18))
        h_layout.addWidget(term_icon)

        # Title (e.g. "ls")
        self.title_label = QLabel(title, self.header)
        self.title_label.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {TEXT_TITLE}; letter-spacing: 0.6px;")
        h_layout.addWidget(self.title_label)

        # Subtitle (e.g. "this computer")
        self.host_label = QLabel(host, self.header)
        self.host_label.setStyleSheet(
            f'font-family: "SF Mono", Menlo, Monaco, monospace; font-size: 11px; color: {TEXT_MUTED};'
        )
        h_layout.addWidget(self.host_label)

        h_layout.addStretch()

        # ● CONNECTED badge
        self.status_container = QWidget(self.header)
        sc_layout = QHBoxLayout(self.status_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(5)

        self.dot_label = QLabel("●", self.status_container)
        self.dot_label.setStyleSheet(f"color: {HEALTHY}; font-size: 9px;")
        sc_layout.addWidget(self.dot_label)

        self.status_text = QLabel("CONNECTED", self.status_container)
        self.status_text.setStyleSheet(
            f"color: {HEALTHY}; font-size: 11px; font-weight: 800; letter-spacing: 0.8px;"
        )
        sc_layout.addWidget(self.status_text)
        h_layout.addWidget(self.status_container)

        h_layout.addSpacing(6)

        # Header Action Buttons (Pin, Expand, Power, Close)
        # 📌 Pin
        self.pin_btn = QPushButton(self.header)
        self.pin_btn.setFixedSize(24, 24)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setIcon(get_icon("pin", TEXT_MUTED, 14))
        self.pin_btn.setToolTip("Pin window (always on top)")
        self.pin_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background: rgba(255, 255, 255, 0.08); }}
        """)
        self.pin_btn.clicked.connect(self._toggle_pin)
        h_layout.addWidget(self.pin_btn)

        # ⤢ Expand
        self.expand_btn = QPushButton(self.header)
        self.expand_btn.setFixedSize(24, 24)
        self.expand_btn.setCursor(Qt.PointingHandCursor)
        self.expand_btn.setIcon(get_icon("expand", TEXT_MUTED, 14))
        self.expand_btn.setToolTip("Maximize / Restore")
        self.expand_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background: rgba(255, 255, 255, 0.08); }}
        """)
        self.expand_btn.clicked.connect(self._toggle_expand)
        h_layout.addWidget(self.expand_btn)

        # ⏻ Power / Restart
        self.power_btn = QPushButton(self.header)
        self.power_btn.setFixedSize(24, 24)
        self.power_btn.setCursor(Qt.PointingHandCursor)
        self.power_btn.setIcon(get_icon("power", TEXT_MUTED, 14))
        self.power_btn.setToolTip("Interrupt / Restart (Ctrl-C)")
        self.power_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background: rgba(232, 33, 39, 0.2); color: {TESLA_RED}; }}
        """)
        self.power_btn.clicked.connect(lambda: self.session_interrupt.emit(self.session_id))
        h_layout.addWidget(self.power_btn)

        # ✕ Close
        self.close_btn = QPushButton(self.header)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setIcon(get_icon("x", TEXT_MUTED, 14))
        self.close_btn.setToolTip("Close terminal")
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background: rgba(232, 33, 39, 0.25); }}
        """)
        self.close_btn.clicked.connect(self._handle_close)
        h_layout.addWidget(self.close_btn)

        frame_layout.addWidget(self.header)

        # 2. Terminal Text Output Area (Dark High-Contrast)
        self.output_area = QTextEdit(self.frame)
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont("SF Mono", 12))
        self.output_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                color: {TEXT_TITLE};
                border: none;
                font-family: "SF Mono", Menlo, Monaco, Consolas, "Courier New", monospace;
                font-size: 12.5px;
                line-height: 1.45;
                padding: 4px 0;
            }}
        """)
        frame_layout.addWidget(self.output_area, stretch=1)

        # 3. Interactive Input Prompt Line
        input_box = QWidget(self.frame)
        ib_layout = QHBoxLayout(input_box)
        ib_layout.setContentsMargins(0, 0, 0, 0)
        ib_layout.setSpacing(6)

        self.input_line = QLineEdit(input_box)
        self.input_line.setPlaceholderText("Type command or input...")
        self.input_line.setProperty("mono", "true")
        self.input_line.setStyleSheet(f"""
            QLineEdit {{
                background-color: {TESLA_INPUT};
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: {RADIUS_BTN}px;
                padding: 7px 12px;
                font-size: 12.5px;
                color: {TEXT_TITLE};
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_CYAN};
            }}
        """)
        self.input_line.returnPressed.connect(self._handle_submit)
        ib_layout.addWidget(self.input_line, stretch=1)

        self.send_btn = QPushButton("SEND", input_box)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_CYAN};
                color: #080c14;
                border: none;
                border-radius: {RADIUS_BTN}px;
                padding: 7px 18px;
                font-size: 11.5px;
                font-weight: 800;
                letter-spacing: 0.6px;
            }}
            QPushButton:hover {{
                background-color: #7dd3fc;
            }}
        """)
        self.send_btn.clicked.connect(self._handle_submit)
        ib_layout.addWidget(self.send_btn)

        frame_layout.addWidget(input_box)
        main_layout.addWidget(self.frame)

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
                f"color: {HEALTHY}; font-size: 11px; font-weight: 800; letter-spacing: 0.8px;"
            )
        else:
            self.dot_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")
            self.status_text.setText("DISCONNECTED")
            self.status_text.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 800; letter-spacing: 0.8px;"
            )

    def set_info(self, title: str, host: str):
        self.session_title = title
        self.session_host = host
        self.title_label.setText(title.upper())
        self.host_label.setText(host)

    def _handle_submit(self):
        text = self.input_line.text()
        self.input_line.clear()
        self.session_input.emit(self.session_id, text + "\n")

    def _handle_close(self):
        self.session_close.emit(self.session_id)
        self.close()

    def _toggle_pin(self):
        self.is_pinned = not self.is_pinned
        color = ACCENT_CYAN if self.is_pinned else TEXT_MUTED
        self.pin_btn.setIcon(get_icon("pin", color, 14))

        flags = self.windowFlags()
        if self.is_pinned:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    def _toggle_expand(self):
        if not self.is_maximized_custom:
            self.setWindowState(self.windowState() | Qt.WindowMaximized)
            self.expand_btn.setIcon(get_icon("shrink", TEXT_MUTED, 14))
            self.is_maximized_custom = True
        else:
            self.setWindowState(self.windowState() & ~Qt.WindowMaximized)
            self.expand_btn.setIcon(get_icon("expand", TEXT_MUTED, 14))
            self.is_maximized_custom = False

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            header_rect = self.header.rect()
            header_pos = self.header.mapFrom(self, event.pos())
            if header_rect.contains(header_pos):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull() and not self.is_maximized_custom:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = QPoint()
        super().mouseReleaseEvent(event)
