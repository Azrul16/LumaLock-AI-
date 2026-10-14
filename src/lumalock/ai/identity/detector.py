"""Offline face detection with OpenCV's bundled cascade; no recognition weights."""

from typing import Protocol

import cv2
import numpy as np


class IdentityBackend(Protocol):
    def detect_faces(self, image: np.ndarray) -> list[tuple[int, int, int, int]]: ...
    def extract_embedding(self, image: np.ndarray): ...
    def compare(self, first, second) -> float: ...


class CascadeIdentityBackend:
    def detect_faces(self, image):
        detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        faces = detector.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(24, 24))
        boxes = [tuple(map(int, face)) for face in faces]
        eyes = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
        confirmed = []
        for x, y, width, height in boxes:
            candidates = eyes.detectMultiScale(
                gray[y : y + int(height * 0.65), x : x + width],
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(max(8, width // 10), max(8, height // 10)),
            )
            centers = [(ex + ew / 2, ey + eh / 2) for ex, ey, ew, eh in candidates]
            if any(
                abs(a[0] - b[0]) > width * 0.15 and abs(a[1] - b[1]) < height * 0.2
                for i, a in enumerate(centers)
                for b in centers[i + 1 :]
            ):
                confirmed.append((x, y, width, height))
        # If eye confirmation fails entirely, retain conservative cascade candidates.
        return confirmed or boxes

    def extract_embedding(self, image):
        return None

    def compare(self, first, second):
        raise ValueError(
            "Recognition weights are not installed; no identity similarity score is available."
        )


def identity_backend():
    return CascadeIdentityBackend()


def face_mask(image, expansion=0.25):
    h, w = image.shape[:2]
    mask = np.zeros((h, w), np.float32)
    try:
        faces = identity_backend().detect_faces(image)
    except cv2.error:
        faces = CascadeIdentityBackend().detect_faces(image)
    for x, y, fw, fh in faces:
        margin = int(max(fw, fh) * expansion)
        cv2.rectangle(
            mask,
            (max(0, x - margin), max(0, y - margin)),
            (min(w - 1, x + fw + margin), min(h - 1, y + fh + margin)),
            1,
            -1,
        )
    return mask, faces
