"""Measured protected-region integrity; structural scores are not recognition scores."""

from dataclasses import dataclass

import cv2
import numpy as np

from lumalock.ai.identity.compositor import protected_integrity


@dataclass(frozen=True)
class IdentityValidation:
    protected_pixels_intact: bool
    structural_similarity: float | None
    embedding_similarity: float | None = None


def validate_identity(original, result, protected):
    region = protected > 0
    if not region.any():
        return IdentityValidation(False, None)
    intact = protected_integrity(original, result, protected)
    ys, xs = np.where(region)
    first = original[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    second = result[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    score = None
    try:
        from skimage.metrics import structural_similarity

        if min(first.shape[:2]) >= 7:
            score = float(
                structural_similarity(
                    cv2.cvtColor(first, cv2.COLOR_RGB2GRAY),
                    cv2.cvtColor(second, cv2.COLOR_RGB2GRAY),
                    data_range=255,
                )
            )
    except ImportError:
        pass
    return IdentityValidation(intact, score)
