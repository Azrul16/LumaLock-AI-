import cv2
import numpy as np

from lumalock.ai.segmentation.segmentation_manager import (
    SegmentationManager,
    classical_subject_mask,
    sky_mask,
)
from lumalock.core.hardware import Hardware
from lumalock.core.model_manager import ModelManager


def test_real_classical_segmentation():
    image = np.full((180, 220, 3), [25, 60, 100], np.uint8)
    cv2.ellipse(image, (110, 95), (40, 65), 0, 0, 360, (200, 80, 35), -1)
    mask = classical_subject_mask(image)
    assert mask[95, 110] > 0.9 and mask[5, 5] < 0.1


def test_sky_is_top_connected():
    image = np.full((100, 100, 3), [90, 55, 20], np.uint8)
    image[:30] = [80, 150, 240]
    image[70:85, 60:80] = [80, 150, 240]
    mask = sky_mask(image)
    assert mask[10, 10] > 0.9 and mask[75, 65] < 0.1


def test_mask_cache(local_storage):
    image = np.full((160, 160, 3), [30, 70, 90], np.uint8)
    cv2.circle(image, (80, 80), 35, (200, 50, 20), -1)
    models = ModelManager(Hardware(8, "CPU", 0, "LOW_MEMORY", "3.11", "test"))
    manager = SegmentationManager(models)
    path = manager.create(image, "subject")
    assert manager.create(image, "subject") == path
    foreground = np.load(path)
    background = np.load(manager.create(image, "background"))
    np.testing.assert_allclose(foreground + background, 1, atol=0.0001)
