"""Tesla-style segmented control widget."""

from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt
from app.ui.icons import get_icon
from app.ui.styles import (
    TEXT_TITLE,
    TEXT_MUTED,
    ACCENT_CYAN,
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
        self.layout.setSpacing(3)

        # Container: Dark smoked matte well with crisp hairline border
        self.setStyleSheet(f"""
            SegmentedControl {{
                background-color: rgba(10, 12, 16, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: {RADIUS_BTN + 2}px;
            }}
        """)

        for opt in self.options:
            val = opt["value"]
            label = opt.get("label", val)

            btn = QPushButton(label.upper(), self)
            btn.setCursor(Qt.PointingHandCursor)
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
                        background-color: rgba(255, 255, 255, 0.12);
                        color: {TEXT_TITLE};
                        border: 1px solid rgba(255, 255, 255, 0.16);
                        border-radius: {RADIUS_BTN - 1}px;
                        padding: 7px 16px;
                        font-weight: 700;
                        font-size: 11.5px;
                        letter-spacing: 0.8px;
                    }}
                """)
                if icon_name:
                    btn.setIcon(get_icon(icon_name, ACCENT_CYAN, 14))
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {TEXT_MUTED};
                        border: none;
                        border-radius: {RADIUS_BTN - 1}px;
                        padding: 7px 16px;
                        font-weight: 600;
                        font-size: 11.5px;
                        letter-spacing: 0.8px;
                    }}
                    QPushButton:hover {{
                        color: {TEXT_TITLE};
                        background-color: rgba(255, 255, 255, 0.04);
                    }}
                """)
                if icon_name:
                    btn.setIcon(get_icon(icon_name, TEXT_MUTED, 14))
