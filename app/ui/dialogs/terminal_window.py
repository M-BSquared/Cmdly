"""Tabbed Terminal Window for viewing and interacting with live sessions."""

from typing import Dict, Optional
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, Signal
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui.styles import (
    SURFACE_BG,
    SURFACE_CARD,
    SURFACE_HOVER,
    BORDER_SOFT,
    TEXT_1,
    TEXT_2,
    RADIUS_BTN,
)


class TerminalWindow(QMainWindow):
    session_input = Signal(str, str)        # (session_id, input_data)
    session_interrupt = Signal(str)         # (session_id)
    session_close = Signal(str)             # (session_id)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Cmdly Terminal")
        self.resize(750, 480)
        self.tabs: Dict[str, TerminalWidget] = {}

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        self.tab_widget = QTabWidget(central)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)

        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS_BTN}px;
                background-color: {SURFACE_CARD};
            }}
            QTabBar::tab {{
                background-color: {SURFACE_BG};
                color: {TEXT_2};
                padding: 6px 14px;
                margin-right: 4px;
                border-top-left-radius: {RADIUS_BTN}px;
                border-top-right-radius: {RADIUS_BTN}px;
                font-weight: 500;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background-color: {SURFACE_CARD};
                color: {TEXT_1};
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                background-color: {SURFACE_HOVER};
            }}
        """)

        layout.addWidget(self.tab_widget)
        self.setCentralWidget(central)

    def ensure_tab(self, session_id: str, title: str) -> TerminalWidget:
        if session_id in self.tabs:
            widget = self.tabs[session_id]
            idx = self.tab_widget.indexOf(widget)
            if idx >= 0:
                self.tab_widget.setCurrentIndex(idx)
            return widget

        term_widget = TerminalWidget(title, self)
        term_widget.send_input.connect(lambda data, sid=session_id: self.session_input.emit(sid, data))
        term_widget.send_interrupt.connect(lambda sid=session_id: self.session_interrupt.emit(sid))
        term_widget.close_requested.connect(lambda sid=session_id: self._close_session(sid))

        self.tabs[session_id] = term_widget
        idx = self.tab_widget.addTab(term_widget, title)
        self.tab_widget.setCurrentIndex(idx)
        return term_widget

    def append_output(self, session_id: str, text: str):
        if session_id in self.tabs:
            self.tabs[session_id].append_output(text)

    def remove_tab(self, session_id: str):
        if session_id in self.tabs:
            widget = self.tabs.pop(session_id)
            idx = self.tab_widget.indexOf(widget)
            if idx >= 0:
                self.tab_widget.removeTab(idx)
            widget.deleteLater()

        if self.tab_widget.count() == 0:
            self.hide()

    def _on_tab_close_requested(self, index: int):
        widget = self.tab_widget.widget(index)
        for sid, w in list(self.tabs.items()):
            if w == widget:
                self._close_session(sid)
                break

    def _close_session(self, session_id: str):
        self.session_close.emit(session_id)
        self.remove_tab(session_id)
