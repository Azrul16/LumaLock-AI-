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
            nodes.write_text(source.replace(old, new), encoding="utf-8")
