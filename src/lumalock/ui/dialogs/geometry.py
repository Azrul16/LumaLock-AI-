"""Conventional framing controls stored as reversible project parameters."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
)

from lumalock.project.edit_state import Geometry


class GeometryDialog(QDialog):
    def __init__(self, geometry, size, parent):
        super().__init__(parent)
        self.setWindowTitle("Crop and geometry")
        self.size = size
        self.turns = geometry.quarter_turns
        layout = QFormLayout(self)
        self.aspect = QComboBox()
        self.aspect.addItems(["Free / custom", "1:1", "4:5", "3:2", "16:9", "9:16"])
        layout.addRow("Crop ratio", self.aspect)
        self.crop = []
        for label, value in zip(["Left", "Top", "Width", "Height"], geometry.crop or [0, 0, 1, 1]):
            spin = QDoubleSpinBox()
            spin.setRange(0, 1)
            spin.setDecimals(3)
            spin.setSingleStep(0.01)
            spin.setValue(value)
            self.crop.append(spin)
            layout.addRow(label + " (fraction)", spin)
        self.rotation = QComboBox()
        self.rotation.addItems(["0°", "90° left", "180°", "90° right"])
        self.rotation.setCurrentIndex(self.turns)
        layout.addRow("Rotation", self.rotation)
        self.straighten = QDoubleSpinBox()
        self.straighten.setRange(-45, 45)
        self.straighten.setSingleStep(0.1)
        self.straighten.setValue(geometry.straighten)
        layout.addRow("Straighten (degrees)", self.straighten)
        self.horizontal = QCheckBox()
        self.horizontal.setChecked(geometry.flip_horizontal)
        self.vertical = QCheckBox()
        self.vertical.setChecked(geometry.flip_vertical)
        layout.addRow("Flip horizontal", self.horizontal)
        layout.addRow("Flip vertical", self.vertical)
        self.aspect.currentIndexChanged.connect(self.set_aspect)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def set_aspect(self, index):
        if not index:
            return
        desired = [1, 4 / 5, 3 / 2, 16 / 9, 9 / 16][index - 1]
        width, height = self.size
        if self.rotation.currentIndex() % 2:
            width, height = height, width
        actual = width / height
        cw, ch = (desired / actual, 1) if actual > desired else (1, actual / desired)
        for spin, value in zip(self.crop, [(1 - cw) / 2, (1 - ch) / 2, cw, ch]):
            spin.setValue(value)

    def geometry(self):
        return Geometry(
            crop=[spin.value() for spin in self.crop],
            quarter_turns=self.rotation.currentIndex(),
            straighten=self.straighten.value(),
            flip_horizontal=self.horizontal.isChecked(),
            flip_vertical=self.vertical.isChecked(),
        )
