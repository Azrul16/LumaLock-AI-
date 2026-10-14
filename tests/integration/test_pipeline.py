import numpy as np
import pytest
from PIL import Image

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.prompt.parser import apply_plan, parse_prompt
from lumalock.core.exceptions import UserError
from lumalock.export.exporter import ExportOptions, export_image
from lumalock.imaging.image_io import load_image
from lumalock.pipeline.renderer import render
from lumalock.project.edit_state import EditState, MaskLayer
from lumalock.project.history import History
from lumalock.project.serialization import load_project, save_project


@pytest.mark.parametrize("suffix", [".jpg", ".png", ".webp", ".tiff"])
def test_open_analyze_prompt_export(photograph, local_storage, suffix):
    source = local_storage / "source.png"
    Image.fromarray(photograph).save(source)
    document = load_image(source)
    state = apply_plan(
        EditState(),
        parse_prompt("Make this warmer and cinematic", analyze(document.pixels), EditState()),
    )
    pixels = render(document.pixels, state)
    target = local_storage / f"edited{suffix}"
    export_image(document, pixels, target, ExportOptions())
    assert Image.open(target).size == document.size
    np.testing.assert_array_equal(load_image(source).pixels, photograph)
    with pytest.raises(UserError):
        export_image(document, pixels, source)


def test_project_save_load_with_mask(photograph, local_storage):
    source = local_storage / "source.png"
    Image.fromarray(photograph).save(source)
    mask = local_storage / "mask.npy"
    np.save(mask, np.ones(photograph.shape[:2], np.float32))
    history = History()
    state = history.state
    state.adjustments.exposure = 0.3
    state.masks.append(MaskLayer(id="face", name="Face", kind="face", mask_file=str(mask)))
    history.push("Edit", state)
    history.save_version("Warm version", state)
    project = local_storage / "test.luma"
    save_project(project, source, history, ["warmer"])
    reopened, loaded, prompts = load_project(project)
    assert reopened == source and prompts == ["warmer"]
    np.testing.assert_array_equal(render(photograph, loaded.state), render(photograph, state))
    assert loaded.index == 1 and loaded.undo().adjustments.exposure == 0
    assert loaded.versions["Warm version"].adjustments.exposure == 0.3


def test_missing_asset_not_silently_ignored(photograph):
    state = EditState(
        masks=[MaskLayer(id="missing", name="Missing", kind="face", mask_file="not-found.npy")]
    )
    with pytest.raises(UserError):
        render(photograph, state)
