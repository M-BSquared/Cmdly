"""Main Shelf View showing the launch button rows with clean frosted glass layout."""

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
    theme_manager,
    RADIUS_BTN,
    FONT_FAMILY,
    MONO_FONT,
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
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Scroll Area for rows
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.rows_container = QWidget(self.scroll_area)
        self.rows_container.setStyleSheet("background: transparent;")
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        self.rows_layout.setAlignment(Qt.AlignTop)  # Keep buttons cleanly at the top!
        self.scroll_area.setWidget(self.rows_container)

        main_layout.addWidget(self.scroll_area, stretch=1)

        # Empty State Widget
        self.empty_card = QFrame(self)
        ec_layout = QVBoxLayout(self.empty_card)
        ec_layout.setContentsMargins(20, 28, 20, 28)
        ec_layout.setSpacing(12)
        ec_layout.setAlignment(Qt.AlignCenter)

        empty_icon = QLabel(self.empty_card)
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_icon.setPixmap(get_icon("play", "#94a3b8", 24).pixmap(24, 24))
        ec_layout.addWidget(empty_icon)

        empty_title = QLabel("No Launch Profiles", self.empty_card)
        empty_title.setAlignment(Qt.AlignCenter)
        empty_title.setStyleSheet(f"font-size: 14px; font-weight: 600; font-family: {FONT_FAMILY};")
        ec_layout.addWidget(empty_title)

        empty_sub = QLabel(
            "Add a command profile to run local scripts or remote SSH programs with one press.",
            self.empty_card,
        )
        empty_sub.setAlignment(Qt.AlignCenter)
        empty_sub.setWordWrap(True)
        empty_sub.setStyleSheet(f"font-size: 12px; color: #94a3b8; font-family: {FONT_FAMILY};")
        ec_layout.addWidget(empty_sub)

        self.empty_add_btn = QPushButton("+ Add Profile", self.empty_card)
        self.empty_add_btn.setCursor(Qt.PointingHandCursor)
        self.empty_add_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.16);
            }
        """)
        self.empty_add_btn.clicked.connect(self.add_button_requested.emit)
        ec_layout.addWidget(self.empty_add_btn)

        self.empty_card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px dashed rgba(255, 255, 255, 0.14);
                border-radius: 12px;
            }
        """)
        main_layout.addWidget(self.empty_card)
        self.empty_card.hide()

        # Missing Connections note
        self.note_label = QLabel("", self)
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(f"font-size: 11.5px; padding: 4px 0; font-family: {FONT_FAMILY};")
        self.note_label.hide()
        main_layout.addWidget(self.note_label)

        # Add Button Row (sleek frosted secondary button)
        self.add_bar = QWidget(self)
        ab_layout = QHBoxLayout(self.add_bar)
        ab_layout.setContentsMargins(0, 2, 0, 0)
        ab_layout.setSpacing(8)

        self.add_btn = QPushButton("+ Add Button", self.add_bar)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self.add_button_requested.emit)
        ab_layout.addWidget(self.add_btn)
        ab_layout.addStretch()
        main_layout.addWidget(self.add_bar)

        # Detached output log area (for background runs)
        self.output_area = QTextEdit(self)
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumHeight(130)
        self.output_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 8px;
                font-family: {MONO_FONT};
                font-size: 11.5px;
            }}
        """)
        self.output_area.hide()
        main_layout.addWidget(self.output_area)

        self._apply_theme()

    def _apply_theme(self):
        t = theme_manager.current_theme
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.05);
                color: {t['text_title']};
                border: 1px dashed {t['border']};
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: 500;
                font-size: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.10);
                border-color: {t['accent']};
                color: {t['accent']};
            }}
            QPushButton:disabled {{
                opacity: 0.35;
            }}
        """)
        self.note_label.setStyleSheet(f"font-size: 11.5px; color: {t['warning']}; padding: 4px 0; font-family: {FONT_FAMILY};")

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
        self.empty_card.setVisible(not has_buttons)
        self.scroll_area.setVisible(has_buttons)
        self.add_bar.setVisible(has_buttons and len(buttons) < MAX_BUTTONS)

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
                f"Missing SSH connection: {names}. Launch will prompt for credentials."
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
