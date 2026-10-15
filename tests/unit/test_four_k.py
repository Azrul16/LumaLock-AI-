from io import BytesIO

from PIL import Image

from lumalock.export.four_k import four_k_png


def test_four_k_keeps_aspect_and_original_bytes(tmp_path):
    path = tmp_path / "photo.png"
    Image.new("RGB", (200, 300), "gray").save(path)
    original = path.read_bytes()
    with Image.open(BytesIO(four_k_png(path))) as result:
        assert result.size == (2560, 3840)
        assert "not native 4K" in result.text["LumaLock export"]
        assert result.info["icc_profile"]
    assert path.read_bytes() == original


def test_four_k_does_not_downsample_larger_images(tmp_path):
    path = tmp_path / "large.png"
    Image.new("RGB", (4096, 32)).save(path)
    assert four_k_png(path) == path.read_bytes()
