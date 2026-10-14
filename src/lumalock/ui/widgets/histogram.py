"""Cached RGB and luminance histograms; changing views never triggers inference."""

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class Histogram(QWidget):
    def __init__(self):
        super().__init__()
        self.values = []
        self.setMinimumHeight(100)
        self.setMaximumHeight(120)

    def set_histogram(self, values):
        self.values = values
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101722"))
        for values, color in zip(self.values, ["#ff636c", "#56d298", "#659eff", "#d3dce7"]):
            counts = np.log1p(np.asarray(values))
            counts /= max(1, float(counts.max()))
            path = QPainterPath()
            for index, value in enumerate(counts):
                point = QPointF(index * self.width() / 255, self.height() * (1 - value * 0.9))
                path.moveTo(point) if index == 0 else path.lineTo(point)
            painter.setPen(QPen(QColor(color), 1))
            painter.drawPath(path)
