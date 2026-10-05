"""Modern iOS/Desktop toggle switch widget."""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, Property, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from app.ui.styles import ACCENT, BORDER_SOFT, TEXT_3, PANEL_FILL


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: QWidget = None):
        super().__init__(parent)
        self._checked = checked
        self._thumb_position = 1.0 if checked else 0.0
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(140)

    @Property(float)
    def thumb_position(self) -> float:
        return self._thumb_position

    @thumb_position.setter
    def thumb_position(self, pos: float):
        self._thumb_position = pos
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked == checked:
            return
        self._checked = checked
        self._anim.stop()
        self._anim.setStartValue(self._thumb_position)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()
        self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        radius = h / 2.0

        # Background Track
        track_color = QColor(ACCENT) if self._checked else QColor(PANEL_FILL)
        border_color = QColor(ACCENT) if self._checked else QColor(BORDER_SOFT)

        painter.setBrush(track_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)

        # Thumb
        thumb_diameter = h - 6
        x_min = 3.0
        x_max = w - thumb_diameter - 3.0
        x = x_min + self._thumb_position * (x_max - x_min)
        y = 3.0

        thumb_color = QColor("#ffffff") if self._checked else QColor(TEXT_3)
        painter.setBrush(thumb_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(x, y, thumb_diameter, thumb_diameter))
