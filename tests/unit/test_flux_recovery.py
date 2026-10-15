import io
from types import SimpleNamespace

import numpy as np
import requests
from PIL import Image

from lumalock.ai.generative.flux_backend import FluxBackend
from lumalock.comfy.manager import ComfyManager
from lumalock.core.config import Settings, data_dir
from lumalock.core.quality import creative_quality


def test_crashed_oom_worker_restarts_and_retries_smaller(local_storage, monkeypatch):
    image = np.full((64, 64, 3), 120, dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    attempts = []

    class Response:
        status_code = 200
        content = buffer.getvalue()

        def __init__(self, value):
            self.value = value

        def raise_for_status(self):
            pass

        def json(self):
            return self.value

    class Runtime:
        def __init__(self):
            self.index = len(attempts)
            attempts.append(self)
            self.url = "http://127.0.0.1:1"
            self.http = self
            self.process = SimpleNamespace(poll=lambda: None)
            self.stopped = False

        def start(self, cancelled, progress, stronger_offload=False):
            self.stronger = stronger_offload

        def memory_failed(self):
            return self.index == 0

        def stop(self):
            self.stopped = True

        def post(self, url, **kwargs):
            return Response(
                {"name": "fixture.png"} if url.endswith("/upload/image") else {"prompt_id": "job"}
            )

        def get(self, url, **kwargs):
            if self.index == 0:
                raise requests.ConnectionError("worker crashed during OOM cleanup")
            return Response({"job": {"outputs": {"16": {"images": [{"filename": "fixture.png"}]}}}})

    monkeypatch.setattr("lumalock.ai.generative.flux_backend.ComfyManager", Runtime)
    models = SimpleNamespace(
        available=lambda key: True,
        verify=lambda *args: None,
        release_all=lambda: None,
        settings=Settings(quality_mode="Preview"),
    )
    result = FluxBackend(models).edit(
        image,
        "Test",
        np.ones((64, 64)),
        SimpleNamespace(strength=0.4),
        lambda: False,
        lambda *args: None,
    )
    np.testing.assert_array_equal(result, image)
    assert len(attempts) == 2
    assert attempts[1].stronger
    assert all(attempt.stopped for attempt in attempts)
    assert creative_quality(models.settings, 0.5).resolution == 256


def test_memory_failure_inspection_ignores_old_runs(local_storage):
    path = data_dir() / "backend/backend.log"
    path.parent.mkdir(parents=True)
    old = b"old run: out of memory\n"
    path.write_bytes(old + b"new run started\n")
    runtime = ComfyManager()
    runtime.log_start = len(old)
    assert not runtime.memory_failed()
    with path.open("ab") as stream:
        stream.write(b"Got an OOM\n")
    assert runtime.memory_failed()
    runtime.stop()
