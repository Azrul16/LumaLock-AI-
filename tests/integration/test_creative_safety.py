import cv2
import numpy as np
import pytest

from lumalock.ai.prompt.schema import EditPlan, GenerativeOptions
from lumalock.core.backend_registry import GENERATIVE_BACKENDS
from lumalock.core.exceptions import UserError
from lumalock.core.hardware import Hardware
from lumalock.core.model_manager import ModelManager
from lumalock.pipeline.creative_edit import creative_edit
from lumalock.project.edit_state import EditState, MaskLayer


def test_creative_protection_even_when_backend_ignores_mask(photograph, local_storage, monkeypatch):
    protected = np.zeros(photograph.shape[:2], np.float32)
    protected[30:65, 55:90] = 1
    path = local_storage / "protected.npy"
    np.save(path, protected)
    guard = MaskLayer(
        id="protect", name="Protect", kind="brush", mask_file=str(path), protected=True
    )
    editable = MaskLayer(id="editable", name="Editable", kind="gradient", geometry=[0, 0, 0, 1])
    state = EditState(mode="Creative", masks=[guard, editable])
    seen = []

    class HostileBackend:
        def edit(self, image, prompt, mask, options, cancelled, progress):
            seen.append(mask.copy())
            return np.full_like(image, 240)

    monkeypatch.setitem(GENERATIVE_BACKENDS.factories, "flux", lambda **_: HostileBackend())
    models = ModelManager(Hardware(8, "CPU", 0, "LOW_MEMORY", "3.11", "test"))
    plan = EditPlan(
        intent="content_change", generative=GenerativeOptions(enabled=True, prompt="Add clouds")
    )
    output = creative_edit(
        photograph, state, editable, plan, models, lambda: False, lambda *_: None
    )
    result = cv2.cvtColor(cv2.imread(str(output)), cv2.COLOR_BGR2RGB)
    assert not seen[0][protected > 0].any()
    np.testing.assert_array_equal(result[protected > 0], photograph[protected > 0])


def test_second_creative_edit_keeps_previous_unedited_pixels(
    photograph, local_storage, monkeypatch
):
    prior = photograph.copy()
    prior[:15] = 77
    prior_path = local_storage / "prior.png"
    cv2.imwrite(str(prior_path), cv2.cvtColor(prior, cv2.COLOR_RGB2BGR))
    editable = np.zeros(photograph.shape[:2], np.float32)
    editable[-15:] = 1
    mask_path = local_storage / "editable.npy"
    np.save(mask_path, editable)
    layer = MaskLayer(id="region", name="Region", kind="brush", mask_file=str(mask_path))
    state = EditState(identity_lock=False, mode="Creative", generated_file=str(prior_path))

    class Backend:
        def edit(self, image, prompt, mask, options, cancelled, progress):
            np.testing.assert_array_equal(image, prior)
            return np.full_like(image, 240)

    monkeypatch.setitem(GENERATIVE_BACKENDS.factories, "flux", lambda **_: Backend())
    models = ModelManager(Hardware(8, "CPU", 0, "LOW_MEMORY", "3.11", "test"))
    plan = EditPlan(generative=GenerativeOptions(enabled=True, prompt="Change selected region"))
    output = creative_edit(photograph, state, layer, plan, models, lambda: False, lambda *_: None)
    result = cv2.cvtColor(cv2.imread(str(output)), cv2.COLOR_BGR2RGB)
    np.testing.assert_array_equal(result[editable == 0], prior[editable == 0])
    assert np.all(result[editable > 0] == 240)


def test_missing_generation_model_is_actionable(local_storage):
    from lumalock.ai.generative.flux_backend import FluxBackend

    models = ModelManager(Hardware(8, "CPU", 0, "LOW_MEMORY", "3.11", "test"))
    with pytest.raises(UserError, match="unavailable"):
        FluxBackend(models).edit(
            None, "Add clouds", None, GenerativeOptions(), lambda: False, lambda *_: None
        )
