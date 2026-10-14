"""Zoomable image canvas with pan, split comparison, clipping and mask painting."""

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


def pixmap(pixels):
    pixels = np.ascontiguousarray(pixels, dtype=np.uint8)
    h, w = pixels.shape[:2]
    return QPixmap.fromImage(QImage(pixels.data, w, h, w * 3, QImage.Format.Format_RGB888).copy())


class ImageCanvas(QGraphicsView):
    painted = Signal(float, float, float, bool)
    stroke_finished = Signal()

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.item = self.scene().addPixmap(QPixmap())
        self.original = None
        self.edited = None
        self.overlay = None
        self.split = None
        self.show_original = False
        self.clipping = False
        self.brush = False
        self.brush_radius = 0.04
        self.last_dab = None
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#0c1016"))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_images(self, original, edited, fit=False):
        self.original, self.edited = original, edited
        self.refresh()
        if fit:
            self.fit_image()

    def refresh(self):
        if self.edited is None:
            return
        pixels = (self.original if self.show_original else self.edited).copy()
        if self.split is not None and not self.show_original:
            cutoff = int(pixels.shape[1] * self.split)
            pixels[:, :cutoff] = self.original[:, :cutoff]
        if self.overlay is not None:
            mask = self.overlay[..., None] * 0.45
            pixels = (pixels * (1 - mask) + np.array([65, 175, 255]) * mask).astype(np.uint8)
        if self.clipping:
            pixels[np.all(pixels > 250, axis=2)] = [255, 55, 75]
            pixels[np.all(pixels < 5, axis=2)] = [50, 100, 255]
        self.item.setPixmap(pixmap(pixels))
        self.scene().setSceneRect(self.item.boundingRect())

    def fit_image(self):
        self.fitInView(self.item.boundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def one_to_one(self):
        self.resetTransform()

    def wheelEvent(self, event):
        current = self.transform().m11()
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        if 0.02 < current * factor < 40:
            self.scale(factor, factor)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.show_original = True
            self.refresh()
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.show_original = False
            self.refresh()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def paint_dab(self, event):
        point = self.mapToScene(event.position().toPoint())
        rect = self.item.boundingRect()
        if rect.width() and rect.contains(point):
            x, y = point.x() / rect.width(), point.y() / rect.height()
            erase = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            if self.last_dab is not None:
                start_x, start_y = self.last_dab
                distance = ((x - start_x) ** 2 + (y - start_y) ** 2) ** 0.5
                steps = max(1, int(distance / max(0.001, self.brush_radius * 0.3)))
                for index in range(1, steps):
                    weight = index / steps
                    self.painted.emit(
                        start_x + (x - start_x) * weight,
                        start_y + (y - start_y) * weight,
                        self.brush_radius,
                        erase,
                    )
            self.last_dab = (x, y)
            self.painted.emit(
                x,
                y,
                self.brush_radius,
                bool(event.modifiers() & Qt.KeyboardModifier.AltModifier),
            )

    def mousePressEvent(self, event):
        if self.brush and event.button() == Qt.MouseButton.LeftButton:
            self.last_dab = None
            self.paint_dab(event)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.brush and event.buttons() & Qt.MouseButton.LeftButton:
            self.paint_dab(event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.brush and event.button() == Qt.MouseButton.LeftButton:
            self.last_dab = None
            self.stroke_finished.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def drawForeground(self, painter, rect):
        if self.edited is None:
            painter.setPen(QColor("#8191a6"))
            painter.drawText(
                self.mapToScene(self.viewport().rect()).boundingRect(),
                Qt.AlignmentFlag.AlignCenter,
                "Open a photograph to begin\n\nEdit beautifully. Preserve identity.",
            )
        elif self.split is not None:
            x = self.item.boundingRect().width() * self.split
            painter.setPen(QPen(QColor("#d4e5ff"), 0))
            painter.drawLine(int(x), 0, int(x), int(self.item.boundingRect().height()))
