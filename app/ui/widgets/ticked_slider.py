"""Tesla-style precision touchscreen slider widget."""

from typing import List
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QMouseEvent, QRadialGradient
from app.ui.styles import ACCENT_CYAN, TEXT_MUTED, TEXT_TITLE


class TickedSlider(QWidget):
    value_changed = Signal(int)

    def __init__(self, steps: List[int], initial_value: int, parent: QWidget = None):
        super().__init__(parent)
        self.steps = steps
        self._current_index = self.steps.index(initial_value) if initial_value in self.steps else 0
        self.setMinimumHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        self._dragging = False

    def value(self) -> int:
        return self.steps[self._current_index]

    def setValue(self, val: int):
        if val in self.steps:
            idx = self.steps.index(val)
            if idx != self._current_index:
                self._current_index = idx
                self.update()
                self.value_changed.emit(self.value())

    def setIndex(self, idx: int):
        if 0 <= idx < len(self.steps) and idx != self._current_index:
            self._current_index = idx
            self.update()
            self.value_changed.emit(self.value())

    def _get_step_x(self, idx: int, w: float, margin: float) -> float:
        total = len(self.steps)
        if total <= 1:
            return margin
        usable = w - 2 * margin
        return margin + (idx / (total - 1)) * usable

    def _get_nearest_index(self, mouse_x: float) -> int:
        w = float(self.width())
        margin = 16.0
        best_idx = 0
        best_dist = float("inf")
        for i in range(len(self.steps)):
            x = self._get_step_x(i, w, margin)
            dist = abs(mouse_x - x)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        return best_idx

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            idx = self._get_nearest_index(event.position().x())
            self.setIndex(idx)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            idx = self._get_nearest_index(event.position().x())
            self.setIndex(idx)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        margin = 16.0
        track_y = 13.0
        track_h = 4.0
        total = len(self.steps)

        # 1. Base Inactive Track (Smoked dark line)
        start_x = self._get_step_x(0, w, margin)
        end_x = self._get_step_x(total - 1, w, margin)
        current_x = self._get_step_x(self._current_index, w, margin)

        painter.setBrush(QColor(255, 255, 255, 30))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(start_x, track_y - track_h / 2.0, end_x - start_x, track_h), 2, 2)

        # 2. Active Track (Electric Tesla Cyan)
        if current_x > start_x:
            painter.setBrush(QColor(ACCENT_CYAN))
            painter.drawRoundedRect(QRectF(start_x, track_y - track_h / 2.0, current_x - start_x, track_h), 2, 2)

        # 3. Precision Tick Marks & Step Labels
        font_labels = QFont("-apple-system", 9)
        font_labels.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)
        painter.setFont(font_labels)

        for i, step in enumerate(self.steps):
            x = self._get_step_x(i, w, margin)

            # Precision notch on track
            notch_color = QColor(255, 255, 255, 200) if i <= self._current_index else QColor(255, 255, 255, 70)
            painter.setPen(QPen(notch_color, 1.5))
            painter.drawLine(QPointF(x, track_y - 2.5), QPointF(x, track_y + 2.5))

            # Step label text below
            label_text = f"{step}S"
            is_active = (i == self._current_index)

            if is_active:
                painter.setPen(QColor(ACCENT_CYAN))
                font_labels.setBold(True)
                painter.setFont(font_labels)
            else:
                painter.setPen(QColor(TEXT_MUTED))
                font_labels.setBold(False)
                painter.setFont(font_labels)

            text_rect = QRectF(x - 22, track_y + 9, 44, 20)
            painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop, label_text)

        # 4. Thumb: Luminous Cyan Glow & White Core Disc
        # Subtle glow ring
        glow_radius = 11.0
        painter.setBrush(QColor(56, 189, 248, 45))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(current_x, track_y), glow_radius, glow_radius)

        # Core Thumb
        thumb_radius = 6.5
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor(ACCENT_CYAN), 2.0))
        painter.drawEllipse(QPointF(current_x, track_y), thumb_radius, thumb_radius)
