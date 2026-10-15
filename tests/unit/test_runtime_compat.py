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


def test_file_backed_storage_survives_patcher_clone(tmp_path, monkeypatch):
    import ast
    import copy
    import os
    from pathlib import Path
    from types import SimpleNamespace

    root = Path(__file__).resolve().parents[2]
    plugin = root / "runtime/comfyui/custom_nodes/ComfyUI-GGUF/nodes.py"
    if not plugin.exists():
        import pytest

        pytest.skip("Pinned runtime is not present")
    loader = tmp_path / "custom_nodes/ComfyUI-GGUF/loader.py"
    loader.parent.mkdir(parents=True)
    loader.write_text(
        'data = {"config": {"num_vocab_tokens": 150000, "default_vocab_size": 131072}}'
    )
    nodes = loader.with_name("nodes.py")
    nodes.write_text(plugin.read_text(encoding="utf-8"), encoding="utf-8")
    patch_gguf_runtime(tmp_path)
    monkeypatch.setenv("LUMALOCK_KEEP_GGUF_MMAP", "1")
    tree = ast.parse(nodes.read_text(encoding="utf-8"))
    definition = next(
        item
        for item in tree.body
        if isinstance(item, ast.ClassDef) and item.name == "GGUFModelPatcher"
    )

    class Base:
        def clone(self, *args, **kwargs):
            return copy.copy(self)

    namespace = {
        "os": os,
        "comfy": SimpleNamespace(model_patcher=SimpleNamespace(ModelPatcher=Base)),
    }
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(nodes), "exec"), namespace)
    patched = namespace["GGUFModelPatcher"]
    original = Base()
    clone = patched.clone(original)
    assert isinstance(clone, patched)
    assert clone.mmap_released is True
    assert original.__class__ is Base
