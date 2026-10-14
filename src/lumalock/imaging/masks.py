"""Resolution-independent masks; manual strokes, gradients, radial and stored masks."""

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from lumalock.core.exceptions import UserError
from lumalock.project.edit_state import MaskLayer


@lru_cache(maxsize=8)
def stored_mask(path, modified, size):
    return np.load(path, allow_pickle=False, mmap_mode="r")


def mask_pixels(
    layer: MaskLayer, shape: tuple[int, int], bounds: tuple[int, int, int, int] | None = None
) -> np.ndarray:
    h, w = shape
    y0, x0, y1, x1 = bounds or (0, 0, h, w)
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    xx /= max(1, w - 1)
    yy /= max(1, h - 1)
    if layer.mask_file:
        path = Path(layer.mask_file)
        if not path.is_file():
            raise UserError(
                f"Mask '{layer.name}' is missing. Recreate it or locate its project file."
            )
        stat = path.stat()
        data = stored_mask(str(path), stat.st_mtime_ns, stat.st_size)
        if bounds:
            map_x = ((xx * (w - 1) + 0.5) * data.shape[1] / w - 0.5).astype(np.float32)
            map_y = ((yy * (h - 1) + 0.5) * data.shape[0] / h - 0.5).astype(np.float32)
            mask = cv2.remap(
                data.astype(np.float32),
                map_x,
                map_y,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REPLICATE,
            )
        else:
            mask = cv2.resize(data.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    elif layer.kind == "rectangle":
        x, y, width, height = layer.geometry
        mask = ((xx >= x) & (xx <= x + width) & (yy >= y) & (yy <= y + height)).astype(np.float32)
    elif layer.kind == "ellipse":
        cx, cy, rx, ry = layer.geometry
        mask = (
            (((xx - cx) / max(rx, 0.001)) ** 2 + ((yy - cy) / max(ry, 0.001)) ** 2) <= 1
        ).astype(np.float32)
    elif layer.kind == "radial":
        cx, cy, rx, ry = layer.geometry
        mask = np.clip(
            1 - np.sqrt(((xx - cx) / max(rx, 0.001)) ** 2 + ((yy - cy) / max(ry, 0.001)) ** 2), 0, 1
        )
    elif layer.kind == "gradient":
        x1, y1, x2, y2 = layer.geometry
        dx, dy = x2 - x1, y2 - y1
        mask = np.clip(((xx - x1) * dx + (yy - y1) * dy) / max(dx * dx + dy * dy, 0.001), 0, 1)
    elif layer.kind == "brush":
        mask = np.zeros((y1 - y0, x1 - x0), np.float32)
        for x, y, radius, erase in layer.strokes:
            dab = np.clip(
                (1 - np.sqrt((xx - x) ** 2 + (yy - y) ** 2) / max(radius, 0.001)) * 4, 0, 1
            )
            mask = mask * (1 - dab) if erase else np.maximum(mask, dab)
    else:
        raise UserError(f"Create the {layer.kind} mask before editing this region.")
    if layer.feather:
        mask = cv2.GaussianBlur(mask, (0, 0), max(0.1, layer.feather * max(h, w) / 1400))
    if layer.inverted:
        mask = 1 - mask
    return np.clip(mask * layer.opacity, 0, 1).astype(np.float32)


def blend(original: np.ndarray, edited: np.ndarray, mask: np.ndarray) -> np.ndarray:
    weight = np.clip(mask, 0, 1)[..., None]
    return original * (1 - weight) + edited * weight
