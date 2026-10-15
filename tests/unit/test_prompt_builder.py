import builtins

import numpy as np
import pytest

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.prompt.presets import PRESETS, preset_prompt
from lumalock.ai.prompt.prompt_builder import (
    auto_enhance_prompt,
    build_edit_plan,
    build_flux_prompt,
)
from lumalock.core.exceptions import UserError
from lumalock.project.edit_state import EditState


def test_natural_and_explicit_creative_modes_preserve_the_request():
    request = "Remove the person behind me."
    natural = build_flux_prompt(request, "Natural")
    creative = build_flux_prompt(request, "Creative")
    assert request in natural and request in creative
    assert "Do not introduce" in natural
    assert "creative transformation" in creative
    assert "creative transformation" not in natural


def test_identity_and_protected_requirements_are_automatic():
    assert "IDENTITY PRESERVATION REQUIREMENT" in build_flux_prompt("Warm light")
    assert "IDENTITY PRESERVATION REQUIREMENT" not in build_flux_prompt(
        "Warm light", identity_lock=False
    )
    assert "Original protected pixels" in build_flux_prompt("Warm light", protected_regions=True)


def test_bangla_unicode_preserved_without_model_imports(monkeypatch):
    original = builtins.__import__

    def no_neural_import(name, *args, **kwargs):
        if name.split(".")[0] in ("torch", "transformers", "llama_cpp"):
            raise AssertionError("Prompt construction must not load a neural runtime")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_neural_import)
    request = "ছবিটা বিকেলের মতো করে দাও, আলোটা সুন্দর করো।"
    assert request in build_flux_prompt(request)


@pytest.mark.parametrize("user_text", ["", "  ", None])
def test_empty_prompt_is_rejected(user_text):
    with pytest.raises(UserError):
        build_flux_prompt(user_text)


def test_presets_are_text_and_dramatic_sky_respects_mode():
    assert len(PRESETS) == 12
    for name in PRESETS:
        assert preset_prompt(name) in build_flux_prompt("Apply preset", preset=name)
    assert "Do not replace" in preset_prompt("Dramatic Sky", "Natural")
    assert "modifying realistic cloud" in preset_prompt("Dramatic Sky", "Creative")


def test_auto_enhance_uses_real_image_statistics():
    analysis = analyze(np.full((64, 64, 3), 20, dtype=np.uint8))
    prompt = auto_enhance_prompt(analysis)
    assert "underexposure" in prompt and "contrast" in prompt
    plan = build_edit_plan("Auto enhance", analysis, EditState())
    assert prompt in plan.generative.prompt
    assert plan.generative.enabled
