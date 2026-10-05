"""Segmented radiogroup control matching the .schw-seg CSS design."""

from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt
from app.ui.icons import get_icon
from app.ui.styles import (
    PANEL_FILL,
    PANEL_HAIRLINE,
    SURFACE_HOVER,
    TEXT_1,
    TEXT_3,
    ACCENT,
    RADIUS_BTN,
)


class SegmentedControl(QWidget):
    value_changed = Signal(str)

    def __init__(
        self,
        options: List[Dict[str, Any]],
        initial_value: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.options = options
        self._current_value = initial_value or (options[0]["value"] if options else "")
        self.buttons: Dict[str, QPushButton] = {}

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setSpacing(4)

        self.setStyleSheet(f"""
            SegmentedControl {{
                background-color: {PANEL_FILL};
                border: 1px solid {PANEL_HAIRLINE};
                border-radius: {RADIUS_BTN}px;
            }}
        """)

        for opt in self.options:
            val = opt["value"]
            label = opt.get("label", val)
            icon_name = opt.get("icon")

            btn = QPushButton(label, self)
            btn.setCursor(Qt.PointingHandCursor)
            if icon_name:
                btn.setIcon(get_icon(icon_name, TEXT_3, 14))

            btn.clicked.connect(lambda checked=False, v=val: self.set_value(v))
            self.buttons[val] = btn
            self.layout.addWidget(btn)

        self._update_styles()

    def get_value(self) -> str:
        return self._current_value

    def set_value(self, value: str):
        if value == self._current_value:
            return
        self._current_value = value
        self._update_styles()
        self.value_changed.emit(value)

    def _update_styles(self):
        for val, btn in self.buttons.items():
            is_active = (val == self._current_value)
            opt = next((o for o in self.options if o["value"] == val), {})
            icon_name = opt.get("icon")

            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {SURFACE_HOVER};
                        color: {TEXT_1};
                        border: none;
                        border-radius: {RADIUS_BTN - 2}px;
                        padding: 6px 12px;
                        font-weight: 600;
                        font-size: 11px;
                        letter-spacing: 0.3px;
                    }}
                """)
                if icon_name:
                    btn.setIcon(get_icon(icon_name, ACCENT, 14))
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {TEXT_3};
                        border: none;
                        border-radius: {RADIUS_BTN - 2}px;
                        padding: 6px 12px;
                        font-weight: 500;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        color: {TEXT_1};
                    }}
                """)
                if icon_name:
                    btn.setIcon(get_icon(icon_name, TEXT_3, 14))
