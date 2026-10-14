"""Real local ComfyUI FLUX editing with cancellation and one lower-memory retry."""

import io
import secrets
import time
import uuid

import numpy as np
import requests
from PIL import Image

from lumalock.comfy.manager import ComfyManager
from lumalock.comfy.workflow import build_workflow
from lumalock.core.exceptions import Cancelled, UserError
from lumalock.core.quality import creative_quality


class FluxBackend:
    def __init__(self, models):
        self.models = models

    def available(self):
        return self.models.available("flux")

    def edit(self, image, prompt, mask, options, cancelled, progress):
        if not self.available():
            raise UserError(
                "FLUX is unavailable. Install the two-model bundle in Settings → AI Models."
            )
        if options.strength == 0:
            return image.copy()
        self.models.verify("flux", cancelled, progress)
        self.models.release_all()
        seed = secrets.randbelow(2**63)
        for attempt in range(2):
            backend = ComfyManager()
            uploaded = None
            try:
                backend.start(cancelled, progress, stronger_offload=attempt > 0)
                quality = creative_quality(self.models.settings, 0.5 if attempt else 1)
                source = Image.fromarray(image)
                source.thumbnail((quality.resolution, quality.resolution), Image.Resampling.LANCZOS)
                width, height = (max(64, round(d / 16) * 16) for d in source.size)
                source = source.resize((width, height), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                source.save(buffer, format="PNG")
                uploaded = f"lumalock-{uuid.uuid4().hex}.png"
                progress(-1, "Preparing reference image…")
                response = backend.http.post(
                    backend.url + "/upload/image",
                    files={"image": (uploaded, buffer.getvalue(), "image/png")},
                    timeout=60,
                )
                response.raise_for_status()
                uploaded = response.json()["name"]
                workflow = build_workflow(
                    uploaded, prompt, width, height, quality.steps, options.strength, seed
                )
                submitted = backend.http.post(
                    backend.url + "/prompt", json={"prompt": workflow}, timeout=30
                )
                if submitted.status_code != 200:
                    raise UserError(
                        "The local runtime rejected the FLUX workflow. Check installed nodes/models in diagnostics."
                    )
                job = submitted.json()["prompt_id"]
                progress(-1, "Encoding and editing locally with FLUX…")
                while True:
                    if cancelled():
                        backend.http.post(backend.url + "/interrupt", json={}, timeout=5)
                        raise Cancelled("FLUX edit cancelled.")
                    if backend.process.poll() is not None:
                        raise UserError(
                            "The FLUX backend stopped. Available RAM/pagefile may be insufficient."
                        )
                    response = backend.http.get(backend.url + f"/history/{job}", timeout=10)
                    response.raise_for_status()
                    history = response.json().get(job)
                    if history:
                        if history.get("status", {}).get("status_str") == "error":
                            messages = history.get("status", {}).get("messages", [])
                            oom = any("memory" in str(m).lower() for m in messages)
                            if oom and attempt == 0:
                                break
                            raise UserError(
                                "FLUX execution failed"
                                + (
                                    " because memory was insufficient."
                                    if oom
                                    else ". See the local backend log."
                                )
                            )
                        outputs = history.get("outputs", {})
                        images = outputs.get("16", {}).get("images", [])
                        if images:
                            progress(-1, "Decoding and applying Identity Lock…")
                            result = backend.http.get(
                                backend.url + "/view", params=images[0], timeout=60
                            )
                            result.raise_for_status()
                            with Image.open(io.BytesIO(result.content)) as output:
                                return np.asarray(
                                    output.convert("RGB").resize(
                                        (image.shape[1], image.shape[0]), Image.Resampling.LANCZOS
                                    )
                                ).copy()
                    time.sleep(0.4)
                progress(-1, "Retrying a smaller edit with stronger CPU offloading…")
            except requests.RequestException as exc:
                raise UserError(
                    "The local FLUX backend connection failed. See diagnostics."
                ) from exc
            finally:
                backend.stop()
                if uploaded:
                    from lumalock.core.config import data_dir

                    path = data_dir() / "backend" / "input" / uploaded
                    if path.parent.resolve() == (data_dir() / "backend" / "input").resolve():
                        path.unlink(missing_ok=True)
        raise UserError(
            "This FLUX edit could not fit. Reduce resolution, close other apps, or increase Windows virtual memory."
        )
