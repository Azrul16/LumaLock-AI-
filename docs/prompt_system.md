# Deterministic prompts

The user's original-language text is included verbatim in USER REQUEST, followed by fixed
editing requirements. Natural mode preserves structure; Creative mode allows requested scene
changes. Explicit UI mode always takes priority. Identity requirements are added automatically
when protection is enabled. Protected regions receive original-pixel recovery after generation.

The twelve photographic presets are text only. Dramatic Sky enhances existing sky in Natural
mode and permits requested sky changes in Creative. Auto Enhance uses measured brightness,
contrast, clipping, saturation, channel balance, noise and sharpness from NumPy/OpenCV.
No translation, remote prompt API, separate model, or neural prompt interpretation is used.

Bangla and other Unicode text is retained. Empty prompts are rejected. Prompt preparation
runs as ordinary local code before the FLUX text-conditioning pipeline.
