# Photo quality review — 2026-10-15

## Verified problem

Inspected `my photo.jpg` and the real accepted output recorded in
`data/preview/flux-direct-acceptance.json`. Both files are 2048×2048. The edited
shirt stripes, jacket fabric and background are visibly softer; background structure
and clothing also drift. The protected face retains a sharper appearance. This is
degradation outside the protected region, not a successful overall quality upgrade.

The old Preview path fed only 384×384 to FLUX, used an 8-step base schedule
(4 actual denoising steps at strength 0.4), and Lanczos-resized back to 2048×2048.
Original-file integrity and exact protected pixels test safety, not photographic quality.
The recorded 891.89-second result is evidence for the old draft pipeline only.
It is not a benchmark for the new settings, and is not native 4K.

Detected hardware: RTX 3050 Laptop GPU, 4 GiB VRAM, 7.71 GiB RAM.
The active model bundle is ~20.57 GiB. CPU offload and OS paging remain major constraints.

## Applied corrections

- Removed the execution watchdog completely, including migration of old persisted limits.
  Explicit Stop and shutdown cancellation remain. Individual network requests still have
  timeouts, which do not impose a total inference deadline.
- Migrated old profiles to Quality: 1024px / 40 base steps. Maximum defaults to
  1536px / 50 base steps. Draft is explicitly 512px / 12 base steps. Partial denoising
  uses a subset of the base schedule; this is not a distilled four-step model.
- An OOM retry increases offloading but does not silently shrink generation dimensions.
  Failure at the selected resolution remains possible on this hardware.
- Save 4K image produces PNG with a minimum 3840px longest edge, preserving aspect
  ratio, retaining larger originals and leaving working assets/masks at original size.
  This enlargement currently uses Lanczos and explicitly records that fact in PNG metadata.
  It is not neural restoration. Square photos export at 3840×3840; 16:9 at 3840×2160.
- Exact Natural commands `auto enhance`, `professional enhance`, and `enhance this photo`
  with no preset or Professional Enhance now use measured full-resolution photo corrections,
  with denoising disabled. They do not regenerate faces, clothing or scenery. Extra prompt
  instructions are never discarded into this shortcut. Protection is restored afterwards.

## Research and recommendation

The recommended architecture separates full-resolution photographic adjustments from
generative content changes, composites only requested regions, preserves original subject
detail, then performs a separately measured 4K enlargement. A larger output canvas is not
evidence of recovered detail. Resolution, model precision, instruction following, protected
region integrity, seams and texture should each be evaluated independently.

| Project | Relevant evidence | Recommendation for this laptop |
| --- | --- | --- |
| [FLUX.2](https://github.com/black-forest-labs/flux2) | Official dev model is 32B; Klein 4B/9B are distilled editing models. | Existing dev stays functional. Benchmark Klein 4B with a higher precision quantization before any default switch; four distilled steps are different from truncating dev sampling. |
| [Klein 4B model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) | Apache 2.0, reference-image editing and CPU offload example, four-step example. | Best next local speed/quality candidate by engineering judgment, not a measured winner here. Card full-pipeline VRAM guidance (~13GB) exceeds this GPU. Quantization/offload still required. |
| [Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) | Authors report reduced drift and improved character consistency; official example uses 40 steps. | Useful alternative on more capable hardware; no evidence it is faster here. This is an image editor, different from the retired Qwen prompt interpreter. |
| [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | Quantized DiT loading enables low-memory operation. | Keep supported loaders, but compare model precision rather than assume Q2 quality equals higher precision. No measured quantization quality loss is claimed here. |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | Tiled processing, x2/x4 models, controllable denoising and optional face enhancement. | Benchmark tiled x2 on original-resolution composites. Keep face enhancement off by default and compare face detail with a neutral resize baseline. Not installed by this change. |
| [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | High-resolution segmentation and portrait matting; published memory depends on variant. | Candidate for whole-person protection. Hair, sleeves and edges need human inspection. No synthetic subject mask or claimed accuracy in current app. |
| [IC-Light](https://github.com/lllyasviel/IC-Light) | Foreground-conditioned illumination editing. | Specialized future relighting option, not a universal detail-preserving replacement. Must test geometry and skin texture. |
| [SUPIR](https://github.com/Fanghua-Yu/SUPIR) | Diffusion-based photographic restoration. | Not first choice for this memory-limited laptop; evaluate fidelity and resource cost before adding another generative restoration stage. |
| [chaiNNer](https://github.com/chaiNNer-org/chaiNNer) | Composable image-processing and upscale workflows. | Useful workflow reference: separate editing, restoration, resizing and save stages. No reason to add its entire GUI to this app. |

Official sources disagree in their compact-model VRAM examples (the FLUX repository
mentions ~8GB for Klein 4B; its model card describes ~13GB). Neither supports a claim
of unoffloaded full-pipeline operation on 4GB. Vendor sub-second claims do not predict
this laptop's latency. [BFL's 4MP output](https://docs.bfl.ai/flux_2/flux2_overview)
also must not be mistaken for 4K UHD (8.29MP) or a 3840px square (14.75MP).

## Acceptance gate before a model switch

Benchmark identical source images and prompts for lighting, object removal, background
replacement and a follow-up edit. Include portraits with glasses/hair and fine fabric.
Keep generation resolution, seed, quantization and steps in each report. Inspect matched
100% crops, compare against original-resolution adjustments and neutral resizing, verify
protected source pixels and unchanged originals, record wall time and peak RAM/VRAM.
Reject seam/ghosting, text or clothing drift when unrelated to the request. Do not use
global sharpness as a quality score: it can reward hallucination and oversharpening.

New high-resolution FLUX inference, Klein, neural 4K upscaling, automatic whole-person
segmentation and end-to-end quality comparisons remain unbenchmarked. No new model weights
were downloaded or silently substituted in this change.
