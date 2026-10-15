"""Measured environment reports without installing or downloading anything."""

import importlib
import importlib.metadata
import importlib.util

from lumalock.core.config import data_dir, model_dir
from lumalock.core.hardware import detect_hardware


def diagnostics(hardware=None):
    hardware = hardware or detect_hardware()
    lines = [f"{key}: {value}" for key, value in hardware.to_dict().items()]
    for name in (
        "numpy",
        "Pillow",
        "opencv-python-headless",
        "torch",
        "torchvision",
        "transformers",
        "diffusers",
        "huggingface-hub",
    ):
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            module_name = {
                "Pillow": "PIL",
                "opencv-python-headless": "cv2",
                "huggingface-hub": "huggingface_hub",
            }.get(name, name)
            if importlib.util.find_spec(module_name):
                module = importlib.import_module(module_name)
                version = str(getattr(module, "__version__", "version unavailable")) + " (bundled)"
            else:
                version = "not installed"
        lines.append(f"{name}: {version}")
    if importlib.util.find_spec("torch"):
        import torch

        lines.extend(
            [f"CUDA available: {torch.cuda.is_available()}", f"CUDA runtime: {torch.version.cuda}"]
        )
    else:
        lines.append("CUDA inference: unavailable until PyTorch is installed")
    installed = ["flux"] if (model_dir() / "flux/installation.json").is_file() else []
    lines.append("Installed models: " + (", ".join(installed) or "none; core editor is model-free"))
    probe = data_dir() / ".write-probe"
    try:
        probe.write_text("ok")
        probe.unlink()
        lines.append("Writable cache: yes")
    except OSError:
        lines.append("Writable cache: no")
    return "\n".join(lines)
