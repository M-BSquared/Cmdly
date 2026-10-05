"""Main Shelf View showing the launch button rows matching Schwalby shelf."""

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
    PANEL_FILL,
    SURFACE_HOVER,
    SURFACE_ACTIVE,
    BORDER_SOFT,
    TEXT_1,
    TEXT_2,
    TEXT_3,
    CRITICAL,
    RADIUS_BTN,
    RADIUS_CARD,
)


class ShelfView(QWidget):
    launch_requested = Signal(object)      # (ButtonConfig)
    terminal_requested = Signal(object)    # (ButtonConfig)
    stop_requested = Signal(object)        # (ButtonConfig)
    edit_requested = Signal(object)        # (ButtonConfig)
    add_button_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.buttons: List[ButtonConfig] = []
        self.connections: List[SshConnection] = []
        self.row_widgets: Dict[str, ShelfRow] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Card container
        self.card = QFrame(self)
        self.card.setObjectName("Card")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        # Rows container inside scroll area if needed
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
            "No launch buttons yet. Add one for each program you start before a flight, "
            "on this computer or on a companion computer.",
            self.card,
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(f"font-size: 13px; color: {TEXT_3}; padding: 12px 0;")
        card_layout.addWidget(self.empty_label)

        # Missing Connections note
        self.note_label = QLabel("", self.card)
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(f"font-size: 11px; color: {TEXT_2}; padding: 4px 0;")
        self.note_label.hide()
        card_layout.addWidget(self.note_label)

        # Add Button action bar
        add_bar = QWidget(self.card)
        ab_layout = QHBoxLayout(add_bar)
        ab_layout.setContentsMargins(0, 4, 0, 0)
        ab_layout.setSpacing(8)

        self.add_btn = QPushButton("Add button", add_bar)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setIcon(get_icon("plus", TEXT_1, 14))
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_HOVER};
                color: {TEXT_1};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                padding: 7px 14px;
                font-weight: 500;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {SURFACE_ACTIVE};
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
        """)
        self.add_btn.clicked.connect(self.add_button_requested.emit)
        ab_layout.addWidget(self.add_btn)
        ab_layout.addStretch()
        card_layout.addWidget(add_bar)

        # Detached output log area (collapsible .schw-output)
        self.output_area = QTextEdit(self.card)
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumHeight(140)
        self.output_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {PANEL_FILL};
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                padding: 8px;
                font-family: "SF Mono", Menlo, Monaco, monospace;
                font-size: 11px;
                color: {TEXT_2};
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
                f"Not set up on this computer yet: {names}. "
                "Press a button that uses one to enter its address and login once."
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
