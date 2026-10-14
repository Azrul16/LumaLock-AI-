"""Image-aware recipes that relight existing portrait pixels without synthesis."""

import math
import uuid
from dataclasses import dataclass

import numpy as np

from lumalock.ai.prompt.parser import apply_plan
from lumalock.core.exceptions import Cancelled, UserError
from lumalock.imaging.colorspace import luminance
from lumalock.imaging.masks import mask_pixels
from lumalock.pipeline.auto_enhance import auto_plan, guard_auto
from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import Adjustments, MaskLayer

RECIPES = {
    "Natural": "Balanced light, restrained color and clean detail.",
    "Portrait": "Correct face lighting while retaining facial structure and skin detail.",
    "Warm light": "Warm afternoon color with controlled highlights.",
    "Low light": "Lift shadows and reduce noise conservatively.",
    "Cinematic": "Soft highlights, restrained saturation and richer contrast.",
}


@dataclass
class Enhancement:
    state: object
    pixels: np.ndarray
    summary: str


def smart_enhance(
    image,
    current,
    analysis,
    segmentation,
    recipe="Natural",
    strength=1,
    cancelled=lambda: False,
    progress=lambda *_: None,
):
    if recipe not in RECIPES:
        raise UserError("Choose an available editing recipe.")
    target = apply_plan(current, auto_plan(analysis))
    controls = target.adjustments.model_dump()
    styles = {
        "Warm light": {"temperature": 0.18, "highlights": -0.16},
        "Cinematic": {"contrast": 0.14, "saturation": -0.06, "highlights": -0.18},
        "Low light": {
            "exposure": max(controls["exposure"], 0.4),
            "shadows": 0.2,
            "denoise": max(controls["denoise"], 0.18),
        },
    }
    controls.update(styles.get(recipe, {}))
    target.adjustments = Adjustments(**controls)
    if recipe == "Portrait" or (
        analysis.face_count
        and analysis.face_exposure_ev is not None
        and analysis.face_exposure_ev < -0.5
    ):
        progress(20, "Measuring portrait lighting…")
        face = next((layer for layer in target.masks if layer.kind == "face"), None)
        if face is None:
            path = segmentation.create(image, "face", cancelled, progress)
            face = MaskLayer(
                id=uuid.uuid4().hex,
                name="Portrait lighting",
                kind="face",
                mask_file=str(path),
                feather=4,
            )
            target.masks.append(face)
        mask = mask_pixels(face, image.shape[:2])
        gray = luminance(image.astype(np.float32) / 255)
        mean = float((gray * mask).sum() / max(1, mask.sum()))
        lift = max(-0.15, min(0.4, math.log2(0.48 / max(0.05, mean)) * 0.35))
        face.adjustments = Adjustments(exposure=lift, highlights=-0.08, sharpening=0.04)
    for name, value in target.adjustments.model_dump().items():
        original = getattr(current.adjustments, name)
        setattr(target.adjustments, name, original + (value - original) * strength)
    for layer in target.masks:
        before = next((item for item in current.masks if item.id == layer.id), None)
        values = {
            name: (getattr(before.adjustments, name) if before else 0)
            + (value - (getattr(before.adjustments, name) if before else 0)) * strength
            for name, value in layer.adjustments.model_dump().items()
        }
        layer.adjustments = Adjustments(**values)
    if cancelled():
        raise Cancelled("Enhancement cancelled.")
    pixels = render(image, target, cancelled, progress)
    pixels, target = guard_auto(image, pixels, target, render)
    return Enhancement(
        target,
        pixels,
        RECIPES[recipe] + " Original facial geometry is retained; no pixels are generated.",
    )
