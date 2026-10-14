import time

import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication

from lumalock.ui.main_window import MainWindow


def wait_until(app, predicate, timeout=15):
    start = time.monotonic()
    while not predicate() and time.monotonic() - start < timeout:
        app.processEvents()
        time.sleep(0.005)
    assert predicate(), "GUI task did not finish"


def test_desktop_load_edit_undo_prompt(photograph, local_storage):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    source = local_storage / "source.png"
    Image.fromarray(photograph).save(source)
    window.open_image(source)
    wait_until(app, lambda: window.document is not None and window.task is None)
    original = window.result.copy()
    window.controls.sliders["exposure"].setValue(30)
    window.commit("Exposure")
    wait_until(app, lambda: not window.render_timer.isActive() and window.task is None)
    assert not np.array_equal(window.result, original)
    window.undo()
    wait_until(app, lambda: not window.render_timer.isActive() and window.task is None)
    np.testing.assert_array_equal(window.result, original)
    window.prompt.setPlainText("Make this warmer")
    window.prompt_edit(False)
    wait_until(app, lambda: window.pending_plan is not None and window.task is None)
    window.apply_pending_plan()
    assert window.controls.sliders["temperature"].value() > 0
    window.quick_enhance("Warm light")
    wait_until(app, lambda: window.task is None)
    assert window.state.adjustments.temperature > 0
    window.look_amount.setValue(0)
    wait_until(app, lambda: not window.look_timer.isActive() and window.task is None)
    assert window.state.identity_lock
    window.cancel_task()
    window.pool.waitForDone()
    app.processEvents()
    window.close()
