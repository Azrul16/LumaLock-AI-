import pytest

from lumalock.comfy.progress import ComfyProgress
from lumalock.webapp.progress import JobTiming


def test_stage_estimate_uses_measured_rate_resets_and_expires():
    now = [100.0]
    timer = JobTiming(clock=lambda: now[0])
    assert timer.snapshot() == {"elapsed_seconds": 0, "eta_seconds": None}
    timer.update(20)
    now[0] += 4
    timer.update(40)
    assert timer.snapshot()["eta_seconds"] == 12
    now[0] += 2
    assert timer.snapshot()["eta_seconds"] == 10
    now[0] += 20
    assert timer.snapshot()["eta_seconds"] is None
    timer.update(-1)  # Decoder has no measurable progress; sampling ETA must disappear.
    assert timer.snapshot()["eta_seconds"] is None
    timer.update(0)
    now[0] += 4
    timer.update(20)
    assert timer.snapshot()["eta_seconds"] == 16
    timer.update(5)  # Retry/restart invalidates the old speed estimate.
    assert timer.snapshot()["eta_seconds"] is None
    timer.finish()
    elapsed = timer.snapshot(False)["elapsed_seconds"]
    now[0] += 300
    assert timer.snapshot(False) == {"elapsed_seconds": elapsed, "eta_seconds": None}


@pytest.mark.parametrize("value,maximum", [(1, 0), (9, 8), (-1, 8), ("1", 8)])
def test_invalid_sampling_counts_do_not_fabricate_progress(value, maximum):
    reports = []
    feed = ComfyProgress("http://127.0.0.1:1", lambda *args: reports.append(args))
    feed.handle({"type": "progress", "data": {"node": "14", "value": value, "max": maximum}})
    assert not reports


def test_sampling_progress_comes_from_actual_step_count_not_other_nodes():
    reports = []
    feed = ComfyProgress("http://127.0.0.1:1", lambda *args: reports.append(args))
    feed.handle({"type": "progress", "data": {"node": "5", "value": 3, "max": 8}})
    assert not reports
    feed.handle({"type": "progress", "data": {"node": "14", "value": 3, "max": 8}})
    assert reports == [(37, "Generating image: sampling step 3 of 8")]
    feed.handle({"type": "executing", "data": {"node": "15"}})
    assert reports[-1] == (-1, "Decoding the generated image")
