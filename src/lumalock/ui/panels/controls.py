"""Shared adjustment controls with signal-blocked state synchronization."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lumalock.project.edit_state import Adjustments

GROUPS = {
    "Basic": ["exposure", "brightness", "contrast", "highlights", "shadows", "whites", "blacks"],
    "Color": ["temperature", "tint", "vibrance", "saturation"],
    "Detail": ["texture", "clarity", "dehaze", "sharpening", "denoise"],
    "Effects": ["vignette", "grain"],
}


class AdjustmentControls(QTabWidget):
    changed = Signal(str, float)
    committed = Signal(str)

    def __init__(self):
        super().__init__()
        self.sliders = {}
        self.labels = {}
        for group, names in GROUPS.items():
            content = QWidget()
            layout = QVBoxLayout(content)
            for name in names:
                row = QHBoxLayout()
                row.addWidget(QLabel(name.replace("_", " ").title()))
                label = QLabel("0")
                row.addStretch()
                row.addWidget(label)
                layout.addLayout(row)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(
                    0
                    if name in ("sharpening", "denoise", "grain")
                    else -300
                    if name == "exposure"
                    else -100,
                    300 if name == "exposure" else 100,
                )
                slider.setSingleStep(1)
                slider.valueChanged.connect(lambda value, key=name: self.emit_change(key, value))
                slider.sliderReleased.connect(lambda key=name: self.committed.emit(key))
                layout.addWidget(slider)
                self.sliders[name], self.labels[name] = slider, label
            layout.addStretch()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content)
            self.addTab(scroll, group)

    def emit_change(self, name, value):
        self.labels[name].setText(f"{value / 100:+.2f} EV" if name == "exposure" else f"{value:+d}")
        self.changed.emit(name, value / 100)

    def sync(self, adjustments: Adjustments):
        for name, value in adjustments.model_dump().items():
            slider = self.sliders[name]
            slider.blockSignals(True)
            slider.setValue(round(value * 100))
            slider.blockSignals(False)
            self.labels[name].setText(
                f"{value:+.2f} EV" if name == "exposure" else f"{round(value * 100):+d}"
            )
