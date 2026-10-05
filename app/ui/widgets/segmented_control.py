"""Apple-style frosted segmented control matching Image 2."""

from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt
from app.ui.icons import get_icon
from app.ui.styles import (
    SLATE_TITLE,
    SLATE_MUTED,
    ACCENT_ORANGE,
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

        # Container matching Image 2: white/frosted rounded pill
        self.setStyleSheet("""
            SegmentedControl {{
                background-color: rgba(255, 255, 255, 0.65);
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 12px;
            }}
        """)

        for opt in self.options:
            val = opt["value"]
            label = opt.get("label", val)

            btn = QPushButton(label, self)
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
                        background-color: #ffffff;
                        color: {SLATE_TITLE};
                        border: 1px solid rgba(0, 0, 0, 0.06);
                        border-radius: 9px;
                        padding: 7px 14px;
                        font-weight: 700;
                        font-size: 13px;
                    }}
                """)
                # In Image 2: SSH icon is orange #ea580c, Ping is dark/accent
                icon_color = ACCENT_ORANGE if val == "ssh" else SLATE_TITLE
                if icon_name:
                    btn.setIcon(get_icon(icon_name, icon_color, 15))
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {SLATE_MUTED};
                        border: none;
                        border-radius: 9px;
                        padding: 7px 14px;
                        font-weight: 500;
                        font-size: 13px;
                    }}
                    QPushButton:hover {{
                        color: {SLATE_TITLE};
                    }}
                """)
                if icon_name:
                    btn.setIcon(get_icon(icon_name, SLATE_MUTED, 15))
