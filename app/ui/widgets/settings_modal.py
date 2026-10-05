"""Settings modal allowing theme selection and preferences."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QComboBox,
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Signal, Qt
from app.config import ConfigManager
from app.ui.icons import get_icon
from app.ui.styles import (
    THEMES,
    theme_manager,
    RADIUS_MODAL,
    RADIUS_BTN,
    FONT_FAMILY,
)


class SettingsModalWidget(QFrame):
    close_requested = Signal()
    theme_selected = Signal(str)

    def __init__(
        self,
        config_manager: ConfigManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.config_manager = config_manager

        self.setMinimumWidth(380)
        self.setMaximumWidth(440)

        t = theme_manager.current_theme
        self.setStyleSheet(f"""
            SettingsModalWidget {{
                background-color: {t['modal']};
                border: 1px solid {t['border']};
                border-radius: {RADIUS_MODAL}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(16)

        # 1. Header (Icon + Title + Close Button)
        header = QWidget(self)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)

        title_icon = QLabel(header)
        title_icon.setPixmap(get_icon("cpu", t["accent"], 18).pixmap(18, 18))
        h_layout.addWidget(title_icon)

        title_label = QLabel("Settings", header)
        title_label.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {t['text_title']}; font-family: {FONT_FAMILY};"
        )
        h_layout.addWidget(title_label)

        h_layout.addStretch()

        close_btn = QPushButton(header)
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setIcon(get_icon("x", t["text_muted"], 14))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.14);
            }}
        """)
        close_btn.clicked.connect(self.close_requested.emit)
        h_layout.addWidget(close_btn)

        layout.addWidget(header)

        # 2. Theme Selection Section
        theme_section = QWidget(self)
        ts_layout = QVBoxLayout(theme_section)
        ts_layout.setContentsMargins(0, 0, 0, 0)
        ts_layout.setSpacing(8)

        theme_lbl = QLabel("APPEARANCE & THEME", theme_section)
        theme_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {t['text_muted']}; letter-spacing: 0.6px;"
        )
        ts_layout.addWidget(theme_lbl)

        # Theme option cards
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        current_id = self.config_manager.get_theme()

        for theme_id, info in THEMES.items():
            card = QPushButton(theme_section)
            card.setCursor(Qt.PointingHandCursor)
            card.setCheckable(True)
            card.setChecked(theme_id == current_id)
            self.btn_group.addButton(card)

            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(12, 10, 12, 10)
            c_layout.setSpacing(10)

            # Accent color preview circle
            dot = QLabel(card)
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"""
                background-color: {info['accent']};
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            """)
            c_layout.addWidget(dot)

            # Theme Name
            t_name = QLabel(info["name"], card)
            t_name.setStyleSheet(
                f"font-size: 13px; font-weight: 500; color: {t['text_title']}; font-family: {FONT_FAMILY};"
            )
            c_layout.addWidget(t_name)

            c_layout.addStretch()

            # Active indicator
            check_lbl = QLabel(card)
            if theme_id == current_id:
                check_lbl.setPixmap(get_icon("check", info["accent"], 14).pixmap(14, 14))
            c_layout.addWidget(check_lbl)

            card.setStyleSheet(f"""
                QPushButton {{
                    background-color: {info['card']};
                    border: 1px solid {t['border']};
                    border-radius: {RADIUS_BTN}px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    border-color: {info['accent']};
                    background-color: {info['card_hover']};
                }}
                QPushButton:checked {{
                    border: 1.5px solid {info['accent']};
                    background-color: {info['card_active']};
                }}
            """)

            card.clicked.connect(lambda checked, tid=theme_id: self._select_theme(tid))
            ts_layout.addWidget(card)

        layout.addWidget(theme_section)

        # 3. Quick shortcuts & Info Section
        info_section = QWidget(self)
        is_layout = QVBoxLayout(info_section)
        is_layout.setContentsMargins(0, 0, 0, 0)
        is_layout.setSpacing(4)

        info_title = QLabel("KEYBOARD & MOUSE SHORTCUTS", info_section)
        info_title.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {t['text_muted']}; letter-spacing: 0.6px;"
        )
        is_layout.addWidget(info_title)

        tips = [
            "• Click profile button to run locally or over SSH",
            "• Click > arrow to open floating terminal console",
            "• Click ■ red button to stop running program (Ctrl-C)",
            "• Click ✏ pencil to customize commands and parameters",
        ]
        for tip in tips:
            lbl = QLabel(tip, info_section)
            lbl.setStyleSheet(f"font-size: 11.5px; color: {t['text_muted']};")
            is_layout.addWidget(lbl)

        layout.addWidget(info_section)

        # 4. Footer with Done Button
        footer = QWidget(self)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(0, 4, 0, 0)
        f_layout.addStretch()

        done_btn = QPushButton("Done", footer)
        done_btn.setCursor(Qt.PointingHandCursor)
        done_btn.setProperty("class", "PrimaryBtn")
        done_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['accent']};
                color: #080c14;
                border: none;
                border-radius: {RADIUS_BTN}px;
                padding: 8px 24px;
                font-weight: 600;
                font-size: 13px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background-color: {t['accent_hover']};
            }}
        """)
        done_btn.clicked.connect(self.close_requested.emit)
        f_layout.addWidget(done_btn)

        layout.addWidget(footer)

    def _select_theme(self, theme_id: str):
        self.config_manager.set_theme(theme_id)
        theme_manager.set_theme(theme_id)
        self.theme_selected.emit(theme_id)
