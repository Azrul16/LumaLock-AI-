# LumaLock AI status

Updated 2026-10-14. Windows x64; RTX 3050 Laptop 4 GiB, 7.71 GiB RAM.
All package installations use the project-local `.venv`. No global Python packages installed.

## DONE

- Non-destructive PySide6 editor: manual light/color/detail/effects controls, HSL and curves,
  history, undo/redo, named versions, .luma projects, autosave, original/split comparison,
  zoom/pan and JPEG/PNG/WebP/TIFF export with source overwrite protection.
- Simple default screen; Advanced tools reveals mask management/history/histogram/quality controls.
- Classical GrabCut/sky heuristics; brush/erase/gradient/radial/rectangle/ellipse masks.
  No additional neural masks, recognition, restoration or upscaling models are used.
- Identity Lock: classical cascade candidates, eye-pair filtering, manual protection, exclusion,
  original-pixel recovery and exact integrity checks. Structural similarity is advisory, not identity probability.
- Reversible crop, aspect ratios, quarter-turn rotation, flips and straighten; masks map back to source coordinates.
- Two-model configuration: Qwen2.5-1.5B Q4_K_M director and FLUX.2-dev Q2_K editor.
  FLUX includes its Mistral Q2_K encoder and VAE. Immutable revisions and upstream checksums are enforced.
- Actual Qwen CPU inference on the user's photo statistics: valid natural plan, 430-character
  instruction, 20.705 seconds; model unloaded before image processing. This is one measured run.
- Actual ComfyUI startup on this GPU; GGUF plugin and all required FLUX workflow nodes registered.
  Backend is loopback-only, browser launch disabled, partner API nodes disabled, no photo uploads.
- User photo tested: original 2048 x 2048 dimensions retained, one frontal face detected after
  classical eye-pair confirmation, manual edits, exact protected-pixel recovery, undo/redo,
  project save/reload and JPEG/PNG/WebP export. Source SHA-256 remained unchanged.
- 48 automated tests pass, including geometry, masks, prompt/state validation, hostile-backend
  protection enforcement and GUI synchronization. Tests with injected backends are contract checks.

## PORTABLE APP VERIFIED

The completed app is in `dist/LumaLockAI`; open `LumaLockAI.exe` and keep its folder intact.
The EXE launches with the user photo from a temporary working directory with Python removed
from PATH. The bundled isolated Python imports PyTorch and detects CUDA; its ComfyUI process
starts and registers all required FLUX/GGUF nodes. No developer Python installation is needed.
First-run setup offers both required model bundles, license acknowledgement, storage preflight
and downloads. Future builds omit ZIP packaging at the user's request. Automatic approval review blocked
cleanup commands, including explicitly named ZIP files and obsolete helpers; existing artifacts remain.

## DEFERRED BY USER

FLUX weight download and actual image-generation validation. The user explicitly requested
models be downloaded when the completed app first starts. Current transfers were stopped.
No FLUX-generated result, quality benchmark or ten-minute runtime guarantee is claimed.
Full inference remains to be tested after the first-run download completes.

## BLOCKED

Automatic approval review rejected deletion of obsolete model directories outside the workspace
with the reason `blocked by policy`. Old BiRefNet/SDXL/recognition files are excluded from
configuration and the portable distribution; obsolete source integrations were removed.

## STORAGE AND LIMITS

Curated model files total 21.61 GiB: FLUX transformer 11.98 GiB, Mistral encoder 8.28 GiB,
VAE 0.31 GiB and Qwen 1.04 GiB. Backend packages measured 4.887 GiB before final packaging;
a conservative 5 GiB runtime allowance keeps the AI portion below the user's 30 GiB limit.
The app folder excludes future model downloads. Downloading and editing require additional free space.

FLUX is licensed for non-commercial use under its official terms. Packaging does not grant
commercial model rights. Another Windows x64 machine still needs compatible hardware/drivers;
CPU fallback exists but performance and memory requirements vary. Full weights may require
substantial Windows virtual memory on an 8 GiB computer.
