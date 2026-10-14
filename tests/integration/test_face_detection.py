import numpy as np
from skimage import data

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.identity.detector import face_mask


def test_public_domain_frontal_face_is_protected():
    image = data.astronaut()
    mask, faces = face_mask(image)
    assert len(faces) >= 1
    x, y, w, h = faces[0]
    assert np.all(mask[y : y + h, x : x + w] == 1)
    assert mask.sum() > w * h
    analysis = analyze(image, regions=True)
    assert analysis.face_count >= 1 and analysis.face_exposure_ev is not None
