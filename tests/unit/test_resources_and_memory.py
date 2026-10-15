import io
from types import SimpleNamespace

import numpy as np
from PIL import Image

from lumalock.comfy.workflow import build_workflow
from lumalock.imaging.masks import blend, blend_uint8
from lumalock.webapp.previews import PreviewCache
from lumalock.webapp.resources import ResourceMonitor, gpu_sample


def test_strip_compositing_is_pixel_identical_and_preserves_inputs():
    rng = np.random.default_rng(42)
    first = rng.integers(0, 256, (275, 321, 3), dtype=np.uint8)
    second = rng.integers(0, 256, first.shape, dtype=np.uint8)
    mask = rng.random(first.shape[:2], dtype=np.float32)
    original = first.copy()
    expected = (
        blend(first.astype(np.float32), second.astype(np.float32), mask).round().astype(np.uint8)
    )
    np.testing.assert_array_equal(blend_uint8(first, second, mask), expected)
    np.testing.assert_array_equal(first, original)


def test_low_memory_vae_preserves_sampling_work_and_reference_connections():
    args = ("reference.png", "Edit", 1024, 1024, 60, 0.45, 123)
    normal, tiled = build_workflow(*args), build_workflow(*args, low_memory=True)
    assert tiled["5"]["class_type"] == "VAEEncodeTiled"
    assert tiled["15"]["class_type"] == "VAEDecodeTiled"
    assert tiled["5"]["inputs"]["pixels"] == normal["5"]["inputs"]["pixels"]
    assert tiled["15"]["inputs"]["samples"] == normal["15"]["inputs"]["samples"]
    for key in normal.keys() - {"5", "15"}:
        assert tiled[key] == normal[key]


def test_gpu_readings_support_na_and_never_import_torch(monkeypatch):
    import subprocess

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout='"Test, GPU", 73, 2048, 4096, N/A\n'
        ),
    )
    assert gpu_sample() == {
        "name": "Test, GPU",
        "percent": 73.0,
        "used_mib": 2048.0,
        "total_mib": 4096.0,
        "temperature_c": None,
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    assert gpu_sample() is None


def test_disk_rates_are_measured_and_cached_not_capacity_percent(tmp_path, monkeypatch):
    from lumalock.webapp import resources

    times = iter((10.0, 12.0))
    counters = iter(
        (
            SimpleNamespace(read_bytes=100, write_bytes=200),
            SimpleNamespace(read_bytes=100 + 4 * 1024**2, write_bytes=200 + 2 * 1024**2),
        )
    )
    gpu_calls = []
    monkeypatch.setattr(resources.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(resources, "gpu_sample", lambda: gpu_calls.append(1))
    monkeypatch.setattr(resources.psutil, "disk_io_counters", lambda: next(counters))
    monitor = ResourceMonitor(tmp_path)
    monitor.collect()
    assert monitor.snapshot()["disk_read_mib_s"] is None
    monitor.collect()
    sample = monitor.snapshot()
    assert sample["disk_read_mib_s"] == 2
    assert sample["disk_write_mib_s"] == 1
    assert len(gpu_calls) == 1  # GPU probe is throttled and snapshots never spawn processes.
    for _ in range(10):
        monitor.snapshot()
    assert len(gpu_calls) == 1


def test_display_previews_are_bounded_originals_untouched_and_lru_evicts(tmp_path):
    image = np.random.default_rng(1).integers(0, 256, (512, 768, 3), dtype=np.uint8)
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    Image.fromarray(image).save(first)
    Image.fromarray(255 - image).save(second)
    original = first.read_bytes()
    cache = PreviewCache()
    thumbnail = cache.get(first, 320)
    assert Image.open(io.BytesIO(thumbnail)).size == (320, 213)
    assert cache.get(first, 320) is thumbnail
    cache.limit = len(thumbnail)
    cache.get(second, 320)
    assert cache.size <= cache.limit
    assert len(cache.items) <= 1
    assert first.read_bytes() == original
