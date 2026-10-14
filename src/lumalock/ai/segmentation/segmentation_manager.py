"""Classical cached masks; no additional neural networks."""

import hashlib
from pathlib import Path

import cv2
import numpy as np

from lumalock.ai.identity.detector import face_mask, identity_backend
from lumalock.core.config import data_dir
from lumalock.core.exceptions import UserError


def sky_mask(image):
    rgb = image.astype(np.float32) / 255
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    blue = (hsv[..., 0] > 175) & (hsv[..., 0] < 255) & (hsv[..., 1] > 0.12) & (hsv[..., 2] > 0.25)
    neutral_bright = (hsv[..., 1] < 0.15) & (hsv[..., 2] > 0.72)
    candidate = (blue | neutral_bright).astype(np.uint8)
    count, labels = cv2.connectedComponents(candidate)
    top_labels = np.unique(labels[0, :])
    top_labels = top_labels[top_labels != 0]
    mask = np.isin(labels, top_labels).astype(np.float32)
    return cv2.GaussianBlur(mask, (0, 0), 2)


def classical_subject_mask(image):
    """GrabCut foreground from a central ROI; not semantic subject recognition."""
    h, w = image.shape[:2]
    scale = min(1, 768 / max(h, w))
    reduced = cv2.resize(image, (max(8, round(w * scale)), max(8, round(h * scale))))
    rh, rw = reduced.shape[:2]
    mask = np.zeros((rh, rw), np.uint8)
    rect = (max(1, rw // 10), max(1, rh // 10), max(1, rw * 8 // 10), max(1, rh * 8 // 10))
    background = np.zeros((1, 65), np.float64)
    foreground = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(reduced, mask, rect, background, foreground, 4, cv2.GC_INIT_WITH_RECT)
    except cv2.error as exc:
        raise UserError(
            "Classical segmentation could not separate this subject. Use a brush mask to select the region."
        ) from exc
    result = np.isin(mask, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.float32)
    if not result.any():
        raise UserError(
            "No foreground was found by classical segmentation. Use a brush mask to select the region."
        )
    return cv2.GaussianBlur(cv2.resize(result, (w, h)), (0, 0), 1.5)


class SegmentationManager:
    def __init__(self, models, expansion=0.25):
        self.models = models
        self.expansion = expansion

    def create(
        self, image, kind, cancelled=lambda: False, progress=lambda value, text: None
    ) -> Path:
        backend = "grabcut-v2"
        if kind == "face":
            backend = type(identity_backend()).__name__ + "-v2"
        elif kind == "sky":
            backend = "top-connected-sky-v1"
        digest = hashlib.sha256(
            image.tobytes() + f"{kind}-{self.expansion}-{backend}".encode()
        ).hexdigest()
        cache = data_dir() / "cache" / "masks"
        cache.mkdir(parents=True, exist_ok=True)
        path = cache / f"{digest}.npy"
        if path.exists():
            return path
        progress(10, f"Creating {kind} mask…")
        if kind == "face":
            mask, faces = face_mask(image, self.expansion)
            if not faces:
                raise UserError(
                    "No frontal face was detected. Use a manual protection mask for missed or profile faces."
                )
        elif kind == "sky":
            mask = sky_mask(image)
            if not mask.any():
                raise UserError(
                    "No sky was found by the conservative sky fallback. Use a brush or gradient mask."
                )
        elif kind in ("subject", "background"):
            if kind == "background":
                subject = self.create(image, "subject", cancelled, progress)
                mask = 1 - np.load(subject, allow_pickle=False)
                np.save(path, mask.astype(np.float32), allow_pickle=False)
                return path
            progress(25, "Using classical GrabCut; inspect foreground coverage")
            mask = classical_subject_mask(image)
        else:
            raise ValueError("Unsupported automatic mask")
        np.save(path, mask.astype(np.float32), allow_pickle=False)
        progress(100, "Mask ready")
        return path
