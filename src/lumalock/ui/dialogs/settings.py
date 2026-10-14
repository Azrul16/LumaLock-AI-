"""Editable local preferences, hardware information and optional model lifecycle."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lumalock.core.config import save_settings
from lumalock.core.model_manager import MODEL_SPECS


class SettingsDialog(QDialog):
    def __init__(self, settings, models, parent):
        super().__init__(parent)
        self.setWindowTitle("Settings · LumaLock AI")
        self.resize(760, 430)
        self.settings = settings
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        general = QWidget()
        form = QFormLayout(general)
        self.preview = QSpinBox()
        self.preview.setRange(256, 4096)
        self.preview.setValue(settings.preview_size)
        self.tile = QSpinBox()
        self.tile.setRange(128, 1024)
        self.tile.setValue(settings.tile_size)
        self.quality = QSpinBox()
        self.quality.setRange(1, 100)
        self.quality.setValue(settings.export_quality)
        self.identity = QCheckBox()
        self.identity.setChecked(settings.identity_lock)
        self.expansion = QDoubleSpinBox()
        self.expansion.setRange(0, 1)
        self.expansion.setSingleStep(0.05)
        self.expansion.setValue(settings.face_expansion)
        self.metadata = QCheckBox()
        self.metadata.setChecked(settings.preserve_metadata)
        self.autosave = QCheckBox()
        self.autosave.setChecked(settings.autosave)
        self.device = QComboBox()
        self.device.addItems(["auto", "cpu", "cuda"])
        self.device.setCurrentText(settings.device)
        self.fp16 = QCheckBox()
        self.fp16.setChecked(settings.use_fp16)
        self.slow = QCheckBox()
        self.slow.setChecked(settings.allow_slow_models)
        self.backend = QComboBox()
        self.backend.addItems(["flux"])
        self.backend.setCurrentText(settings.generative_backend)
        for label, widget in [
            ("Preview longest edge", self.preview),
            ("Photographic tile size", self.tile),
            ("Export quality", self.quality),
            ("Identity Lock default", self.identity),
            ("Face protection margin", self.expansion),
            ("Preserve export metadata", self.metadata),
            ("Autosave project every minute", self.autosave),
            ("Inference device", self.device),
            ("FP16 on supported GPU", self.fp16),
            ("Allow slower heavy models with offloading", self.slow),
            ("Creative backend", self.backend),
        ]:
            form.addRow(label, widget)
        form.addRow(
            QLabel(
                f"Hardware profile: {models.hardware.profile}\nQwen unloads before FLUX; low-memory FLUX retries use smaller dimensions."
            )
        )
        tabs.addTab(general, "Preferences")
        ai = QWidget()
        ailayout = QVBoxLayout(ai)
        ailayout.addWidget(
            QLabel(
                "Downloads fetch model files only. Photographs stay on this device.\nSizes below are estimates; the download checks actual repository size and free space."
            )
        )
        table = QTableWidget(len(MODEL_SPECS), 4)
        self.model_table = table
        table.setHorizontalHeaderLabels(["Model", "Status", "Estimated disk", "Action"])
        for row, (key, spec) in enumerate(MODEL_SPECS.items()):
            table.setItem(row, 0, QTableWidgetItem(spec["name"]))
            status = "Installed" if models.installed(key) else "Not installed"
            if models.installed(key) and not models.available(key):
                status = "Installed; inference dependencies missing"
            if models.hardware.ram_gb < spec["min_ram"] and key == "flux":
                status = (
                    "Slow offloading required"
                    if settings.allow_slow_models
                    else "Not recommended on this computer"
                )
            table.setItem(row, 1, QTableWidgetItem(status))
            table.setItem(row, 2, QTableWidgetItem(f"~{spec['size_gb']} GB"))
            actions = QWidget()
            buttons = QHBoxLayout(actions)
            buttons.setContentsMargins(0, 0, 0, 0)
            for label, callback in [
                ("Download / Repair", lambda k=key: parent.download_model(k)),
                ("Verify", lambda k=key: parent.verify_model(k)),
                ("Remove", lambda k=key: parent.remove_model(k)),
            ]:
                button = QPushButton(label)
                button.clicked.connect(
                    lambda checked=False, action=callback: self.model_action(action)
                )
                buttons.addWidget(button)
            table.setCellWidget(row, 3, actions)
        table.resizeColumnsToContents()
        table.setColumnWidth(3, 245)
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1000)
        self.status_timer.timeout.connect(lambda: self.refresh_models(models))
        self.status_timer.start()
        ailayout.addWidget(table)
        ailayout.addWidget(
            QLabel(
                "Only Qwen and FLUX are supported. The FLUX bundle includes its required encoder and VAE."
            )
        )
        tabs.addTab(ai, "AI Models")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def refresh_models(self, models):
        for row, key in enumerate(MODEL_SPECS):
            status = (
                "Files complete · Verify to check integrity"
                if models.installed(key)
                else "Missing or incomplete · Download / Repair"
            )
            if models.installed(key) and not models.available(key):
                status = "Runtime missing · repair app folder"
            self.model_table.item(row, 1).setText(status)

    def model_action(self, action):
        self.save()
        action()

    def save(self):
        self.settings.preview_size = self.preview.value()
        self.settings.tile_size = self.tile.value()
        self.settings.export_quality = self.quality.value()
        self.settings.identity_lock = self.identity.isChecked()
        self.settings.face_expansion = self.expansion.value()
        self.settings.preserve_metadata = self.metadata.isChecked()
        self.settings.autosave = self.autosave.isChecked()
        self.settings.device = self.device.currentText()
        self.settings.use_fp16 = self.fp16.isChecked()
        self.settings.allow_slow_models = self.slow.isChecked()
        self.settings.generative_backend = self.backend.currentText()
        save_settings(self.settings)
        self.accept()
