"""Visible model installation, pause/resume and recoverable errors."""

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from lumalock.core.model_manager import MODEL_SPECS
from lumalock.ui.workers.task import Task


class ModelSetupDialog(QDialog):
    def __init__(self, models, keys, parent=None, verify_only=False):
        super().__init__(parent)
        self.models, self.keys, self.verify_only = models, list(keys), verify_only
        self.setWindowTitle("AI model setup · LumaLock AI")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(640, 310)
        layout = QVBoxLayout(self)
        self.summary = QLabel("Preparing AI models" if not verify_only else "Verifying AI models")
        layout.addWidget(self.summary)
        self.components = QLabel()
        self.components.setWordWrap(True)
        layout.addWidget(self.components)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.detail = QLabel("Checking files…")
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.detail)
        note = QLabel(
            "Files are checked before AI runs. Pause retains partial downloads.\nManual editing remains available without AI models."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QHBoxLayout()
        self.retry = QPushButton("Retry / Resume")
        self.retry.clicked.connect(self.start)
        self.pause = QPushButton("Pause")
        self.pause.clicked.connect(self.pause_download)
        self.done = QPushButton("Continue editing")
        self.done.clicked.connect(self.accept)
        for button in (self.retry, self.pause, self.done):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.task = None
        self.completed = False
        self.refresh()

    def refresh(self):
        self.components.setText(
            "\n".join(
                f"{'Files present' if self.models.installed(key) else 'Download / repair needed'} · {MODEL_SPECS[key]['name']}"
                for key in self.keys
            )
        )

    def start(self):
        if self.task:
            return
        self.completed = False
        self.retry.setEnabled(False)
        self.pause.setEnabled(True)
        self.done.setEnabled(False)
        self.progress.setRange(0, 0)
        self.summary.setText("Verifying models…" if self.verify_only else "Installing AI models…")
        task = Task(self.operation)
        self.task = task
        task.signals.progress.connect(self.update_progress)
        task.signals.result.connect(self.success)
        task.signals.error.connect(self.failure)
        task.signals.finished.connect(self.finished)
        self.pool.start(task)

    def operation(self, cancelled, progress):
        for index, key in enumerate(self.keys):

            def report(value, detail):
                overall = -1 if value < 0 else min(99, int((index * 100 + value) / len(self.keys)))
                progress(overall, f"{MODEL_SPECS[key]['name']}\n{detail}")

            if self.verify_only:
                self.models.verify(key, cancelled, report)
            else:
                self.models.download(key, cancelled, report)
        return True

    def update_progress(self, value, detail):
        self.progress.setRange(0, 0 if value < 0 else 100)
        self.progress.setValue(max(0, value))
        self.detail.setText(detail)

    def success(self, _):
        self.completed = True
        self.summary.setText("AI models ready" if not self.verify_only else "Verification complete")
        self.update_progress(100, "Every required file passed checksum verification.")

    def failure(self, message):
        self.summary.setText(
            "Setup paused" if "paused" in message.lower() else "Setup needs attention"
        )
        self.detail.setText(message)

    def finished(self):
        cancelled = self.task.cancelled.is_set()
        self.task = None
        self.pause.setEnabled(False)
        self.done.setEnabled(True)
        self.retry.setEnabled(not self.completed)
        if cancelled and not self.completed:
            self.summary.setText("Setup paused")
            self.detail.setText("Partial files are saved. Retry / Resume continues the download.")
        if not self.completed:
            self.progress.setRange(0, 100)
        self.refresh()

    def pause_download(self):
        if self.task:
            self.task.cancelled.set()
            self.pause.setEnabled(False)
            self.detail.setText(
                "Pausing safely… Network requests may take up to 15 seconds to stop."
            )

    def reject(self):
        if self.task:
            self.pause_download()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.task:
            self.pause_download()
            event.ignore()
        else:
            event.accept()
