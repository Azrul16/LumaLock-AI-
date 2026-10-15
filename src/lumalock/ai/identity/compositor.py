"""Protected pixels are removed from editing masks and recovered after inference."""

import cv2
import numpy as np

from lumalock.imaging.masks import blend_uint8


def safe_generation_mask(editable: np.ndarray, protected: np.ndarray) -> np.ndarray:
    if editable.shape != protected.shape:
        raise ValueError("Protection and editing masks must have identical dimensions")
    # Hard exclusion includes the entire expanded protected region, even soft edges.
    return np.where(protected > 0, 0, np.clip(editable, 0, 1)).astype(np.float32)


def recover_protected(original, generated, protected):
    """Exact original protected pixels, feathered into the surrounding generated scene."""
    hard = (protected > 0).astype(np.float32)
    expanded = cv2.dilate(hard, np.ones((9, 9), np.uint8))
    feather = cv2.GaussianBlur(expanded, (0, 0), 3)
    feather = np.maximum(feather, hard)
    return blend_uint8(generated, original, feather)


def protected_integrity(original, result, protected) -> bool:
    region = protected > 0
    return bool(np.array_equal(original[region], result[region]))
