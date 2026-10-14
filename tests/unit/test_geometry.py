import numpy as np
import pytest

from lumalock.imaging.geometry import geometry_size, source_coordinate, transform_image
from lumalock.imaging.masks import mask_pixels
from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import EditState, Geometry, MaskLayer


def test_crop_rotation_and_original_coordinate_mapping():
    image = np.arange(6 * 8 * 3, dtype=np.uint8).reshape(6, 8, 3)
    geometry = Geometry(quarter_turns=1, crop=[0, 0, 0.5, 1])
    result = render(image, EditState(geometry=geometry))
    np.testing.assert_array_equal(result, np.rot90(image)[:, :3])
    assert geometry_size((8, 6), geometry) == (3, 8)
    assert source_coordinate(0, 0, Geometry(quarter_turns=1), (6, 8)) == (1, 0)
    np.testing.assert_array_equal(image, np.arange(6 * 8 * 3, dtype=np.uint8).reshape(6, 8, 3))


def test_flips_are_reversible_and_mask_geometry_is_real():
    image = np.arange(12, dtype=np.uint8).reshape(3, 4)
    geometry = Geometry(flip_horizontal=True, flip_vertical=True)
    np.testing.assert_array_equal(
        transform_image(transform_image(image, geometry), geometry), image
    )
    rectangle = mask_pixels(
        MaskLayer(id="r", name="R", kind="rectangle", geometry=[0, 0, 0.5, 0.5]), (100, 100)
    )
    assert rectangle[:50, :50].all() and not rectangle[60:, 60:].any()
    ellipse = mask_pixels(
        MaskLayer(id="e", name="E", kind="ellipse", geometry=[0.5, 0.5, 0.2, 0.2]), (100, 100)
    )
    assert ellipse[50, 50] == 1 and ellipse[0, 0] == 0


def test_invalid_crop_is_rejected():
    with pytest.raises(ValueError):
        Geometry(crop=[0.9, 0.9, 0.5, 0.5])
