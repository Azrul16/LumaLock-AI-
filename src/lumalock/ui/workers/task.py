"""Cancellable jobs with GUI-thread signal delivery and single-worker scheduling."""

import logging
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal

from lumalock.core.exceptions import Cancelled, UserError


class TaskSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)
    finished = Signal()


class Task(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.signals = TaskSignals()
        self.operation = operation
        self.cancelled = Event()

    def run(self):
        try:
            if self.cancelled.is_set():
                return
            result = self.operation(self.cancelled.is_set, self.signals.progress.emit)
            if not self.cancelled.is_set():
                self.signals.result.emit(result)
        except (UserError, Cancelled) as exc:
            self.signals.error.emit(str(exc))
        except Exception:
            logging.getLogger("lumalock.tasks").exception("Background operation failed")
            self.signals.error.emit(
                "The operation failed. Check Help → System Information and the local log for technical details."
            )
        finally:
            self.signals.finished.emit()
