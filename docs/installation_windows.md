# Windows installation

For the portable release, extract LumaLockAI-Windows-x64.zip to a writable folder and open
LumaLockAI/LumaLockAI.exe. It contains Python and ComfyUI runtime dependencies. On first
startup, select the two model bundles, acknowledge FLUX's non-commercial terms and finish
setup. Downloads total about 21.61 GiB, in addition to the bundled runtime. Leave extra disk
space for extraction and working files. Use Windows x64 and a compatible NVIDIA driver for GPU.

Source development uses Python 3.11 in the project-local .venv. Install packages only with
.venv/Scripts/python.exe -m pip, never globally or with --user. The environment lock lists
versions and the official CUDA / llama-cpp CPU wheel indexes. Backend source is pinned under
runtime/comfyui, with ComfyUI-GGUF under custom_nodes; all installations remain in .venv.

Build the model-free portable package with .venv/Scripts/python.exe build.py --zip.
