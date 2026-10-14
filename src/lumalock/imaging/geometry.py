"""Non-destructive crop, rotation, flips and straightening without neural inference."""

import cv2
import numpy as np


def transform_image(image, geometry):
    result = image
    if geometry.straighten:
        h, w = result.shape[:2]
        matrix = cv2.getRotationMatrix2D(((w - 1) / 2, (h - 1) / 2), geometry.straighten, 1)
        result = cv2.warpAffine(
            result, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101
        )
    if geometry.quarter_turns:
        result = np.rot90(result, geometry.quarter_turns)
    if geometry.flip_horizontal:
        result = result[:, ::-1]
    if geometry.flip_vertical:
        result = result[::-1]
    if geometry.crop:
        x, y, width, height = geometry.crop
        h, w = result.shape[:2]
        x0, y0 = round(x * w), round(y * h)
        x1, y1 = max(x0 + 1, round((x + width) * w)), max(y0 + 1, round((y + height) * h))
        result = result[y0 : min(h, y1), x0 : min(w, x1)]
    return np.ascontiguousarray(result)


def source_coordinate(x, y, geometry, source_shape):
    """Map a painted display coordinate back into the original normalized image."""
    if geometry.crop:
        left, top, width, height = geometry.crop
        x, y = left + x * width, top + y * height
    if geometry.flip_horizontal:
        x = 1 - x
    if geometry.flip_vertical:
        y = 1 - y
    for _ in range(geometry.quarter_turns):
        x, y = 1 - y, x
    if geometry.straighten:
        h, w = source_shape
        matrix = cv2.getRotationMatrix2D(((w - 1) / 2, (h - 1) / 2), -geometry.straighten, 1)
        x, y = matrix @ np.array([x * (w - 1), y * (h - 1), 1])
        x, y = x / max(1, w - 1), y / max(1, h - 1)
    return float(np.clip(x, 0, 1)), float(np.clip(y, 0, 1))


def geometry_size(size, geometry):
    width, height = size
    if geometry.quarter_turns % 2:
        width, height = height, width
    if geometry.crop:
        x, y, cw, ch = geometry.crop
        width, height = (
            max(1, round((x + cw) * width) - round(x * width)),
            max(1, round((y + ch) * height) - round(y * height)),
        )
    return width, height
