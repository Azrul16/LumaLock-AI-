# Browser workflow validation

The interface supports photo input, direct prompts, Natural/Creative mode, deterministic
presets, manual protection, inline result saving/branching, retry, Stop and chat deletion.
Chat assets are immutable and independent of original source files. Shared images survive
chat deletion. Real Edge tests use explicit image-service fixtures to verify interactions;
they do not establish neural output quality. Actual FLUX results are recorded in STATUS.md.

The UI interaction references were the official image guides at
https://learn.chatgpt.com/docs/image-generation and https://learn.chatgpt.com/docs/image-inputs.
The app uses its own local backend and does not connect to those hosted image services.
