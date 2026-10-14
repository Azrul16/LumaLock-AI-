import hashlib
import json

import pytest

from lumalock.core.exceptions import UserError
from lumalock.core.hardware import Hardware
from lumalock.core.model_manager import ModelManager


def test_model_checksum_detects_same_size_corruption(local_storage, monkeypatch):
    from lumalock.core.model_manager import MODEL_SPECS

    monkeypatch.setitem(
        MODEL_SPECS,
        "prompt",
        {
            "id": "test-fixture",
            "revision": "test",
            "file": "test.safetensors",
        },
    )
    models = ModelManager(Hardware(8, "CPU", 0, "LOW_MEMORY", "3.11", "test"))
    path = models.location("prompt")
    path.mkdir(parents=True)
    weight = path / "test.safetensors"
    weight.write_bytes(b"model-original")
    marker = {
        "id": "test-fixture",
        "revision": "test",
        "files": {
            "test.safetensors": {
                "size": weight.stat().st_size,
                "sha256": hashlib.sha256(weight.read_bytes()).hexdigest(),
                "repo": "test-fixture",
                "revision": "test",
            }
        },
    }
    (path / "installation.json").write_text(json.dumps(marker))
    models.verify("prompt")
    weight.write_bytes(b"model-modified")
    with pytest.raises(UserError, match="checksum"):
        models.verify("prompt")


def test_empty_manifest_and_missing_support_are_not_installed(local_storage):
    from lumalock.core.model_manager import MODEL_SPECS

    models = ModelManager(Hardware(8, "CPU", 0, "LOW_MEMORY", "3.11", "test"))
    path = models.location("flux")
    path.mkdir(parents=True)
    spec = MODEL_SPECS["flux"]
    marker = {"id": spec["id"], "revision": spec["revision"], "files": {}}
    (path / "installation.json").write_text(json.dumps(marker))
    assert not models.installed("flux")
    with pytest.raises(UserError, match="incomplete"):
        models.verify("flux")


def test_verification_can_be_cancelled(local_storage, monkeypatch):
    from lumalock.core.exceptions import Cancelled

    path = local_storage / "weight"
    path.write_bytes(b"model")
    with pytest.raises(Cancelled, match="Paused"):
        ModelManager.checksum(path, lambda: True)


def test_non_oom_errors_are_not_retried():
    from lumalock.core.memory_manager import MemoryManager

    attempted = []

    def operation(device, tile):
        attempted.append(device)
        raise RuntimeError("invalid tensor shape")

    with pytest.raises(RuntimeError, match="shape"):
        MemoryManager().run(operation)
    assert len(attempted) == 1
