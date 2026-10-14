"""Measure preview and original-resolution rendering on a synthetic photograph."""

import argparse
import json
import time

import cv2
import numpy as np
import psutil

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.prompt.parser import apply_plan
from lumalock.core.config import data_dir
from lumalock.pipeline.auto_enhance import auto_plan
from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import EditState


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=2400)
    parser.add_argument("--height", type=int, default=1600)
    args = parser.parse_args()
    rng = np.random.default_rng(17)
    image = rng.integers(10, 230, (args.height, args.width, 3), dtype=np.uint8)
    preview = cv2.resize(image, (1200, round(args.height * 1200 / args.width)))
    start = time.perf_counter()
    analysis = analyze(preview)
    analysis_time = time.perf_counter() - start
    state = apply_plan(EditState(), auto_plan(analysis))
    start = time.perf_counter()
    render(preview, state)
    preview_time = time.perf_counter() - start
    start = time.perf_counter()
    result = render(image, state)
    final_time = time.perf_counter() - start
    memory = psutil.Process().memory_info()
    record = {
        "resolution": [args.width, args.height],
        "analysis_seconds": analysis_time,
        "preview_seconds": preview_time,
        "final_seconds": final_time,
        "segmentation_seconds": None,
        "restoration_seconds": None,
        "peak_gpu_bytes": None,
        "peak_process_bytes": getattr(memory, "peak_wset", None),
        "notes": "CPU photographic engine. Unrun optional model timings are null.",
    }
    path = data_dir() / "benchmark.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return result


if __name__ == "__main__":
    main()
