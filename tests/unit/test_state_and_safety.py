import numpy as np
import pytest

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.identity.compositor import (
    protected_integrity,
    recover_protected,
    safe_generation_mask,
)
from lumalock.ai.prompt.parser import apply_plan, parse_prompt
from lumalock.core.config import Settings, load_settings, save_settings
from lumalock.core.exceptions import UserError
from lumalock.core.memory_manager import MemoryManager
from lumalock.project.edit_state import EditState
from lumalock.project.history import History


def test_history_branches():
    history = History()
    state = history.state
    state.adjustments.exposure = 0.2
    history.push("Expose", state)
    state.adjustments.temperature = 0.3
    history.push("Warm", state)
    assert history.undo().adjustments.temperature == 0
    state = history.state
    state.adjustments.contrast = 0.2
    history.push("Contrast", state)
    assert len(history.entries) == 3 and history.redo().adjustments.temperature == 0


def test_identity_exclusion_and_recovery(photograph):
    protected = np.zeros(photograph.shape[:2], np.float32)
    protected[30:60, 50:85] = 1
    editable = safe_generation_mask(np.ones_like(protected), protected)
    assert np.count_nonzero(editable[protected > 0]) == 0
    result = recover_protected(photograph, 255 - photograph, protected)
    assert protected_integrity(photograph, result, protected)


def test_oom_retries_cpu():
    attempts = []

    def backend(device, tile):
        attempts.append((device, tile))
        if device != "cpu":
            raise RuntimeError("CUDA out of memory")
        return "recovered"

    assert MemoryManager().run(backend) == "recovered"
    assert attempts == [("cuda", 512), ("cuda", 384), ("cuda", 256), ("cpu", 256)]


def test_oom_failure_is_actionable():
    def backend(device, tile):
        raise RuntimeError("out of memory")

    with pytest.raises(UserError):
        MemoryManager().run(backend)


def test_config_roundtrip(local_storage):
    settings = Settings(preview_size=900)
    save_settings(settings)
    assert load_settings().preview_size == 900


@pytest.mark.parametrize(
    "text,generative",
    [
        ("Brighten my face", False),
        ("Make this warmer", False),
        ("Make the sky blue", False),
        ("Add clouds", True),
        ("Remove the person behind me", True),
        ("Remove noise", False),
    ],
)
def test_prompt_routing(photograph, text, generative):
    plan = parse_prompt(text, analyze(photograph), EditState())
    assert plan.generative.enabled is generative


def test_relative_followup(photograph):
    state = EditState()
    state.adjustments.temperature = 0.4
    plan = parse_prompt("Make it less warm", analyze(photograph), state)
    assert 0 < apply_plan(state, plan).adjustments.temperature < 0.4
