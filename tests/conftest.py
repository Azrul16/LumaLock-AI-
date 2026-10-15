"""Synthetic photographic fixtures; no personal images are used."""

import numpy as np
import pytest


@pytest.fixture
def photograph():
    y, x = np.mgrid[0:128, 0:192]
    return (
        np.stack([40 + x * 0.8, 30 + y * 1.2, 150 + x * 0.2 - y * 0.4], axis=-1)
        .clip(0, 255)
        .astype(np.uint8)
    )


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMALOCK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LUMALOCK_MODEL_DIR", str(tmp_path / "models"))
    return tmp_path
