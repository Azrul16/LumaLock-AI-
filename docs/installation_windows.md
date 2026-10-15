# Windows source installation

Use Python 3.11 in the project-local .venv. Install only with
`.venv/Scripts/python.exe -m pip`; never install globally or with --user.
The existing runtime/comfyui checkout and required GGUF plugin use the same environment.
Transformers remains necessary for FLUX's own conditioning pipeline.

Start Launch LumaLock AI.cmd. It opens the browser automatically; keep the terminal open.
Settings handles the FLUX bundle's license, progress, pause/resume and verification. Models
live in root models/flux; chats/settings/logs live in root data. Back these up when moving.
The current source environment is not a standalone portable EXE/ZIP distribution.
