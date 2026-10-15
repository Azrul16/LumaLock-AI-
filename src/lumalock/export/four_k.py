"""Aspect-preserving 4K exports; interpolation is not neural detail recovery."""

from io import BytesIO

from PIL import Image, ImageCms, PngImagePlugin


def four_k_png(path):
    """Keep larger images intact; otherwise export with a 3840px longest edge."""
    with Image.open(path) as source:
        image = source.convert("RGB")
        width, height = image.size
        if max(width, height) >= 3840:
            return path.read_bytes()
        scale = 3840 / max(width, height)
        target = (max(1, round(width * scale)), max(1, round(height * scale)))
        image = image.resize(target, Image.Resampling.LANCZOS)
        info = PngImagePlugin.PngInfo()
        info.add_text(
            "LumaLock export", "3840px long edge; Lanczos enlargement, not native 4K AI generation"
        )
        buffer = BytesIO()
        image.save(
            buffer,
            format="PNG",
            pnginfo=info,
            icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes(),
        )
        return buffer.getvalue()
