import numpy as np
import pytest
from pydantic import ValidationError

from lumalock.imaging.protection import ProtectionShape, protection_mask


def test_manual_shapes_brush_and_erase_are_normalized():
    mask = protection_mask(
        (200, 100),
        [
            {"tool": "rectangle", "points": [[0.1, 0.1], [0.9, 0.9]]},
            {"tool": "erase", "points": [[0.5, 0.5]], "radius": 0.1},
            {"tool": "brush", "points": [[0, 0], [0.05, 0.05]], "radius": 0.03},
        ],
    )
    assert mask.shape == (100, 200)
    assert mask[20, 40] == 1 and mask[50, 100] == 0 and mask[0, 0] == 1
    assert np.array_equal(protection_mask((100, 100), []), np.zeros((100, 100)))
    ellipse = protection_mask((100, 100), [{"tool": "ellipse", "points": [[0.2, 0.2], [0.8, 0.8]]}])
    assert ellipse[50, 50] == 1 and ellipse[0, 0] == 0


def test_protection_rejects_paths_invalid_coordinates_and_bad_shapes():
    for shape in (
        {"tool": "brush", "points": [[-0.1, 0.1]]},
        {"tool": "brush", "points": [[float("nan"), 0.1]]},
        {"tool": "rectangle", "points": [[0.1, 0.1]]},
        {"tool": "brush", "points": [[0.1, 0.1]], "file": "../secret"},
    ):
        with pytest.raises(ValidationError):
            ProtectionShape.model_validate(shape)
