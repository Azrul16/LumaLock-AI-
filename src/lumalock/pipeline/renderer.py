"""UI-independent rendering from original pixels and authoritative parameters."""

from pathlib import Path

import cv2
import numpy as np

from lumalock.core.exceptions import Cancelled, UserError
from lumalock.imaging.adjustments import apply_adjustments, apply_curves, apply_hsl
from lumalock.imaging.geometry import transform_image
from lumalock.imaging.masks import blend, mask_pixels
from lumalock.project.edit_state import EditState


def render(
    image: np.ndarray,
    state: EditState,
    cancelled=lambda: False,
    progress=lambda value, text: None,
    tile_threshold: int = 4_000_000,
) -> np.ndarray:
    progress(10, "Rendering photographic adjustments…")
    if cancelled():
        raise Cancelled("Rendering cancelled.")
    base = image
    if state.generated_file:
        loaded = cv2.imread(state.generated_file)
        if loaded is None:
            raise UserError(
                "The generated layer is missing. Locate it or restore an earlier history state."
            )
        base = cv2.resize(cv2.cvtColor(loaded, cv2.COLOR_BGR2RGB), (image.shape[1], image.shape[0]))
    height, width = base.shape[:2]
    for layer in state.masks:
        if layer.enabled and layer.mask_file and not Path(layer.mask_file).is_file():
            raise UserError(
                f"Mask '{layer.name}' is missing. Recreate it or restore its project asset."
            )
    if (
        not any(state.adjustments.model_dump().values())
        and not state.hsl
        and not state.curves
        and not any(
            layer.enabled and any(layer.adjustments.model_dump().values()) for layer in state.masks
        )
    ):
        progress(100, "Ready")
        return transform_image(base.copy(), state.geometry)
    if height * width > tile_threshold:
        output = np.empty_like(base)
        tile = 512
        feather = max((layer.feather for layer in state.masks), default=0)
        halo = max(32, int(feather * max(height, width) / 1400 * 4) + 1)
        total = ((height + tile - 1) // tile) * ((width + tile - 1) // tile)
        done = 0
        for y in range(0, height, tile):
            for x in range(0, width, tile):
                if cancelled():
                    raise Cancelled("Rendering cancelled.")
                y1, x1 = min(height, y + tile), min(width, x + tile)
                sy, sx = max(0, y - halo), max(0, x - halo)
                ey, ex = min(height, y1 + halo), min(width, x1 + halo)
                bounds = (sy, sx, ey, ex)
                rendered = _render_region(
                    base[sy:ey, sx:ex], state, cancelled, bounds, (height, width)
                )
                output[y:y1, x:x1] = rendered[y - sy : y1 - sy, x - sx : x1 - sx]
                done += 1
                progress(int(done / total * 100), "Rendering original-resolution tiles…")
        return transform_image(output, state.geometry)
    result = _render_region(base, state, cancelled, None, base.shape[:2])
    progress(100, "Ready")
    return transform_image(result, state.geometry)


def _render_region(base, state, cancelled, bounds, full_shape):
    rgb = base.astype(np.float32) / 255
    result = apply_adjustments(rgb, state.adjustments, bounds=bounds, full_shape=full_shape)
    result = apply_hsl(result, state.hsl)
    result = apply_curves(result, state.curves)
    for index, layer in enumerate(state.masks):
        if cancelled():
            raise Cancelled("Rendering cancelled.")
        if layer.enabled and any(layer.adjustments.model_dump().values()):
            mask = mask_pixels(layer, full_shape, bounds)
            result = blend(
                result,
                apply_adjustments(result, layer.adjustments, bounds=bounds, full_shape=full_shape),
                mask,
            )
    return (np.clip(result, 0, 1) * 255 + 0.5).astype(np.uint8)
