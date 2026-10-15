# Chat interface review ? 2026-10-15

Interaction references: [official image guide](https://learn.chatgpt.com/docs/image-generation)
and [image inputs](https://learn.chatgpt.com/docs/image-inputs). LumaLock uses its own brand
and local Qwen/FLUX models; it does not connect to ChatGPT or an OpenAI image service.

## Review 1 ? workflows and failure diagnosis

The reported frozen-app traceback was ModuleNotFoundError for lumalock.ai.generative.
Added explicit Python package markers, an explicit hidden import, release archive checks
and an executable backend-import diagnostic. The chat workspace supports image attachment,
prompt submission, result cards, saving, selecting earlier images, and follow-up edits.
Conversations use immutable managed images and preserve the first photo as the identity anchor.
GUI/integration tests exercise these transitions with injected image services; these tests do
not claim neural generation quality. First review: 62 tests passed.

Actual FLUX testing exposed the pinned GGUF plugin missing default_num_special_tokens.
The runtime applies the documented upstream correction from
https://github.com/city96/ComfyUI-GGUF/pull/479. A separate runtime correction selects GPU
compute with CPU offloading for the text encoder. CPU-only mode still selects CPU.

## Review 2 ? recovery, safety and layout

Checked restored conversations, retry after failures, cancellation, selection of an older
result, background export and filename extensions. The same-size model-corruption regression
caught a timestamp-cache gap on Windows; removed the cache so integrity verification always
hashes the complete file. Adjusted image scaling for narrow windows and compact user attachment
thumbnails. Smoke screenshots wait for the Qt layout to settle after background image loading.
Corrected suite: 64 tests passed. Source GUI photo launch passed. Packaged checks and the real
FLUX result are recorded in STATUS.md once observed; no successful generation is assumed.
