# LumaLock AI status

## CURRENT: local browser app (2026-10-15)

### Chat deletion and bounded CPU/GPU coordination

Each sidebar chat now has a Delete chat button with confirmation. The authenticated DELETE
endpoint removes that conversation's metadata and unshared managed images, keeps other chats
and original files, and creates a fresh empty chat when the last chat is deleted. Deletion is
blocked while work is active. Unreadable remaining chat metadata suppresses image reclamation
to protect potentially shared assets; preview RAM is cleared after a deletion.

Automatic device selection is labelled CPU + GPU on NVIDIA machines. Supported native
weight transfers may overlap host work and CUDA compute through one asynchronous offload
stream. CPU-only mode and stronger memory recovery disable asynchronous offloading. Qwen
still unloads before the much larger image models; no full-model simultaneous residency or
100% utilization target is claimed. The installed GGUF implementation does not use every
native ComfyUI transfer optimization, so full FLUX acceleration remains unverified.

The real CUDA VAE roundtrip passed with one stream (43% maximum observed GPU utilization,
287 MiB reported GPU use, 45.64 seconds including startup under concurrent test load).
This is a compatibility check, not a controlled speed comparison. Evidence:
data/preview/gpu-vae-async-result.json. The user's source photo SHA-256 remained unchanged.
See [ComfyUI offload options](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/cli_args.py)
and [PyTorch transfer behavior](https://docs.pytorch.org/tutorials/intermediate/pinmem_nonblock.html).

Cleanup was attempted again for dist/build/caches and obsolete Qt bytecode, using checked
PowerShell paths. Automatic approval review rejected both actions with "blocked by policy";
those paths remain untouched. The earlier 0.64 GiB of unused dependencies remains removed.
Models and personal data were preserved. No alternative deletion route was used.
Validation: all 88 tests passed (32.12 seconds), including real Edge confirmation/cancel,
deletion and reload checks; the updated source server passed its isolated launch smoke test.

### CUDA VAE device correction

The observed zero GPU usage was confirmed during reference-photo encoding: the worker had
CUDA selected but the launcher unconditionally passed --cpu-vae. Auto/NVIDIA modes now use
CUDA for tiled VAE encoding/decoding on the first attempt. Explicit CPU mode and the stronger
OOM retry retain CPU VAE offloading. Explicit GPU mode reports an error if no NVIDIA GPU is
detected or the runtime fails to initialize CUDA. NO_VRAM still means weight offloading,
not disabling CUDA compute. Planning messages identify Qwen's deliberate CPU execution;
encoding stages identify the selected device or CPU memory fallback.

Verified with an actual 256x256 roundtrip through the installed FLUX VAE on the user's photo:
the worker logged VAE load device cuda:0, dtype bfloat16; encode/decode completed without OOM.
Observed GPU utilization reached 51%, with 224 MiB reported GPU memory use during polling.
The complete probe, including worker startup, took 27.27 seconds. The original SHA-256 was
unchanged. Evidence: data/preview/gpu-vae-result.json. This verifies VAE CUDA execution,
not full FLUX generation quality or speed. CPU/disk work during planning, checksum verification
and loading can still coincide with a real 0% GPU reading. All 83 automated tests passed.

### Single progress display and browser recovery fixes

Edit progress, percentage, elapsed time, ETA and Stop now live only in the image skeleton
card. The composer banner is hidden when that card owns the active edit. Model setup likewise
uses its dialog progress while open, with a single fallback banner when the dialog is closed.
Upload/submission and edits running in another chat retain their fallback status/Stop access.

Fixed stale polling failures overriding newer successful state, lingering disconnected notices
after reconnection, and loss of newly typed prompt drafts when an earlier submission returns.
Real Edge regressions cover single visible progress, Stop, refresh, model dialog open/close,
stale requests, reconnection and retaining a newly typed draft. Existing inference limitations
remain unchanged; these are browser workflow fixes.
Validation: all 79 tests passed (24.90 seconds), including the new browser regressions;
the isolated web-server launch smoke test and Ruff checks passed.

### Resource monitor and two performance reviews

- Top-right live system CPU/RAM/GPU utilization, with GPU memory/temperature, disk read/write
  rates and project-drive free space in an accessible dropdown. These are measured readings,
  not benchmark scores. Unsupported/stale values show unavailable. A background sampler
  caches readings, throttles NVIDIA probes, and never imports torch into the web server.
- Browser image cards now use bounded-size display previews; Save still downloads the original
  full-resolution result. Preview decoding is serialized and its RAM cache is capped at 8 MiB.
- Low-memory inference uses native tiled VAE encoding/decoding, bounded CPU/BLAS thread pools,
  and one hardware probe per worker launch. Sampling quality settings and model choices stay
  unchanged. Cancellation no longer triggers a memory-retry after Stop; worker assignment
  failures clean up the owned process. Restart now selects the most recent conversation.
- Full-frame float compositing was replaced by bounded strips. A single synthetic 2048x2048
  CPU comparison measured 256 MiB versus 28 MiB peak temporary allocations with identical
  output SHA-256. Times were 0.2408 versus 0.2601 seconds: this is a memory reduction, not a
  demonstrated inference speedup. Details: data/preview/performance-review.json.
- Removed Qt/PDF/WebEngine and PyInstaller packages from the project .venv, reducing its
  measured footprint from about 5.99 GiB to 5.346 GiB. Refreshed editable metadata and the
  dependency lock; pip check reports no broken requirements. No global packages changed.
- Review 1 passed 72 tests; review 2 passed 79 tests, including telemetry, unavailable
  readings, preview bounds, pixel-identical compositing, cancellation and restored chat order.
  Source launch smoke test and actual backend import diagnostic passed.
- The restarted app was checked in real Microsoft Edge at desktop and 390px mobile widths:
  actual CPU/RAM/GPU readings appeared, the resource dropdown stayed within the viewport and
  no JavaScript errors occurred. Screenshots: data/preview/resource-monitor-desktop.png and
  data/preview/resource-monitor-mobile.png. No owned AI worker remained after cancellation.

Research references: [NVIDIA telemetry query documentation](https://docs.nvidia.com/deploy/nvidia-smi/index.html),
[psutil measurement API](https://psutil.readthedocs.io/stable/index.html), and
[PyTorch cache limitations](https://docs.pytorch.org/docs/stable/generated/torch.cuda.memory.empty_cache.html).
The pinned ComfyUI nodes.py schemas were inspected for tiled VAE compatibility. Clearing
unused CUDA cache cannot free live model tensors, so it is not presented as a memory cure.

The storage audit found about 90 GiB free on C: and 72 GiB on D:. High disk activity can
reflect Windows paging; it is separate from storage capacity. After the cancelled edit no
owned AI worker remained; system RAM still included the user's editor and browser processes.
FLUX weights plus encoder exceed physical RAM on this device, so paging and long inference
remain possible. No successful full FLUX run or general speedup is claimed for these changes.

Automatic approval review again blocked deleting dist/build/caches and the obsolete partial
download (reason: "blocked by policy"). Those files remain; no alternate deletion method was
used. Complete model weights, photos, chats and projects were preserved.

Progress update: animated image skeletons now appear inline while editing, with visible
current-stage percentage, elapsed time and estimated stage time remaining. Sampling counts
come from the owned ComfyUI websocket, not a simulated timer. Estimates require at least two
measured progress points and reset on stage changes, retries or stalled progress. Loading,
planning and decoding remain indeterminate when no counts are available. The estimate is for
the current stage, not a promise of total edit completion time. Reduced-motion settings disable
the shimmer. The model setup dialog also shows percentage, elapsed time and available estimates.

Validation: 72 tests passed, including real Edge progress/reload/cancel checks, conservative
timing regressions, a local websocket protocol fixture and worker recovery tests. The updated
source server passed its launch smoke test. These telemetry tests do not establish successful
end-to-end FLUX output on this hardware. The running edit was stopped at the user's request
to activate the updated server; prior conversations and images were retained.

This section supersedes the historical desktop-release notes below.
Open **Launch LumaLock AI.cmd** in the project root. It starts the project-local Python
server in the foreground and opens the browser. Closing its CMD or pressing Ctrl+C stops
the server; owned inference workers are contained in a Windows kill-on-close job. Closing
only the browser tab leaves the server running. The old launcher forwards to this launcher.

All four complete model weight files were moved out of dist into root **models/**:
Qwen 1,117,320,736 bytes; FLUX 12,858,250,208 bytes; Mistral 8,890,338,848 bytes;
VAE 336,213,556 bytes. Migration evidence: data/preview/model-migration.json.
Chats, assets, projects, settings and logs were preserved under root **data/**.
Source photographs were retained. No global Python packages were installed.

The HTML/CSS/JavaScript interface supports photo upload/drop/paste, prompts, inline results,
PNG saving, Edit image branching, persisted conversations, retry and cancellation. Model
setup includes actual progress, Pause, resume/repair, checksum verification and explicit
license acknowledgement. The API is loopback-only with local session/Origin protections.
Qt UI source and its tests have been removed; the browser has no manual mask or project editor.

Review 1 passed 63 automated tests, including real Microsoft Edge browser workflows using
explicit image-service test doubles. Two additional real Windows tests verified CMD termination
stops the server and server termination kills its owned worker. Review 2 corrected garbled
Unicode symbols and obsolete no-face guidance; final suite results are recorded below.
Source web launch smoke test passed on 127.0.0.1:7860.
Final second review: **65 tests passed in 15.87 seconds**; Ruff checks passed.
The actual CMD-launched server was opened in Microsoft Edge: both model bundles reported
complete and runtime available, with no JavaScript errors. Screenshot: data/preview/web-final-models.png.

LIMITATION: Actual Qwen inference and complete model checksums were previously verified.
Real FLUX testing encountered GPU memory exhaustion on this 4 GiB GPU / 7.71 GiB RAM machine.
Smaller retry and offloading fixes have regression coverage, but successful full neural image
generation remains unverified. UI workflow tests do not establish model quality. Classical
face protection is not an identity-recognition guarantee and may miss faces.

Automatic approval review rejected deleting dist and its ZIP with the reason "blocked by policy".
These legacy artifacts remain unused. It also rejected rewriting README and several guides;
their desktop/EXE instructions are obsolete. Use this section for current launch instructions.

Updated 2026-10-15. Windows x64; RTX 3050 Laptop 4 GiB, 7.71 GiB RAM.
All package installations use the project-local `.venv`. No global Python packages installed.

## DONE

- Non-destructive PySide6 editor: manual light/color/detail/effects controls, HSL and curves,
  history, undo/redo, named versions, .luma projects, autosave, original/split comparison,
  zoom/pan and JPEG/PNG/WebP/TIFF export with source overwrite protection.
- Default chat workspace: attach/drop photos, send prompts, inline result images, Save image and
  Edit image, follow-ups, branching, saved conversations, retry and Stop. Advanced editor
  retains manual controls, masks, histogram, geometry and .luma projects.
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
- 64 automated tests pass, including geometry, masks, prompt/state validation, hostile-backend
  protection enforcement and GUI synchronization. Tests with injected backends are contract checks.

## PORTABLE APP VERIFIED

The completed app is in `dist/LumaLockAI`; open `LumaLockAI.exe` and keep its folder intact.
The EXE launches with the user photo from a temporary working directory with Python removed
from PATH. The bundled isolated Python imports PyTorch and detects CUDA; its ComfyUI process
starts and registers all required FLUX/GGUF nodes. No developer Python installation is needed.
First-run setup offers both required model bundles, license acknowledgement, storage preflight
and downloads. Future builds omit ZIP packaging at the user's request. Automatic approval review blocked
cleanup commands, including explicitly named ZIP files and obsolete helpers; existing artifacts remain.

## CHAT REVISION AND TWO REVIEW PASSES

See [chat-review.md](chat-review.md) for the review record and primary interface references.
Review 1 passed 62 tests; review 2 and its corrections passed 64 tests. Additional targeted
chat/model/runtime regressions passed after final layout changes. Source desktop launch with
the actual user photo passed; visual inspection confirmed the attached image and composer.

The reported frozen-app crash was `ModuleNotFoundError: lumalock.ai.generative`.
Explicit package markers and a hidden import correct lazy-module discovery. Build verification
checks the executable archive for FLUX, workflow and chat modules, and `--check-backend` tests
actual frozen imports. The final release is being rebuilt and checked before handoff.

Local conversations retain immutable image versions and the initial photo as the identity
anchor. Selecting Edit on an older result changes the next prompt's reference without
changing that anchor. Failed/cancelled requests remain retryable. Chat export protects user
originals and managed history assets. File exports run in a background worker.

The second review caught unreliable timestamp-based checksum caching on Windows; the cache
was removed. Verification hashes every required model file in full, detecting same-size edits.

## MODELS AND REAL GENERATION TEST

Qwen and all three FLUX components are completely downloaded in `dist/LumaLockAI/models`.
All required files have passed full SHA-256 verification. Model setup retains its progress,
pause/resume, retry/repair, license acknowledgement and readiness checks for fresh installations.

Actual FLUX testing identified missing tokenizer metadata in the pinned GGUF plugin. The
runtime applies the documented upstream `default_num_special_tokens` correction. The text
encoder now uses GPU compute with CPU offloading on supported hardware, rather than being
forced entirely onto CPU in LOW_VRAM mode. CPU-only mode still selects CPU. Backend source
is bundled and local compatibility corrections are recorded in `lumalock/comfy/compat.py`.

The real user-photo test has passed the tokenizer/text-encoding stage and reached the FLUX
image model. A final image has not yet been observed; successful full inference and image
quality are not claimed while this test is running. This 4 GiB GPU / 7.71 GiB RAM computer
requires heavy offloading and Windows virtual memory; no processing-time guarantee is made.

## BLOCKED

Automatic approval review rejected deletion of obsolete model directories outside the workspace
with the reason `blocked by policy`. Old BiRefNet/SDXL/recognition files are excluded from
configuration and the portable distribution; obsolete source integrations were removed.

## STORAGE AND LIMITS

Curated model files total 21.61 GiB: FLUX transformer 11.98 GiB, Mistral encoder 8.28 GiB,
VAE 0.31 GiB and Qwen 1.04 GiB. Backend packages measured 4.887 GiB before final packaging;
a conservative 5 GiB runtime allowance keeps the AI portion below the user's 30 GiB limit.
The app folder stores models as setup downloads them. Downloading and editing require additional free space.

FLUX is licensed for non-commercial use under its official terms. Packaging does not grant
commercial model rights. Another Windows x64 machine still needs compatible hardware/drivers;
CPU fallback exists but performance and memory requirements vary. Full weights may require
substantial Windows virtual memory on an 8 GiB computer.
