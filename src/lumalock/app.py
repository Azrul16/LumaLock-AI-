"""Desktop application entry point."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from lumalock.core.logging import configure_logging
from lumalock.ui.main_window import MainWindow
from lumalock.ui.theme import STYLE


def main():
    parser = argparse.ArgumentParser(description="LumaLock AI desktop editor")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Launch the actual window and exit after initialization",
    )
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--open", type=Path)
    args = parser.parse_args()
    configure_logging()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("LumaLock AI")
    app.setOrganizationName("LumaLock")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    if args.open:
        window.open_image(args.open)
    if args.smoke_test:

        def finish():
            if window.task:
                QTimer.singleShot(100, finish)
                return
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(args.screenshot))
            print("Desktop launch smoke test passed", flush=True)
            window.close()
            app.quit()

        QTimer.singleShot(500, finish)
    elif not window.settings.first_run_done:
        from lumalock.core.config import save_settings
        from lumalock.ui.dialogs.first_run import FirstRunWizard

        wizard = FirstRunWizard(window.hardware, window)
        if wizard.exec():
            window.settings.first_run_done = True
            window.settings.flux_license_accepted = wizard.license.isChecked()
            save_settings(window.settings)
            window.models.settings = window.settings
            chosen = wizard.selected()
            if chosen:
                window.settings.ai_setup_requested = chosen
                save_settings(window.settings)
                window.setup_models(chosen)
    elif window.settings.ai_setup_requested:
        missing = [
            key for key in window.settings.ai_setup_requested if not window.models.installed(key)
        ]
        if missing:
            window.setup_models(missing)
    return app.exec()
