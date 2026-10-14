import numpy as np

from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import Adjustments, EditState, MaskLayer


def test_tiled_render_matches_untiled():
    yy, xx = np.mgrid[0:610, 0:730]
    image = (
        np.stack([xx / 4 + 20, yy / 4 + 30, (xx + yy) / 7 + 10], axis=-1)
        .clip(0, 255)
        .astype(np.uint8)
    )
    state = EditState(
        adjustments=Adjustments(
            exposure=0.25, temperature=0.1, clarity=0.1, vignette=0.15, grain=0.1
        )
    )
    layer = MaskLayer(
        id="radial", name="Radial", kind="radial", feather=3, adjustments=Adjustments(exposure=0.2)
    )
    state.masks.append(layer)
    tiled = render(image, state, tile_threshold=1)
    normal = render(image, state, tile_threshold=999999999)
    np.testing.assert_allclose(tiled.astype(float), normal.astype(float), atol=1)


def test_tiled_stored_mask(local_storage):
    image = np.full((610, 730, 3), 100, np.uint8)
    mask = np.linspace(0, 1, 96 * 64, dtype=np.float32).reshape(64, 96)
    path = local_storage / "mask.npy"
    np.save(path, mask)
    state = EditState(
        masks=[
            MaskLayer(
                id="mask",
                name="Mask",
                kind="subject",
                mask_file=str(path),
                adjustments=Adjustments(exposure=0.4),
            )
        ]
    )
    tiled = render(image, state, tile_threshold=1)
    normal = render(image, state, tile_threshold=999999999)
    np.testing.assert_allclose(tiled.astype(float), normal.astype(float), atol=1)
