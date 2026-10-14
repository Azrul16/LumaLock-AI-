"""Oriented sRGB image loading with retained, corrected EXIF."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps

from lumalock.core.exceptions import UserError


@dataclass
class ImageDocument:
    path: Path
    pixels: np.ndarray
    exif: bytes
    size: tuple[int, int]

    def preview(self, maximum: int) -> np.ndarray:
        height, width = self.pixels.shape[:2]
        if max(height, width) <= maximum:
            return self.pixels.copy()
        image = Image.fromarray(self.pixels)
        image.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
        return np.asarray(image).copy()


def load_image(path: Path | str) -> ImageDocument:
    path = Path(path).resolve()
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source)
            icc = image.info.get("icc_profile")
            if icc:
                image = ImageCms.profileToProfile(
                    image,
                    ImageCms.ImageCmsProfile(BytesIO(icc)),
                    ImageCms.createProfile("sRGB"),
                    outputMode="RGB",
                )
            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", image.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            exif = source.getexif()
            exif.pop(274, None)
            # Camera thumbnails may contain unrotated/unprocessed personal pixels.
            exif.pop(513, None)
            exif.pop(514, None)
            return ImageDocument(path, np.asarray(image).copy(), exif.tobytes(), image.size)
    except Exception as exc:
        raise UserError(
            "This image could not be opened. Use a valid JPEG, PNG, WebP or TIFF file."
        ) from exc
