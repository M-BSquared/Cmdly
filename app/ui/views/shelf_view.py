"""Main Shelf View showing the launch button rows with Tesla smoked glass styling."""

from typing import List, Dict, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QTextEdit,
)
from PySide6.QtCore import Signal, Qt
from app.models import ButtonConfig, SshConnection, MAX_BUTTONS, TARGET_SSH
from app.ui.widgets.shelf_row import ShelfRow
from app.ui.icons import get_icon
from app.ui.styles import (
    TESLA_CARD,
    TESLA_BORDER,
    TESLA_INPUT,
    TEXT_TITLE,
    TEXT_BODY,
    TEXT_MUTED,
    ACCENT_CYAN,
    RADIUS_CARD,
    RADIUS_BTN,
)


class ShelfView(QWidget):
    launch_requested = Signal(object)
    terminal_requested = Signal(object)
    stop_requested = Signal(object)
    edit_requested = Signal(object)
    add_button_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.buttons: List[ButtonConfig] = []
        self.connections: List[SshConnection] = []
        self.row_widgets: Dict[str, ShelfRow] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 6, 12, 12)
        main_layout.setSpacing(10)

        # Card container: Tesla Smoked Glass Card
        self.card = QFrame(self)
        self.card.setObjectName("Card")
        self.card.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {TESLA_CARD};
                border: 1px solid {TESLA_BORDER};
                border-radius: {RADIUS_CARD}px;
            }}
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)

        # Rows container inside scroll area
        self.scroll_area = QScrollArea(self.card)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.rows_container = QWidget(self.scroll_area)
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        self.scroll_area.setWidget(self.rows_container)
        card_layout.addWidget(self.scroll_area)

        # Empty State label
        self.empty_label = QLabel(
            "NO LAUNCH PROFILES CONFIGURED. ADD A PROFILE TO CONTROL ON-BOARD OR REMOTE PROGRAMS.",
            self.card,
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(f"font-size: 11.5px; font-weight: 600; color: {TEXT_MUTED}; letter-spacing: 0.8px; padding: 18px 4px;")
        card_layout.addWidget(self.empty_label)

        # Missing Connections note
        self.note_label = QLabel("", self.card)
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(f"font-size: 11.5px; color: {TEXT_MUTED}; padding: 4px 0;")
        self.note_label.hide()
        card_layout.addWidget(self.note_label)

        # Add Button action bar (Tesla High-Tech Action)
        add_bar = QWidget(self.card)
        ab_layout = QHBoxLayout(add_bar)
        ab_layout.setContentsMargins(0, 4, 0, 0)
        ab_layout.setSpacing(8)

        self.add_btn = QPushButton("ADD BUTTON", add_bar)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setIcon(get_icon("plus", ACCENT_CYAN, 14))
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.06);
                color: {TEXT_TITLE};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: {RADIUS_BTN}px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 11.5px;
                letter-spacing: 0.8px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.12);
                border-color: {ACCENT_CYAN};
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
        """)
        self.add_btn.clicked.connect(self.add_button_requested.emit)
        ab_layout.addWidget(self.add_btn)
        ab_layout.addStretch()
        card_layout.addWidget(add_bar)

        # Detached output log area (Cyber console)
        self.output_area = QTextEdit(self.card)
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumHeight(140)
        self.output_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {TESLA_INPUT};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: {RADIUS_BTN}px;
                padding: 8px;
                font-family: "SF Mono", Menlo, Monaco, monospace;
                font-size: 11.5px;
                color: {TEXT_BODY};
            }}
        """)
        self.output_area.hide()
        card_layout.addWidget(self.output_area)

        main_layout.addWidget(self.card)

    def set_data(
        self,
        buttons: List[ButtonConfig],
        connections: List[SshConnection],
        active_sessions: Dict[str, bool],
        errors: Dict[str, str],
    ):
        self.buttons = buttons
        self.connections = connections

        # Clear existing rows
        for w in self.row_widgets.values():
            self.rows_layout.removeWidget(w)
            w.deleteLater()
        self.row_widgets.clear()

        has_buttons = len(buttons) > 0
        self.empty_label.setVisible(not has_buttons)
        self.scroll_area.setVisible(has_buttons)
        self.add_btn.setEnabled(len(buttons) < MAX_BUTTONS)

        if has_buttons:
            for b in buttons:
                sid = f"schwalby/{b.id}"
                is_running = bool(active_sessions.get(sid, False))
                err = errors.get(b.id, "")
                row = ShelfRow(b, is_running=is_running, error_msg=err, parent=self.rows_container)

                row.launch_clicked.connect(self.launch_requested.emit)
                row.terminal_clicked.connect(self.terminal_requested.emit)
                row.stop_clicked.connect(self.stop_requested.emit)
                row.edit_clicked.connect(self.edit_requested.emit)

                self.rows_layout.addWidget(row)
                self.row_widgets[b.id] = row

        # Check for missing SSH connections
        known_conns = {c.name for c in connections}
        missing = []
        for b in buttons:
            if b.target == TARGET_SSH and b.connection and b.connection not in known_conns:
                if b.connection not in missing:
                    missing.append(b.connection)

        if missing:
            names = ", ".join(f'"{n}"' for n in missing)
            self.note_label.setText(
                f"UNRESOLVED SSH CONNECTIONS: {names}. "
                "LAUNCH WILL PROMPT FOR ADDRESS AND CREDENTIALS."
            )
            self.note_label.show()
        else:
            self.note_label.hide()

    def update_row_state(self, button_id: str, is_running: bool, error_msg: str = ""):
        if button_id in self.row_widgets:
            self.row_widgets[button_id].update_state(is_running, error_msg)

    def show_output(self, text: str):
        if text.strip():
            self.output_area.setText(text)
            self.output_area.show()
        else:
            self.output_area.hide()
