"""Bounded-memory HTTPS transfers with resume, real progress and cooperative pause."""

import time

import requests

from lumalock.core.exceptions import Cancelled, UserError


def receive_file(item, target, cancelled, progress):
    from huggingface_hub import hf_hub_url
    from huggingface_hub.utils import build_hf_headers

    partial = target.with_name(target.name + ".part")
    size = item["size"]
    url = hf_hub_url(item["repo"], item["file"], revision=item["revision"])
    for attempt in range(3):
        if cancelled():
            raise Cancelled("Paused. Download / Repair resumes partial files.")
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == size:
            return
        if offset > size:
            with partial.open("wb"):
                pass
            offset = 0
        headers = build_hf_headers()
        headers["Accept-Encoding"] = "identity"
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            with requests.get(url, headers=headers, stream=True, timeout=(15, 10)) as response:
                if response.status_code in (401, 403):
                    raise UserError(
                        "Model access was denied. Accept the repository terms in your Hugging Face account and sign in locally, then retry."
                    )
                response.raise_for_status()
                if response.status_code == 206:
                    expected = f"bytes {offset}-"
                    if not response.headers.get("Content-Range", "").startswith(expected):
                        raise UserError(
                            "The server returned an invalid download range; retry later."
                        )
                else:
                    offset = 0  # Servers ignoring Range must overwrite, never append.
                count = offset
                start = last = time.monotonic()
                with partial.open("ab" if offset else "wb") as stream:
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        if cancelled():
                            raise Cancelled("Paused. Download / Repair resumes partial files.")
                        if not chunk:
                            continue
                        count += len(chunk)
                        if count > size:
                            raise UserError("The server returned an unexpected file size.")
                        stream.write(chunk)
                        now = time.monotonic()
                        if now - last >= 0.25 or count == size:
                            speed = (count - offset) / max(0.001, now - start)
                            seconds = int((size - count) / max(1, speed))
                            eta = (
                                f"{seconds // 60}m {seconds % 60}s remaining"
                                if speed
                                else "Estimating time…"
                            )
                            progress(
                                count,
                                f"{target.name}\n{count / 1024**3:.2f} / {size / 1024**3:.2f} GiB · {speed / 1024**2:.1f} MiB/s · {eta}",
                            )
                            last = now
                if count != size:
                    raise requests.ConnectionError("Incomplete response")
                return
        except requests.RequestException:
            if attempt == 2:
                raise
            progress(offset, "Connection interrupted · reconnecting and resuming…")
            # Short interruptible backoff avoids an aggressive retry loop.
            for _ in range(10 * (attempt + 1)):
                if cancelled():
                    raise Cancelled("Paused. Download / Repair resumes partial files.")
                time.sleep(0.1)
