from types import SimpleNamespace

import numpy as np
from PIL import Image

from lumalock.core.config import Settings
from lumalock.imaging.image_io import load_image
from lumalock.pipeline.chat_edit import edit_chat_image
from lumalock.pipeline.photo_correction import is_photo_correction


def test_photo_correction_does_not_regenerate_and_preserves_manual_area(
    photograph, local_storage, monkeypatch
):
    source = local_storage / "original.png"
    Image.fromarray(photograph).save(source)
    original = source.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Photographic correction must never invoke diffusion")

    monkeypatch.setattr("lumalock.pipeline.chat_edit.creative_edit", forbidden)
    models = SimpleNamespace(available=lambda key: True, settings=Settings())
    result = edit_chat_image(
        source,
        source,
        "auto enhance",
        models,
        True,
        lambda: False,
        lambda *a: None,
        protection=[{"tool": "rectangle", "points": [[0, 0], [0.4, 1]]}],
    )
    output = load_image(result).pixels
    assert output.shape == photograph.shape
    np.testing.assert_array_equal(
        output[:, : photograph.shape[1] // 3], photograph[:, : photograph.shape[1] // 3]
    )
    assert np.any(output != photograph)
    assert source.read_bytes() == original


def test_extra_instructions_are_not_silently_ignored():
    assert is_photo_correction("auto enhance", "Natural", None)
    assert not is_photo_correction("auto enhance and remove the sign", "Natural", None)
    assert not is_photo_correction("auto enhance", "Creative", None)
    assert not is_photo_correction("auto enhance", "Natural", "Dramatic Sky")
