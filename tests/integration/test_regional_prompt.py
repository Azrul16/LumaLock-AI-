import cv2
import numpy as np

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.segmentation.segmentation_manager import SegmentationManager
from lumalock.core.hardware import Hardware
from lumalock.core.model_manager import ModelManager
from lumalock.pipeline.prompt_edit import prepare_prompt
from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import EditState


def test_prompt_creates_real_subject_mask(local_storage):
    image = np.full((180, 220, 3), [25, 65, 100], np.uint8)
    cv2.ellipse(image, (110, 95), (40, 65), 0, 0, 360, (120, 65, 30), -1)
    models = ModelManager(Hardware(8, "CPU", 0, "LOW_MEMORY", "3.11", "test"))
    segmentation = SegmentationManager(models)
    prepared = prepare_prompt(
        "Brighten me",
        image,
        analyze(image),
        EditState(),
        models,
        segmentation,
        lambda: False,
        lambda *_: None,
    )
    assert prepared.state.masks[0].kind == "subject"
    assert prepared.state.masks[0].adjustments.exposure > 0
    rendered = render(image, prepared.state)
    assert rendered[95, 110].mean() > image[95, 110].mean()
    np.testing.assert_array_equal(rendered[5, 5], image[5, 5])
