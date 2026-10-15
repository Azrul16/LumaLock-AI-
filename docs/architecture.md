# Architecture

Image + original-language prompt -> deterministic PromptBuilder -> FLUX.2-dev Q2_K ->
protection compositor -> immutable result in chat.

`ai/prompt/prompt_builder.py`, templates.py and presets.py contain ordinary Python logic.
Natural is the default; explicit Creative mode permits only requested scene changes.
OpenCV/NumPy statistics guide Auto Enhance. No separate neural prompt interpreter exists.
The required text-conditioning encoder and VAE belong to the FLUX pipeline.

A loopback aiohttp server serves local HTML/CSS/JavaScript. Session/Origin checks protect
mutations. One executor owns AI work; the browser renders authoritative durable chat state.
CPU host processing and supported CUDA transfers use bounded concurrency. Workers are
contained in a Windows job object; terminal closure stops them. There is no total execution deadline.
Low-RAM runs retain file-backed GGUF storage instead of eagerly copying complete weights
into private RAM. Memory recovery keeps the requested resolution and may offload VAE work to CPU.

Original identity anchors remain fixed across result branches. User-painted normalized masks
are stored with chat turns, rasterized classically and restored from original pixels. Full
image export is separate from bounded browser previews. Source photos are never overwritten.

Exact Natural auto-enhance commands use original-resolution photographic adjustments.
Other edits use FLUX at the selected generation resolution. Save 4K image separately
exports at least 3840px on the long edge; current enlargement is Lanczos, not neural
restoration. See quality-research.md for the verified failure and candidate architecture.
