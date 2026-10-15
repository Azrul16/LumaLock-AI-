from lumalock.comfy.compat import patch_gguf_runtime


def test_pinned_gguf_tokenizer_correction_is_idempotent(tmp_path):
    loader = tmp_path / "custom_nodes/ComfyUI-GGUF/loader.py"
    loader.parent.mkdir(parents=True)
    loader.write_text(
        'data = {"config": {"num_vocab_tokens": 150000, "default_vocab_size": 131072}}'
    )
    nodes = loader.with_name("nodes.py")
    nodes.write_text(
        'options = {"initial_device": comfy.model_management.text_encoder_offload_device()}'
    )
    patch_gguf_runtime(tmp_path)
    fixed = loader.read_text()
    assert '"default_num_special_tokens": 1000' in fixed
    patch_gguf_runtime(tmp_path)
    assert loader.read_text() == fixed
    assert nodes.read_text().count('"load_device"') == 1
