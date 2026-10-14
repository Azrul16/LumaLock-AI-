"""Acceptance checks using a user-selected photo; never modify the source."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.identity.compositor import recover_protected
from lumalock.ai.identity.detector import face_mask
from lumalock.export.exporter import ExportOptions, export_image
from lumalock.imaging.image_io import load_image
from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import EditState, MaskLayer
from lumalock.project.history import History
from lumalock.project.serialization import load_project, save_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/acceptance"))
    args = parser.parse_args()
    source = args.image.resolve()
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    document = load_image(source)
    args.output.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    state = EditState()
    state.adjustments.exposure = 0.2
    state.adjustments.highlights = -0.15
    state.adjustments.shadows = 0.12
    state.adjustments.temperature = 0.06
    state.adjustments.sharpening = 0.08
    result = render(document.pixels, state)
    assert result.shape == document.pixels.shape
    assert np.any(result != document.pixels)
    protected, faces = face_mask(document.pixels)
    # Exercise manual protection independently of automatic detection coverage.
    manual = MaskLayer(
        id="manual",
        name="Face protection",
        kind="ellipse",
        geometry=[0.5, 0.27, 0.13, 0.13],
        protected=True,
    )
    from lumalock.imaging.masks import mask_pixels

    protected = np.maximum(protected, mask_pixels(manual, document.pixels.shape[:2]))
    recovered = recover_protected(document.pixels, result, protected)
    np.testing.assert_array_equal(recovered[protected > 0], document.pixels[protected > 0])
    history = History()
    history.push("Manual acceptance edit", state)
    np.testing.assert_array_equal(render(document.pixels, history.undo()), document.pixels)
    np.testing.assert_array_equal(render(document.pixels, history.redo()), result)
    history.save_version("Acceptance version", state)
    project = args.output / "photo-test.luma"
    save_project(project, source, history, [])
    reopened, loaded, _ = load_project(project)
    assert reopened == source
    np.testing.assert_array_equal(render(load_image(reopened).pixels, loaded.state), result)
    for suffix in ("jpg", "png", "webp"):
        target = args.output / f"manual-edit.{suffix}"
        export_image(document, result, target, ExportOptions(metadata=False, quality=98))
        with Image.open(target) as output:
            assert output.size == document.size
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    report = {
        "source_unchanged": True,
        "dimensions": document.size,
        "detected_frontal_faces": len(faces),
        "manual_edit": True,
        "protected_pixels_exact": True,
        "undo_redo": True,
        "project_roundtrip": True,
        "exports": ["JPEG", "PNG", "WebP"],
        "seconds": time.perf_counter() - start,
        "analysis": {
            k: v for k, v in analyze(document.preview(1200)).to_dict().items() if k != "histogram"
        },
    }
    (args.output / "manual-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "analysis"}, indent=2))


if __name__ == "__main__":
    main()
