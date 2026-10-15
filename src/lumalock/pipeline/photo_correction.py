"""Explicit auto-enhance commands adjust full-resolution source pixels without diffusion."""

import uuid

import cv2
import numpy as np

from lumalock.ai.identity.compositor import recover_protected
from lumalock.ai.identity.detector import face_mask
from lumalock.ai.prompt.parser import apply_plan
from lumalock.core.config import data_dir
from lumalock.core.exceptions import Cancelled, UserError
from lumalock.pipeline.auto_enhance import auto_plan
from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import EditState


def is_photo_correction(prompt, mode, preset):
    return (
        mode == "Natural"
        and preset in (None, "Professional Enhance")
        and prompt.strip().casefold()
        in {"auto enhance", "professional enhance", "enhance this photo"}
    )


def correct_photo(original, current, analysis, settings, preserve, manual, cancelled, progress):
    state = apply_plan(EditState(), auto_plan(analysis))
    # Avoid smoothing fine fabric/skin texture in the photographic correction path.
    state.adjustments.denoise = 0
    result = render(current, state, cancelled, progress)
    if preserve:
        protected = manual
        if protected is None:
            protected, _ = face_mask(original, settings.face_expansion)
        if not np.any(protected):
            raise UserError(
                "No protected face area found. Paint protection or switch Preserve people off."
            )
        result = recover_protected(original, result, protected)
    if cancelled():
        raise Cancelled("Photo correction stopped.")
    directory = data_dir() / "generated"
    directory.mkdir(exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}.png"
    if not cv2.imwrite(str(path), cv2.cvtColor(result, cv2.COLOR_RGB2BGR)):
        raise UserError("Could not save the corrected photograph.")
    return path
