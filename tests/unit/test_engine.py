import numpy as np
import pytest
from pydantic import ValidationError

from lumalock.imaging.adjustments import apply_adjustments
from lumalock.imaging.masks import blend, mask_pixels
from lumalock.imaging.tiling import tiled_process
from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import Adjustments, EditState, MaskLayer


def test_neutral_exact(photograph):
    np.testing.assert_array_equal(render(photograph, EditState()), photograph)


def test_exposure_linear():
    dark = np.full((10, 10, 3), 0.1, np.float32)
    from lumalock.imaging.colorspace import to_linear

    result = apply_adjustments(dark, Adjustments(exposure=1))
    np.testing.assert_allclose(to_linear(result), to_linear(dark) * 2, rtol=1e-4)


def test_temperature_and_contrast():
    neutral = np.full((20, 20, 3), 0.5, np.float32)
    warm = apply_adjustments(neutral, Adjustments(temperature=0.5))
    assert warm[..., 0].mean() > warm[..., 2].mean()
    gradient = np.tile(np.linspace(0.1, 0.9, 20, dtype=np.float32)[None, :, None], (20, 1, 3))
    contrast = apply_adjustments(gradient, Adjustments(contrast=0.4))
    assert contrast.std() > gradient.std()


def test_mask_boundaries():
    source = np.zeros((12, 12, 3), np.float32)
    edited = np.ones_like(source)
    mask = np.zeros((12, 12), np.float32)
    mask[:, 6:] = 1
    result = blend(source, edited, mask)
    np.testing.assert_array_equal(result[:, :6], 0)
    np.testing.assert_array_equal(result[:, 6:], 1)


def test_brush_erase():
    layer = MaskLayer(
        id="brush", name="Brush", kind="brush", strokes=[[0.5, 0.5, 0.2, 0], [0.5, 0.5, 0.1, 1]]
    )
    mask = mask_pixels(layer, (100, 100))
    assert mask[50, 50] == 0 and mask.max() > 0


@pytest.mark.parametrize("name", ["exposure", "contrast", "temperature", "denoise"])
def test_schema_rejects_out_of_bounds(name):
    with pytest.raises(ValidationError):
        Adjustments(**{name: 100})


def test_tiling_has_no_seams(photograph):
    result = tiled_process(
        photograph.astype(np.float32), lambda tile: tile * 0.75, tile_size=64, overlap=16
    )
    np.testing.assert_allclose(result, photograph * 0.75, atol=0.0001)


def test_cancel_render(photograph):
    from lumalock.core.exceptions import Cancelled

    with pytest.raises(Cancelled):
        render(photograph, EditState(), cancelled=lambda: True)
