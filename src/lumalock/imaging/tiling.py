"""Overlapping weighted tiles for bounded-memory restoration."""

import numpy as np

from lumalock.core.exceptions import Cancelled


def tiled_process(image: np.ndarray, operation, tile_size=384, overlap=48, cancelled=lambda: False):
    if not 0 <= overlap < tile_size:
        raise ValueError("Overlap must be smaller than the tile")
    height, width = image.shape[:2]
    output = np.zeros_like(image, dtype=np.float32)
    total = np.zeros((height, width, 1), np.float32)
    step = tile_size - overlap
    for y in range(0, height, step):
        for x in range(0, width, step):
            if cancelled():
                raise Cancelled("Processing cancelled.")
            tile = image[y : y + tile_size, x : x + tile_size]
            result = operation(tile)
            h, w = tile.shape[:2]
            wy = np.maximum(np.hanning(h), 0.05) if h > 1 else np.ones(1)
            wx = np.maximum(np.hanning(w), 0.05) if w > 1 else np.ones(1)
            weights = (wy[:, None] * wx[None, :])[..., None].astype(np.float32)
            output[y : y + h, x : x + w] += result * weights
            total[y : y + h, x : x + w] += weights
    return output / np.maximum(total, 1e-8)
