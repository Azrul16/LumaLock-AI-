"""Prepare prompt plans and required cached masks before offering a preview."""

import uuid
from dataclasses import dataclass

from lumalock.ai.prompt.local_model import interpret
from lumalock.ai.prompt.parser import apply_plan
from lumalock.ai.prompt.schema import EditPlan
from lumalock.core.exceptions import Cancelled
from lumalock.project.edit_state import EditState, MaskLayer


@dataclass
class PreparedPrompt:
    plan: EditPlan
    state: EditState
    prompt: str


def prepare_prompt(prompt, image, analysis, state, models, segmentation, cancelled, progress):
    plan = interpret(prompt, analysis, state, models, cancelled, progress)
    if plan.generative.enabled or plan.confidence < 0.4:
        return PreparedPrompt(plan, state, prompt)
    for region in plan.regions:
        if cancelled():
            raise Cancelled("Prompt edit cancelled.")
        if not any(layer.kind == region.region for layer in state.masks):
            if region.region == "custom":
                from lumalock.core.exceptions import UserError

                raise UserError("Create a custom mask before applying this regional prompt.")
            path = segmentation.create(image, region.region, cancelled, progress)
            state.masks.append(
                MaskLayer(
                    id=uuid.uuid4().hex,
                    name=region.region.title(),
                    kind=region.region,
                    mask_file=str(path),
                )
            )
            if region.region in ("subject", "background") and True:
                plan.explanation += " Subject uses classical GrabCut; inspect its coverage."
    return PreparedPrompt(plan, apply_plan(state, plan), prompt)
