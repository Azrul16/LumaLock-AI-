# Third-party licenses

LumaLock application source is MIT. This does not grant rights to model weights or dependencies.

| Component | Terms / source |
| --- | --- |
| FLUX.2-dev Q2_K and VAE | FLUX Non-Commercial License; [official terms](https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md) |
| Mistral 3.2 supporting encoder | Review [upstream model card](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506); retain Apache-2.0 notices |
| Qwen2.5-1.5B Instruct GGUF | [Official quantized model](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF), Apache-2.0 |
| ComfyUI | GPL-3.0; pinned corresponding backend source is included in the portable runtime |
| ComfyUI-GGUF | Apache-2.0; source and upstream license retained |
| llama-cpp-python / llama.cpp | Retain bundled MIT notices |
| OpenCV cascades | Retain OpenCV and cascade-specific notices |
| PySide6 / Qt | Applicable LGPL/GPL/commercial terms; dynamic Qt libraries and notices included |

Each recipient acknowledges FLUX terms before downloading. No token, weights or private
photographs are distributed in the ZIP. The executable's license does not authorize selling
or commercially deploying the FLUX model. Review the actual upstream terms for intended use.

Pinned backend source: ComfyUI `e0a32bce84f4603f2b61b16b50f8958e68fd6171`,
ComfyUI-GGUF `6ea2651e7df66d7585f6ffee804b20e92fb38b8a`.
Dependency license files are retained under `third_party_licenses` in the distribution.
