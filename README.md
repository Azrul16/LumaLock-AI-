# LumaLock AI

**Edit beautifully. Preserve identity.** A local Windows photo editor with a simple default
workspace, advanced photographic controls and an optional two-model AI workflow.

## Run the portable app

Open `dist/LumaLockAI/LumaLockAI.exe`. Keep the entire `LumaLockAI` folder together
in a writable location. Python and the local backend are bundled; no separate Python
installation is needed. First-run setup offers Qwen and FLUX downloads after license
acknowledgement. Model weights and personal photographs are excluded from the app folder.

Model files total about 21.61 GiB. The bundled AI runtime uses approximately 5 GiB; the AI
storage limit is 30 GiB. Leave extra space for downloads, working files and output.
Windows x64 is required. NVIDIA GPU acceleration needs a compatible current driver; CPU
fallback is slower and full FLUX still needs substantial memory/virtual memory.

The model choices are fixed: FLUX.2-dev Q2_K and Qwen2.5-1.5B-Instruct Q4_K_M. The FLUX
bundle includes its Mistral Q2_K encoder and VAE. No additional neural models are installed.
FLUX.2-dev uses the Non-Commercial License; each recipient must review and acknowledge it.
See [licenses](docs/licensing.md) and [verified status](docs/STATUS.md).

## Editing

Open a photo. Choose Natural, Portrait, Warm light, Low light or Cinematic for quick conventional
correction and adjust Look amount. These do not invoke the image model. Use AI Enhance or
enter a prompt to preview a Qwen plan, then Apply / Generate to run local FLUX.
Choose Creative AI and paint an editable area when adding/removing scene elements.
Paint face protection to preserve original pixels. Inspect protection coverage before generation.

Identity Lock defaults on. Natural AI uses identity/composition instructions; generation
excludes protected regions, recovers original protected pixels and verifies them exactly.
Classical detection can miss/profile faces; manual protection is always available. Structural
comparison measures image structure, not recognition probability or a guarantee of visual quality.

Compare shows a split view; hold Space on the canvas for the original. Manual controls provide
light, color, detail, effects, HSL, curves and crop/rotate/straighten. Advanced tools exposes
history, masks, versions, histogram, analysis and quality controls. Export writes a new file;
the source is never overwritten automatically. Save a `.luma` project to resume later.

## Source development

Use Python 3.11 in this project's `.venv`; never install globally or with `--user`.

```powershell
.\.venv\Scripts\python.exe launch.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe validate_photo.py 'my photo.jpg'
.\.venv\Scripts\python.exe diagnostics.py
.\.venv\Scripts\python.exe build.py
```

The source environment additionally needs the pinned ComfyUI and ComfyUI-GGUF checkout under
`runtime/comfyui` and project-local AI dependencies. `requirements-lock.txt` records the
Windows Python 3.11 environment. The standalone distribution is the intended recipient path.

Actual Qwen inference, backend startup and manual/photo acceptance tests have passed.
Full FLUX inference is **not yet validated**: at the user's request its weights download on
first startup. No generated-image result or ten-minute processing guarantee is claimed.
