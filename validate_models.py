"""Real FLUX-only photo acceptance check with the same execution limit as the app."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from lumalock.ai.identity.detector import face_mask
from lumalock.core.config import data_dir
from lumalock.project.chat import ChatStore
from lumalock.webapp.service import ImageService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--quality", choices=["Preview", "Quality", "Maximum"], default="Quality")
    args = parser.parse_args()
    original_bytes = args.image.read_bytes()
    store = ChatStore(data_dir() / "preview" / "flux-acceptance" / "chats")
    service = ImageService(store=store)
    chat = service.new_chat()
    service.attach(chat["id"], args.image, args.image.name)
    start = time.monotonic()
    previous = None
    try:
        service.start_edit(
            chat["id"],
            "Make this photo look like beautiful late afternoon with warm natural light. Do not change my face.",
            quality=args.quality,
            mode="Natural",
            preset="Late Afternoon",
        )
        while True:
            state = service.state(chat["id"])
            job = state["job"]
            mark = (job["progress"], job["message"])
            if mark != previous:
                print(json.dumps(job), flush=True)
                previous = mark
            if job["status"] not in ("running", "stopping"):
                break
            time.sleep(1)
        success = job["status"] == "complete"
        report = {
            "real_flux_inference": success,
            "quality_profile": args.quality,
            "seconds": round(time.monotonic() - start, 2),
            "status": job["status"],
            "message": job["message"],
            "original_unchanged": hashlib.sha256(original_bytes).hexdigest()
            == hashlib.sha256(args.image.read_bytes()).hexdigest(),
            "separate_prompt_model_loaded": False,
        }
        if success:
            result_path = store.asset(state["chat"]["turns"][-1]["result"])
            root = np.asarray(
                Image.open(store.asset(state["chat"]["turns"][-1]["root"])).convert("RGB")
            )
            result = np.asarray(Image.open(result_path).convert("RGB"))
            protected, _ = face_mask(root, service.settings.face_expansion)
            report.update(
                output=str(result_path),
                protected_pixels_exact=bool(
                    np.array_equal(root[protected > 0], result[protected > 0])
                ),
                dimensions_retained=result.shape == root.shape,
            )
            assert report["protected_pixels_exact"] and report["dimensions_retained"]
        (data_dir() / "preview" / "flux-direct-acceptance.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report), flush=True)
        if not success:
            raise SystemExit(job["message"])
    finally:
        service.close()


if __name__ == "__main__":
    main()
