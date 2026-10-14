# Two local AI models

The editor uses only Qwen2.5-1.5B-Instruct Q4_K_M for prompt planning and FLUX.2-dev Q2_K
for image editing. The FLUX pipeline necessarily includes its supporting text encoder and VAE;
these are components of the FLUX bundle, not alternative image editors.

| File | GiB | Source |
| --- | ---: | --- |
| flux2-dev-Q2_K.gguf | 11.98 | city96/FLUX.2-dev-gguf |
| Mistral-Small-3.2-24B-Instruct-2506-Q2_K.gguf | 8.28 | unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF |
| flux2-vae.safetensors | 0.31 | Comfy-Org/flux2-dev |
| qwen2.5-1.5b-instruct-q4_k_m.gguf | 1.04 | Qwen/Qwen2.5-1.5B-Instruct-GGUF |

Total weights: 21.61 GiB. Runtime allowance: 5 GiB. Limit: 30 GiB.
`config/models.yaml` pins immutable revisions. Downloading checks complete metadata/storage,
fetches only curated files, reuses completed verified weights and checks upstream SHA-256.
Installation markers appear only after all bundle files are verified. No duplicate precision
variants are installed. Transfers can be cancelled between files and resumed/reused on retry.

First-run setup or Settings / AI Models performs downloads. HF_TOKEN or normal Hugging Face
CLI authentication may be used if repository access needs it; tokens are never bundled or logged.
Official gated FLUX access requires terms acceptance in the recipient's own account if used.
The selected quantized/support repositories are publicly accessible at the pinned revisions.

After download, inference is local and offline. Qwen runs CPU GGUF and unloads before a private
ComfyUI process starts. FLUX uses low-VRAM GGUF loading, CPU VAE, uncached workflows and
one smaller/stronger-offload retry for reported OOM. Unsupported/missing weights give clear errors.

No actual FLUX output has been validated yet because the user deferred weights until first-run setup.
Do not interpret backend availability, contract tests or conventional quick looks as a trained-model benchmark.
