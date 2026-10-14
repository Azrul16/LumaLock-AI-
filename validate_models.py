"""Explicit real-model acceptance checks after the user installs the two bundles."""

import argparse
import json
import time
from pathlib import Path

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.core.exceptions import UserError
from lumalock.core.hardware import detect_hardware
from lumalock.core.model_manager import ModelManager
from lumalock.imaging.image_io import load_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["prompt", "flux"], default="prompt")
    parser.add_argument("--image", type=Path, required=True)
    args = parser.parse_args()
    models = ModelManager(detect_hardware())
    if not models.available(args.model):
        raise UserError("Install the selected model bundle before this real acceptance check.")
    models.verify(args.model)
    image = load_image(args.image)
    start = time.perf_counter()
    if args.model == "prompt":
        from lumalock.ai.prompt.local_model import direct

        request = direct(
            "Make this photo professionally edited.",
            analyze(image.preview(1200)),
            models,
            lambda: False,
            lambda v, m: print(m, flush=True),
        )
        assert (
            request.mode == "natural" and request.preserve_identity and request.preserve_composition
        )
        assert not models.loaded
        print(
            json.dumps(
                {
                    "real_qwen_inference": True,
                    "mode": request.mode,
                    "unloaded": True,
                    "seconds": time.perf_counter() - start,
                }
            )
        )
    else:
        import cv2
        import numpy as np

        from lumalock.ai.identity.detector import face_mask
        from lumalock.ai.prompt.schema import EditPlan, GenerativeOptions
        from lumalock.pipeline.creative_edit import creative_edit
        from lumalock.project.edit_state import EditState, MaskLayer

        models.settings.quality_mode = "Preview"
        protected, faces = face_mask(image.pixels)
        if not faces:
            raise UserError(
                "Choose a frontal portrait or mark a manual protection mask for this acceptance test."
            )
        layer = MaskLayer(id="whole", name="Natural edit", kind="rectangle", geometry=[0, 0, 1, 1])
        plan = EditPlan(
            generative=GenerativeOptions(
                enabled=True,
                prompt="Professionally enhance this reference photograph. Preserve every person, face, clothing and composition. Improve lighting and natural color balance.",
                strength=0.4,
            )
        )
        output = creative_edit(
            image.pixels,
            EditState(),
            layer,
            plan,
            models,
            lambda: False,
            lambda v, m: print(m, flush=True),
        )
        result = cv2.cvtColor(cv2.imread(str(output)), cv2.COLOR_BGR2RGB)
        np.testing.assert_array_equal(result[protected > 0], image.pixels[protected > 0])
        assert np.any(result != image.pixels)
        print(
            json.dumps(
                {
                    "real_flux_inference": True,
                    "protected_pixels_exact": True,
                    "seconds": time.perf_counter() - start,
                    "output": str(output),
                }
            )
        )


if __name__ == "__main__":
    try:
        main()
    except UserError as exc:
        raise SystemExit(str(exc))
