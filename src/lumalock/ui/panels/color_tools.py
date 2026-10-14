"""HSL controls and editable five-point tone curves."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QWidget

from lumalock.project.edit_state import HSL_COLORS


class ColorTools(QWidget):
    hsl_changed = Signal(str, object)
    curve_changed = Signal(str, object)

    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.color = QComboBox()
        self.color.addItems(HSL_COLORS)
        form.addRow("HSL color", self.color)
        self.hsl = []
        for label in ("Hue", "Saturation", "Luminance"):
            spin = QDoubleSpinBox()
            spin.setRange(-1, 1)
            spin.setSingleStep(0.05)
            spin.setDecimals(2)
            spin.valueChanged.connect(self.emit_hsl)
            self.hsl.append(spin)
            form.addRow(label, spin)
        self.channel = QComboBox()
        self.channel.addItems(["master", "red", "green", "blue"])
        form.addRow(QLabel("Tone curve · input → output"))
        form.addRow("Channel", self.channel)
        self.points = []
        for x in (0, 0.25, 0.5, 0.75, 1):
            spin = QDoubleSpinBox()
            spin.setRange(0, 1)
            spin.setSingleStep(0.025)
            spin.setDecimals(3)
            spin.setValue(x)
            spin.valueChanged.connect(self.emit_curve)
            self.points.append(spin)
            form.addRow(f"{x:.2f}", spin)
        self.color.currentIndexChanged.connect(self.sync_selection)
        self.channel.currentIndexChanged.connect(self.sync_selection)
        self.state = None

    def sync(self, state):
        self.state = state
        self.sync_selection()

    def sync_selection(self):
        if self.state is None:
            return
        values = self.state.hsl.get(self.color.currentText(), [0, 0, 0])
        for spin, value in zip(self.hsl, values):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        points = self.state.curves.get(
            self.channel.currentText(), [[x, x] for x in (0, 0.25, 0.5, 0.75, 1)]
        )
        import numpy as np

        inputs, outputs = np.array(points).T
        for spin, x in zip(self.points, (0, 0.25, 0.5, 0.75, 1)):
            spin.blockSignals(True)
            spin.setValue(float(np.interp(x, inputs, outputs)))
            spin.blockSignals(False)

    def emit_hsl(self):
        self.hsl_changed.emit(self.color.currentText(), [spin.value() for spin in self.hsl])

    def emit_curve(self):
        self.curve_changed.emit(
            self.channel.currentText(),
            [[x, spin.value()] for x, spin in zip((0, 0.25, 0.5, 0.75, 1), self.points)],
        )
