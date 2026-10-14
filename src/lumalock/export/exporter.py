"""Atomic exports with source-file protection and sRGB metadata."""

import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms
from pydantic import BaseModel, Field

from lumalock.core.exceptions import UserError
from lumalock.imaging.image_io import ImageDocument


class ExportOptions(BaseModel):
    quality: int = Field(95, ge=1, le=100)
    width: int | None = Field(None, ge=1, le=50000)
    height: int | None = Field(None, ge=1, le=50000)
    metadata: bool = True


def export_image(
    document: ImageDocument,
    pixels: np.ndarray,
    target: Path | str,
    options: ExportOptions | None = None,
) -> None:
    target = Path(target).resolve()
    options = options or ExportOptions()
    if target == document.path.resolve() or (target.exists() and target.samefile(document.path)):
        raise UserError("Choose a new output filename to preserve the original photograph.")
    formats = {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".webp": "WEBP",
        ".tif": "TIFF",
        ".tiff": "TIFF",
    }
    format_name = formats.get(target.suffix.lower())
    if not format_name:
        raise UserError("Choose JPEG, PNG, WebP or TIFF for export.")
    image = Image.fromarray(pixels)
    if options.width or options.height:
        w = options.width or round(image.width * options.height / image.height)
        h = options.height or round(image.height * options.width / image.width)
        image = image.resize((w, h), Image.Resampling.LANCZOS)
    kwargs = {"icc_profile": ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()}
    if format_name in ("JPEG", "WEBP"):
        kwargs["quality"] = options.quality
    if format_name == "JPEG":
        kwargs["subsampling"] = 0
    if options.metadata and document.exif:
        exif = Image.Exif()
        exif.load(document.exif)
        exif[40962], exif[40963] = image.size
        kwargs["exif"] = exif.tobytes()
    temporary = target.with_name(f".{target.stem}-{uuid.uuid4().hex}.tmp")
    try:
        image.save(temporary, format=format_name, **kwargs)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
