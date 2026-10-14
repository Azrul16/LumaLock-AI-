"""Conventional structural comparison without recognition neural networks."""

from dataclasses import dataclass

import cv2

from lumalock.ai.identity.detector import face_mask
from lumalock.ai.identity.validator import validate_identity


@dataclass(frozen=True)
class FaceCheck:
    faces: int
    structural_similarity: float | None

    def describe(self):
        if not self.faces:
            return "No frontal face detected. Draw a manual protection mask and inspect the result."
        if self.structural_similarity is None:
            return f"Detected {self.faces} face(s). Structural comparison is unavailable; inspect the result manually."
        return (
            f"Compared {self.faces} detected face region(s) using conventional structural similarity "
            f"({self.structural_similarity:.3f}). This measures image structure, not identity probability. "
            "Inspect the person and mask coverage before export."
        )


def check_faces(original, edited):
    protected, faces = face_mask(original)
    if not faces:
        return FaceCheck(0, None)
    if edited.shape != original.shape:
        edited = cv2.resize(edited, (original.shape[1], original.shape[0]))
    report = validate_identity(original, edited, protected)
    return FaceCheck(len(faces), report.structural_similarity)
