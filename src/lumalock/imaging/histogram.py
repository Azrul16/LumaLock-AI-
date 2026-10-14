"""Fast preview histograms without repeating exposure, noise or face analysis."""

import numpy as np


def histogram(image):
    gray = np.clip(
        image[..., 0] * 0.2126 + image[..., 1] * 0.7152 + image[..., 2] * 0.0722, 0, 255
    ).astype(np.uint8)
    return [
        np.bincount(image[..., index].ravel(), minlength=256).tolist() for index in range(3)
    ] + [np.bincount(gray.ravel(), minlength=256).tolist()]
