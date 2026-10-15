"""Small documented compatibility correction for the pinned GGUF runtime."""

from lumalock.core.exceptions import UserError


def patch_gguf_runtime(root):
    # Upstream fix: https://github.com/city96/ComfyUI-GGUF/pull/479
    loader = root / "custom_nodes" / "ComfyUI-GGUF" / "loader.py"
    if not loader.is_file():
        raise UserError("The GGUF runtime plugin is missing. Repair the app folder.")
    old = '"config": {"num_vocab_tokens": 150000, "default_vocab_size": 131072}'
    new = '"config": {"num_vocab_tokens": 150000, "default_vocab_size": 131072, "default_num_special_tokens": 1000}'
    source = loader.read_text(encoding="utf-8")
    if old in source:
        loader.write_text(source.replace(old, new), encoding="utf-8")
    elif '"default_num_special_tokens"' not in source:
        raise UserError("The GGUF tokenizer runtime is incompatible. Repair the app folder.")
    # LOW_VRAM otherwise runs the whole 24B encoder on CPU. Comfy's supported
    # load_device option permits GPU compute with CPU initial/offload storage.
    nodes = root / "custom_nodes" / "ComfyUI-GGUF" / "nodes.py"
    if nodes.is_file():
        source = nodes.read_text(encoding="utf-8")
        old = '"initial_device": comfy.model_management.text_encoder_offload_device()'
        new = '"load_device": comfy.model_management.get_torch_device(),\n                "initial_device": comfy.model_management.text_encoder_offload_device()'
        if (
            old in source
            and '"load_device": comfy.model_management.get_torch_device()' not in source
        ):
            source = source.replace(old, new)
        # Keep file-backed quantized storage on memory-limited machines. The plugin's
        # eager mmap-detach copies whole encoders/transformers into private RAM/pagefile.
        if "    mmap_released = False" in source:
            if "import os\n" not in source:
                source = "import os\n" + source
            source = source.replace(
                "    mmap_released = False",
                '    mmap_released = os.environ.get("LUMALOCK_KEEP_GGUF_MMAP") == "1"',
            )
        clone_old = 'n.mmap_released = getattr(self, "mmap_released", False)'
        clone_new = 'n.mmap_released = os.environ.get("LUMALOCK_KEEP_GGUF_MMAP") == "1" or getattr(self, "mmap_released", False)'
        if clone_old in source:
            if "import os\n" not in source:
                source = "import os\n" + source
            source = source.replace(clone_old, clone_new)
        nodes.write_text(source, encoding="utf-8")
