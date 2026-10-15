import numpy as np
import pytest
from skimage import data

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.segmentation.segmentation_manager import SegmentationManager
from lumalock.core.config import Settings
from lumalock.core.hardware import Hardware
from lumalock.core.model_manager import ModelManager
from lumalock.core.quality import creative_quality
from lumalock.pipeline.smart_enhance import smart_enhance
from lumalock.project.edit_state import EditState


def test_quality_changes_real_inference_work():
    settings = Settings(quality_mode="Maximum")
    assert creative_quality(settings).steps == 50 and creative_quality(settings).resolution == 1536
    settings.creative_resolution = 1536
    assert creative_quality(settings).resolution == 1536
    settings.quality_mode = "Preview"
    assert creative_quality(settings).steps == 12 and creative_quality(settings).resolution == 512
    settings.quality_mode = "Quality"
    assert creative_quality(settings).steps == 40 and creative_quality(settings).resolution == 1024


def test_portrait_amount_zero_and_identity_lock(local_storage):
    image = data.astronaut()
    original = image.copy()
    manager = ModelManager(Hardware(8, "CPU", 0, "LOW_MEMORY", "3.11", "test"))
    segmentation = SegmentationManager(manager)
    result = smart_enhance(
        image, EditState(), analyze(image, regions=True), segmentation, "Portrait", 0
    )
    np.testing.assert_array_equal(result.pixels, original)
    assert result.state.identity_lock and result.state.generated_file is None
    assert any(layer.kind == "face" for layer in result.state.masks)
    stronger = smart_enhance(
        image, EditState(), analyze(image, regions=True), segmentation, "Portrait", 0.75
    )
    assert not np.array_equal(stronger.pixels, original)
    assert stronger.pixels.shape == original.shape
    np.testing.assert_array_equal(image, original)


def test_unknown_recipe_is_actionable(photograph, local_storage):
    from lumalock.core.exceptions import UserError

    with pytest.raises(UserError, match="recipe"):
        smart_enhance(photograph, EditState(), analyze(photograph), None, "imaginary")
