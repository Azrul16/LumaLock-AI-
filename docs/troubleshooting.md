# Troubleshooting

Extract the entire ZIP into a writable Windows x64 folder before opening LumaLockAI.exe.
Do not move only the EXE or launch it inside the archive. No Python installation is required.

If AI models are missing, complete first-run setup or use Settings / AI Models. The download
uses actual model files and upstream checksums; interrupted transfers may be retried. Gated
access, when required, needs acceptance of official terms and HF_TOKEN/normal HF login.
Never share a token in the archive. Manual controls and quick looks need no weights.

NVIDIA acceleration requires a compatible current driver. An 8 GiB RAM / 4 GiB GPU machine
may need substantial Windows virtual memory and smaller generation resolution. Qwen is
unloaded before FLUX; a reported OOM gets one smaller, stronger-offload retry. No runtime
promise is made. CPU-only machines use CPU fallback and can be much slower.

Technical logs are under data/logs and data/backend/backend.log next to the portable EXE.
Keep your source photos safe; exports and .luma projects use separate filenames. Classical
face/foreground/sky detection needs visual coverage review; paint protection for missed faces.
