"""Measurements for existing masks without repeating segmentation."""

from dataclasses import replace

import numpy as np

from lumalock.imaging.colorspace import luminance
from lumalock.imaging.masks import mask_pixels


def update_regional_analysis(analysis, image, layer):
    mask = mask_pixels(layer, image.shape[:2])
    total = float(mask.sum())
    if total < 1:
        return analysis
    mean = float((luminance(image.astype(np.float32) / 255) * mask).sum() / total)
    if layer.kind == "subject":
        return replace(analysis, subject_exposure=mean)
    if layer.kind == "sky":
        return replace(analysis, sky_exposure=mean, sky_present=True)
    return analysis
