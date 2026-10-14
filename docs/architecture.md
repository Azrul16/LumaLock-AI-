# Architecture

PySide6 widgets call background services through one cooperative-cancellation worker.
Manual controls and quick looks use NumPy/OpenCV; they never invoke image generation.
State, masks, geometry, history and versions are validated and non-destructive.
Full-resolution exports use bounded-memory tiles before conventional framing transforms.

Qwen's CPU GGUF model produces a validated EditingRequest with a professional FLUX instruction.
Its model/mmap closes before the owned ComfyUI child process starts. The process listens only
on loopback, uses the bundled Python runtime and GGUF nodes, receives the reference PNG,
runs a native FLUX.2 reference workflow and returns the generated image through a local API.
Identity compositing stays outside the generative backend and restores original protected pixels.

The portable EXE uses adjacent `data` and `models` folders, with environment overrides for
advanced users. Bundled backend Python runs with an isolated `_pth` configuration and does
not require developer Python or global packages. Source execution uses only project-local `.venv`.
First-run setup downloads the curated, pinned two-model bundle after license acknowledgement.
The shareable ZIP excludes model files, runtime caches, projects, photos and developer environments.

Projects store validated JSON, history, masks and generated assets, plus source fingerprint;
large model files are never embedded. Rotating logs omit image pixels, face crops and private metadata.
