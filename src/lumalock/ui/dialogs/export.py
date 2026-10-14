"""Resolution, compression and metadata options for original-resolution output."""

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QSpinBox

from lumalock.export.exporter import ExportOptions


class ExportDialog(QDialog):
    def __init__(self, size, settings, parent):
        super().__init__(parent)
        self.setWindowTitle("Export photograph")
        form = QFormLayout(self)
        self.preset = QComboBox()
        self.preset.addItems(
            ["Maximum Quality", "Social Media", "Web", "Profile Picture", "Custom"]
        )
        self.width = QSpinBox()
        self.width.setRange(1, 50000)
        self.width.setValue(size[0])
        self.height = QSpinBox()
        self.height.setRange(1, 50000)
        self.height.setValue(size[1])
        self.quality = QSpinBox()
        self.quality.setRange(1, 100)
        self.quality.setValue(settings.export_quality)
        self.metadata = QCheckBox()
        self.metadata.setChecked(settings.preserve_metadata)
        self.ratio = size[0] / size[1]
        self.width.valueChanged.connect(self.sync_height)
        self.preset.currentIndexChanged.connect(self.select_preset)
        for label, widget in [
            ("Preset", self.preset),
            ("Width", self.width),
            ("Height", self.height),
            ("Quality", self.quality),
            ("Preserve metadata", self.metadata),
        ]:
            form.addRow(label, widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.original_size = size

    def sync_height(self, width):
        self.height.setValue(max(1, round(width / self.ratio)))

    def select_preset(self, index):
        if index == 0:
            self.width.setValue(self.original_size[0])
            self.height.setValue(self.original_size[1])
            self.quality.setValue(98)
        elif index in (1, 2):
            longest = 2048 if index == 1 else 1280
            width = round(longest * min(1, self.ratio))
            self.width.setValue(width)
            self.quality.setValue(90 if index == 1 else 85)
        elif index == 3:
            self.width.setValue(1024)
            self.height.setValue(1024)
            self.quality.setValue(95)

    def options(self):
        return ExportOptions(
            width=self.width.value(),
            height=self.height.value(),
            quality=self.quality.value(),
            metadata=self.metadata.isChecked(),
        )
