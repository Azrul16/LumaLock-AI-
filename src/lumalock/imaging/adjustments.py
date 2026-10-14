"""Linear-light tone, chromatic adaptation, local contrast and selective color."""

from functools import lru_cache

import cv2
import numpy as np

from lumalock.imaging.colorspace import luminance, to_linear, to_srgb
from lumalock.project.edit_state import HSL_COLORS, Adjustments


@lru_cache(maxsize=64)
def adaptation_matrix(temperature, tint):
    xyz = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ],
        np.float32,
    )
    bradford = np.array(
        [[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]],
        np.float32,
    )
    cone = bradford @ xyz
    gains = np.exp(
        np.array([temperature * 0.13, tint * -0.08, temperature * -0.17 + tint * 0.04], np.float32)
    )
    return (np.linalg.inv(cone) @ np.diag(gains) @ cone).astype(np.float32)


def apply_adjustments(
    image: np.ndarray,
    controls: Adjustments,
    seed: int = 42,
    bounds: tuple[int, int, int, int] | None = None,
    full_shape: tuple[int, int] | None = None,
) -> np.ndarray:
    """Process normalized floating-point RGB; zero controls are an identity transform."""
    a = controls
    if not any(a.model_dump().values()):
        return image.copy()
    rgb = image.astype(np.float32).copy()
    if a.exposure or a.temperature or a.tint:
        linear = to_linear(rgb)
        if a.temperature or a.tint:
            # Bradford adaptation in cone-response space, rather than RGB offsets.
            adaptation = adaptation_matrix(a.temperature, a.tint)
            linear = np.maximum(linear @ adaptation.T, 0).astype(np.float32)
        linear *= 2**a.exposure
        # Soft rolloff above the white point, continuous at 0.8.
        if a.exposure > 0:
            linear = np.where(linear > 0.8, 0.8 + 0.2 * (1 - np.exp(-(linear - 0.8) / 0.2)), linear)
        rgb = to_srgb(linear)
    y = luminance(rgb)
    delta = (
        a.brightness * 0.15
        + a.shadows * 0.25 * (1 - y) ** 3
        + a.highlights * 0.25 * y**3
        + a.whites * 0.2 * y**6
        + a.blacks * 0.16 * (1 - y) ** 6
    )
    target = np.clip(y + delta, 0, 1)
    if a.contrast:
        target = np.clip(target + a.contrast * (target - 0.5) * target * (1 - target) * 2.4, 0, 1)
    rgb += (target - y)[..., None]
    rgb = np.clip(rgb, 0, 1)
    if a.dehaze:
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        light = lab[..., 0] / 100
        local = light - cv2.GaussianBlur(light, (0, 0), 6)
        corrected = (light - 0.025 * a.dehaze) / max(0.8, 1 - 0.08 * a.dehaze)
        lab[..., 0] = np.clip(corrected + a.dehaze * 0.25 * local, 0, 1) * 100
        rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    if a.saturation or a.vibrance:
        hsv = cv2.cvtColor(np.clip(rgb, 0, 1), cv2.COLOR_RGB2HSV)
        skin = ((hsv[..., 0] >= 5) & (hsv[..., 0] <= 50)).astype(np.float32)
        hsv[..., 1] *= 1 + a.saturation + a.vibrance * (1 - hsv[..., 1]) * (1 - 0.55 * skin)
        hsv[..., 1] = np.clip(hsv[..., 1], 0, 1)
        rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    if a.denoise:
        smooth = cv2.bilateralFilter(rgb, 7, 0.035 + a.denoise * 0.09, 4)
        rgb = rgb * (1 - a.denoise) + smooth * a.denoise
    if a.clarity or a.texture or a.sharpening:
        y = luminance(rgb)
        mid = y - cv2.GaussianBlur(y, (0, 0), 5)
        high = y - cv2.GaussianBlur(y, (0, 0), 1)
        rgb += (mid * a.clarity * 0.6 + high * (a.texture * 0.5 + a.sharpening * 0.8))[..., None]
    if a.vignette:
        h, w = rgb.shape[:2]
        if bounds is not None and full_shape is not None:
            y0, x0, y1, x1 = bounds
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            yy = yy / max(1, full_shape[0] - 1) * 2 - 1
            xx = xx / max(1, full_shape[1] - 1) * 2 - 1
        else:
            yy, xx = np.mgrid[-1 : 1 : complex(h), -1 : 1 : complex(w)]
        radial = np.clip((xx * xx + yy * yy) / 1.6, 0, 1)
        rgb *= (1 - a.vignette * 0.55 * radial)[..., None]
    if a.grain:
        h, w = rgb.shape[:2]
        y0, x0 = (bounds[0], bounds[1]) if bounds else (0, 0)
        yy, xx = np.mgrid[y0 : y0 + h, x0 : x0 + w].astype(np.uint32)
        hashed = xx * np.uint32(374761393) + yy * np.uint32(668265263) + np.uint32(seed)
        hashed = (hashed ^ (hashed >> np.uint32(13))) * np.uint32(1274126177)
        uniform = (hashed ^ (hashed >> np.uint32(16))).astype(np.float64) / 4294967295
        noise = ((uniform - 0.5) * a.grain * 0.065).astype(np.float32)
        rgb += noise[..., None]
    return np.clip(rgb, 0, 1).astype(np.float32)


def apply_hsl(rgb: np.ndarray, controls: dict[str, list[float]]) -> np.ndarray:
    if not controls:
        return rgb
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HLS)
    original_hue = hsv[..., 0].copy()
    centers = [0, 30, 60, 120, 180, 240, 275, 315]
    for name, values in controls.items():
        center = centers[HSL_COLORS.index(name)]
        distance = np.abs((original_hue - center + 180) % 360 - 180)
        weight = np.maximum(0, 1 - distance / 35) ** 2
        hue, saturation, light = values
        hsv[..., 0] = (hsv[..., 0] + hue * 30 * weight) % 360
        hsv[..., 2] *= 1 + saturation * weight
        hsv[..., 1] += light * 0.25 * weight
    hsv[..., 1:] = np.clip(hsv[..., 1:], 0, 1)
    return np.clip(cv2.cvtColor(hsv, cv2.COLOR_HLS2RGB), 0, 1)


def apply_curves(rgb: np.ndarray, curves: dict[str, list[list[float]]]) -> np.ndarray:
    result = rgb.copy()
    for name, points in curves.items():
        x, y = np.array(points).T
        if name == "master":
            result = np.interp(result, x, y).astype(np.float32)
        else:
            index = ("red", "green", "blue").index(name)
            result[..., index] = np.interp(result[..., index], x, y)
    return result
