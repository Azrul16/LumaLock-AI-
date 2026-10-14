"""First-run hardware and optional component selection without hidden downloads."""

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWizard, QWizardPage

from lumalock.core.config import load_settings
from lumalock.core.model_manager import MODEL_SPECS


class FirstRunWizard(QWizard):
    def __init__(self, hardware, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to LumaLock AI")
        self.resize(580, 370)
        welcome = QWizardPage()
        welcome.setTitle("Edit beautifully. Preserve identity.")
        layout = QVBoxLayout(welcome)
        label = QLabel(
            "A local desktop photo editor. Your photographs stay on this device.\n\nThe core editor needs no model downloads and works offline."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.addPage(welcome)
        performance = QWizardPage()
        performance.setTitle("Your computer")
        layout = QVBoxLayout(performance)
        layout.addWidget(
            QLabel(
                f"GPU: {hardware.gpu}\nVRAM: {hardware.vram_gb:g} GB\nRAM: {hardware.ram_gb:g} GB\n\nRecommended profile: {hardware.profile}\nModels load sequentially, with smaller-resolution and CPU retries."
            )
        )
        self.addPage(performance)
        components = QWizardPage()
        components.setTitle("Choose optional AI components")
        layout = QVBoxLayout(components)
        core = QCheckBox("Core editor · ready to use")
        core.setChecked(True)
        core.setEnabled(False)
        layout.addWidget(core)
        self.choices = {}
        for key in ("prompt", "flux"):
            spec = MODEL_SPECS[key]
            checkbox = QCheckBox(f"{spec['name']} · ~{spec['size_gb']} GB")
            checkbox.setChecked(True)
            if hardware.ram_gb < spec["min_ram"] and key == "flux":
                allowed = load_settings().allow_slow_models
                checkbox.setEnabled(allowed)
                checkbox.setText(
                    checkbox.text() + (" · slower offloading" if allowed else " · not recommended")
                )
            layout.addWidget(checkbox)
            self.choices[key] = checkbox
        label = QLabel(
            "Complete model files: about 21.61 GiB. Bundled AI runtime: about 5 GiB. Limit: 30 GiB.\nSelected models download after Finish. No photograph is uploaded.\nYou can install models later in Settings → AI Models."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.addPage(components)
        license_page = QWizardPage()
        license_page.setTitle("FLUX.2-dev license")
        license_layout = QVBoxLayout(license_page)
        license_label = QLabel(
            "FLUX.2-dev uses the FLUX Non-Commercial License. Review the official terms at https://huggingface.co/black-forest-labs/FLUX.2-dev. This application does not grant commercial model rights."
        )
        license_label.setWordWrap(True)
        license_layout.addWidget(license_label)
        self.license = QCheckBox("I acknowledge the FLUX.2-dev non-commercial license")
        self.license.setChecked(load_settings().flux_license_accepted)
        license_layout.addWidget(self.license)
        license_page.registerField("flux_license*", self.license)
        self.addPage(license_page)

    def selected(self):
        return [key for key, choice in self.choices.items() if choice.isChecked()]
