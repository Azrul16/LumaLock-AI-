"""One prompt edits the selected result while retaining the original identity anchor."""

from pathlib import Path

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.prompt.local_model import interpret
from lumalock.core.exceptions import Cancelled, UserError
from lumalock.imaging.image_io import load_image
from lumalock.pipeline.creative_edit import creative_edit
from lumalock.project.edit_state import EditState, MaskLayer


def edit_chat_image(root, source, prompt, models, preserve_people, cancelled, progress):
    if not prompt.strip():
        raise UserError("Describe the edit you want to make.")
    for key in ("prompt", "flux"):
        if not models.available(key):
            raise UserError(
                "Install or repair the AI models using Models in the top bar, then retry."
            )
    if cancelled():
        raise Cancelled("Edit stopped.")
    original = load_image(root)
    current = original if Path(root).resolve() == Path(source).resolve() else load_image(source)
    if original.size != current.size:
        raise UserError("The selected image no longer matches the original photo dimensions.")
    state = EditState(identity_lock=preserve_people)
    if original.path != current.path:
        state.generated_file = str(current.path)
    progress(-1, "Preparing your edit locally…")
    plan = interpret(prompt, analyze(current.preview(1024)), state, models, cancelled, progress)
    if not plan.generative.enabled:
        raise UserError(
            "The editing director could not prepare this request. Please try a more specific prompt."
        )
    state.mode = "Creative" if plan.intent == "content_change" else "Preserve"
    whole = MaskLayer(
        id="chat-edit", name="Requested image edit", kind="rectangle", geometry=[0, 0, 1, 1]
    )
    return creative_edit(original.pixels, state, whole, plan, models, cancelled, progress)
