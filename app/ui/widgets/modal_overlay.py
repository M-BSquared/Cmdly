"""In-app frosted glass modal overlay container."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFrame,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QMouseEvent
from app.ui.styles import FROSTED_OVERLAY


class ModalOverlay(QWidget):
    dismiss_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.pinned = False
        self._content_widget: Optional[QWidget] = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setAlignment(Qt.AlignCenter)

        self.hide()

    def show_content(self, widget: QWidget, pinned: bool = False):
        self.pinned = pinned
        self.clear_content()

        self._content_widget = widget

        # Soft drop shadow for floating modal effect
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(36)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 10)
        widget.setGraphicsEffect(shadow)

        self.layout.addWidget(widget)
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    def clear_content(self):
        if self._content_widget:
            self.layout.removeWidget(self._content_widget)
            self._content_widget.hide()
            self._content_widget = None

    def dismiss(self):
        if not self.pinned:
            self.clear_content()
            self.hide()
            self.dismiss_requested.emit()

    def mousePressEvent(self, event: QMouseEvent):
        # Click outside modal card dismisses overlay if not pinned
        if not self.pinned and self._content_widget:
            child_pos = self._content_widget.mapFrom(self, event.pos())
            if not self._content_widget.rect().contains(child_pos):
                self.dismiss()
                return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(15, 23, 42, 85))  # Smooth frosted backdrop tint

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())
