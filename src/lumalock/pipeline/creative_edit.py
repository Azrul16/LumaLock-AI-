"""Mask enforcement and original-face recovery around replaceable generation."""

import uuid

import cv2
import numpy as np

from lumalock.ai.identity.compositor import (
    recover_protected,
    safe_generation_mask,
)
from lumalock.ai.identity.detector import face_mask
from lumalock.ai.identity.validator import validate_identity
from lumalock.core.backend_registry import GENERATIVE_BACKENDS
from lumalock.core.config import data_dir
from lumalock.core.exceptions import UserError
from lumalock.imaging.masks import blend_uint8, mask_pixels


def creative_edit(image, state, layer, plan, models, cancelled, progress, manual_protection=None):
    base = image
    if state.generated_file:
        prior = cv2.imread(state.generated_file)
        if prior is None:
            raise UserError(
                "The previous creative layer is missing. Restore its project asset before continuing."
            )
        base = cv2.resize(cv2.cvtColor(prior, cv2.COLOR_BGR2RGB), (image.shape[1], image.shape[0]))
    editable = mask_pixels(layer, image.shape[:2])
    protected = np.zeros(image.shape[:2], np.float32)
    if state.identity_lock:
        manual = manual_protection is not None or any(mask.protected for mask in state.masks)
        if manual_protection is not None:
            if manual_protection.shape != protected.shape:
                raise UserError("The protection mask does not match this photo.")
            protected = manual_protection.astype(np.float32)
        if not manual:
            protected, faces = face_mask(image, models.settings.face_expansion)
        # Add user-created face protection masks to the detected protection region.
        for mask in state.masks:
            if mask.kind == "face" or mask.protected:
                protected = np.maximum(protected, mask_pixels(mask, image.shape[:2]))
        if not protected.any():
            if manual:
                raise UserError(
                    "Your protection mask is empty. Paint an area or Clear protection to use automatic face selection."
                )
            raise UserError(
                "Preserve people could not identify a face. Try a clearer, front-facing photo. For a scene without people, switch Preserve people off below the prompt."
            )
        editable = safe_generation_mask(editable, protected)
    if not editable.any():
        raise UserError("The editable mask is empty after face protection.")
    progress(10, "Protecting face pixels…")
    backend = GENERATIVE_BACKENDS.create(models.settings.generative_backend, models=models)
    generated = backend.edit(
        base, plan.generative.prompt, editable, plan.generative, cancelled, progress
    )
    result = blend_uint8(base, generated, editable)
    if state.identity_lock:
        result = recover_protected(image, result, protected)
        if not validate_identity(image, result, protected).protected_pixels_intact:
            raise UserError(
                "Creative output failed protected-region verification; result rejected."
            )
    directory = data_dir() / "generated"
    directory.mkdir(exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}.png"
    if not cv2.imwrite(str(path), cv2.cvtColor(result, cv2.COLOR_RGB2BGR)):
        raise UserError("Generated layer could not be written.")
    return path
