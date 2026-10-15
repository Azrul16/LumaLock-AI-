# AI engine

Exactly one main image model is configured: city96/FLUX.2-dev-gguf, flux2-dev-Q2_K.gguf,
pinned to the revision in config/models.yaml. Its required Mistral conditioning encoder and
FLUX VAE are support components of the same image pipeline, not standalone prompt services.
The transformer is 12,858,250,208 bytes, encoder 8,890,338,848 bytes and VAE 336,213,556 bytes.
Together they occupy approximately 20.57 GiB. Normal Python libraries are not model storage.

`download_models.py` downloads only this bundle; --verify hashes it and --list inspects its
pinned download plan. Use project-local .venv Python. Manifests publish only after upstream
SHA-256 checks succeed. Every required file is verified before inference.

The current laptop has 4 GiB GPU VRAM and 7.71 GiB RAM. The weights exceed physical memory,
so paging and long execution remain possible. Preview reduces resolution and sampling work.
No total execution cap is applied. Explicit Stop remains available. Higher resolution can take substantially longer.
