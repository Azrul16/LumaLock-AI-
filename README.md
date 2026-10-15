# LumaLock AI

**Edit beautifully. Preserve identity.** A local Windows photo editor with a simple default
workspace, advanced photographic controls and an optional two-model AI workflow.

## Run the portable app

Open `dist/LumaLockAI/LumaLockAI.exe`. Keep the entire `LumaLockAI` folder together
in a writable location. Python and the local backend are bundled; no separate Python
installation is needed. First-run setup offers Qwen and FLUX downloads after license
acknowledgement. Fresh builds omit model weights. Setup stores downloaded models beside the app; personal photographs are never bundled.

Model files total about 21.61 GiB. The bundled AI runtime uses approximately 5 GiB; the AI
storage limit is 30 GiB. Leave extra space for downloads, working files and output.
Windows x64 is required. NVIDIA GPU acceleration needs a compatible current driver; CPU
fallback is slower and full FLUX still needs substantial memory/virtual memory.

The model choices are fixed: FLUX.2-dev Q2_K and Qwen2.5-1.5B-Instruct Q4_K_M. The FLUX
bundle includes its Mistral Q2_K encoder and VAE. No additional neural models are installed.
FLUX.2-dev uses the Non-Commercial License; each recipient must review and acknowledge it.
See [licenses](docs/licensing.md) and [verified status](docs/STATUS.md).

## Edit in chat

1. Click **+ Photo** or drop a photo into the chat.
2. Describe the change and press **Send** (Enter). Shift+Enter adds a new line.
3. The returned image appears in the conversation with **Save image** and **Edit image**.
4. Click **Edit image** on any result to continue from that version. A normal follow-up
   automatically uses the latest result. The original identity reference stays fixed.

Chats and image versions are saved locally. The sidebar reopens earlier conversations.
Errors appear beside the request with **Retry edit**; Stop cancels work without losing earlier
results. Preserve people defaults on and recovers original protected face pixels. Review
coverage carefully: classical detection can miss faces. Use Advanced editor for manual masks,
light/color controls, crop, projects and conventional model-free editing. For a scene without
people, you can explicitly switch Preserve people off.

**Models & settings** manages downloads, checksum verification and repair. Quality controls
trade processing time for image resolution and sampling steps. Your photos stay on this device.

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

AI setup uses a dedicated progress dialog with real downloaded bytes, speed, remaining time,
pause, retry and resume. Missing files or an incomplete component bundle cannot be marked ready.
Downloads publish the installation manifest only after all files pass upstream SHA-256 checks;
model integrity is checked before inference. AI actions open setup when a model is missing.
Settings provides Download / Repair and Verify, with current file status. App updates preserve
existing models and settings.

64 automated tests, actual Qwen inference, backend startup, standalone EXE launch and acceptance
tests on the user photo have passed. Qwen is complete and SHA-256 verified in this installation.
All FLUX components are now downloaded and have passed checksum verification. The real
FLUX image test is still in progress; see docs/STATUS.md for the verified result and limits.
