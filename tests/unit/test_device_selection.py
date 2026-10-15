import pytest

from lumalock.comfy.manager import device_flags, transfer_flags
from lumalock.comfy.progress import ComfyProgress
from lumalock.core.exceptions import UserError


@pytest.mark.parametrize("mode", ["auto", "cuda"])
def test_small_gpu_uses_cuda_vae_before_cpu_fallback(mode):
    flags = device_flags(mode, 4)
    assert "--cpu" not in flags
    assert "--cpu-vae" not in flags
    assert "--novram" in flags  # Model offloading is compatible with CUDA compute.
    assert "--cpu-vae" in device_flags(mode, 4, stronger_offload=True)


def test_cpu_and_missing_gpu_modes_are_explicit():
    assert device_flags("cpu", 4) == ["--cpu", "--cpu-vae"]
    assert device_flags("auto", 0) == ["--cpu", "--cpu-vae"]
    with pytest.raises(UserError, match="no NVIDIA GPU"):
        device_flags("cuda", 0)


def test_stage_reports_selected_device_and_memory_fallback():
    reports = []
    feed = ComfyProgress(
        "http://127.0.0.1:1", lambda *a: reports.append(a), "CUDA selected", "CPU memory fallback"
    )
    feed.handle({"type": "executing", "data": {"node": "5"}})
    assert reports[-1] == (-1, "Encoding your reference photo (CPU memory fallback)")
    feed.handle({"type": "executing", "data": {"node": "6"}})
    assert reports[-1] == (-1, "Encoding your prompt (CUDA selected)")


def test_async_transfers_are_bounded_and_disabled_for_cpu_or_memory_retry():
    assert transfer_flags("auto", 4) == ["--async-offload", "1"]
    assert transfer_flags("cuda", 4) == ["--async-offload", "1"]
    assert transfer_flags("auto", 4, True) == ["--disable-async-offload"]
    assert transfer_flags("cpu", 4) == ["--disable-async-offload"]
    assert transfer_flags("auto", 0) == ["--disable-async-offload"]
