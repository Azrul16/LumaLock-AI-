"""Cheap photographic measurements, computed only on bounded analysis images."""

import math
from dataclasses import asdict, dataclass

import cv2
import numpy as np

from lumalock.imaging.colorspace import luminance


@dataclass
class ImageAnalysis:
    luminance_mean: float
    black_clipping: float
    white_clipping: float
    contrast: float
    dynamic_range: float
    blur_score: float
    noise: float
    saturation: float
    white_balance: list[float]
    histogram: list[list[int]]
    face_count: int | None = None
    face_exposure_ev: float | None = None
    sky_present: bool | None = None
    sky_exposure: float | None = None
    subject_exposure: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def describe(self) -> str:
        exposure = (
            "Underexposed"
            if self.luminance_mean < 0.3
            else "Bright"
            if self.luminance_mean > 0.7
            else "Balanced exposure"
        )
        description = (
            f"{exposure} · mean luminance {self.luminance_mean:.2f}\n"
            f"Highlights clipped: {self.white_clipping:.1%} · blacks: {self.black_clipping:.1%}\n"
            f"Noise estimate: {self.noise:.3f} · sharpness: {self.blur_score:.0f}"
        )
        if self.face_count is not None:
            description += f"\nDetected faces: {self.face_count}"
            if self.face_exposure_ev is not None:
                description += f" · face exposure {self.face_exposure_ev:+.2f} EV"
        return description


def analyze(image: np.ndarray, regions: bool = False) -> ImageAnalysis:
    height, width = image.shape[:2]
    if max(height, width) > 1024:
        ratio = 1024 / max(height, width)
        image = cv2.resize(
            image, (round(width * ratio), round(height * ratio)), interpolation=cv2.INTER_AREA
        )
    rgb = image.astype(np.float32) / 255
    y = luminance(rgb)
    gray = (y * 255).astype(np.uint8)
    residual = y - cv2.GaussianBlur(y, (0, 0), 1)
    gradient = np.abs(cv2.Laplacian(y, cv2.CV_32F))
    flat = gradient < np.percentile(gradient, 40)
    noise = float(np.median(np.abs(residual[flat])) / 0.6745) if flat.any() else 0
    mean = rgb.mean(axis=(0, 1))
    histogram = [
        np.histogram(image[..., i], bins=256, range=(0, 256))[0].tolist() for i in range(3)
    ]
    histogram.append(np.histogram(gray, bins=256, range=(0, 256))[0].tolist())
    result = ImageAnalysis(
        float(y.mean()),
        float((y < 0.01).mean()),
        float((y > 0.99).mean()),
        float(y.std()),
        float(np.percentile(y, 99) - np.percentile(y, 1)),
        float(cv2.Laplacian(gray, cv2.CV_32F).var()),
        noise,
        float(cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[..., 1].mean()),
        (mean / max(float(mean.mean()), 1e-5)).tolist(),
        histogram,
    )
    if regions:
        from lumalock.ai.identity.detector import face_mask
        from lumalock.ai.segmentation.segmentation_manager import sky_mask

        face, faces = face_mask(image)
        result.face_count = len(faces)
        if face.any():
            result.face_exposure_ev = float(math.log2(max(float(y[face > 0].mean()), 0.001) / 0.45))
        sky = sky_mask(image)
        result.sky_present = bool(sky.any())
        if sky.any():
            result.sky_exposure = float(y[sky > 0.1].mean())
    return result
