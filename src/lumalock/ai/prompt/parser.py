"""Deterministic fallback with relative follow-ups and cautious content routing."""

import re

from lumalock.ai.prompt.schema import EditPlan, GenerativeOptions, RegionAdjustment
from lumalock.pipeline.auto_enhance import auto_plan
from lumalock.presets.builtins import PRESETS
from lumalock.project.edit_state import Adjustments, EditState


def parse_prompt(prompt: str, analysis, current: EditState) -> EditPlan:
    text = prompt.lower().strip()
    if not text:
        return EditPlan(confidence=0, explanation="Enter an editing request.")
    content = re.search(r"\b(add|insert|replace|remove|erase|delete)\b", text)
    if content and not re.search(r"\b(remove|reduce) (noise|grain|haze|color cast)\b", text):
        return EditPlan(
            intent="content_change",
            generative=GenerativeOptions(enabled=True, prompt=prompt),
            explanation="This changes image content and requires Creative Mode and an editable mask.",
        )
    values = {}
    if any(word in text for word in ("professional", "fix", "natural", "lighting")):
        values.update(auto_plan(analysis).global_adjustments.model_dump(exclude_defaults=True))
    for name, preset in PRESETS.items():
        if name.lower() in text:
            values.update(preset)
    for words, key, value in [
        (("warm", "afternoon", "golden"), "temperature", 0.18),
        (("cold", "cool", "blue hour"), "temperature", -0.16),
        (("cinematic",), "contrast", 0.14),
        (("moody",), "exposure", -0.18),
        (("vibrant", "vivid"), "vibrance", 0.22),
        (("dark", "darker"), "exposure", -0.3),
        (("soft",), "clarity", -0.10),
        (("high contrast",), "contrast", 0.25),
        (("low contrast",), "contrast", -0.2),
        (("noise", "denoise"), "denoise", 0.25),
        (("sharp", "sharpen"), "sharpening", 0.2),
    ]:
        if any(word in text for word in words):
            values[key] = value
    if "black and white" in text or "monochrome" in text:
        values["saturation"] = -1
    regions = []
    bright = any(word in text for word in ("bright", "lift", "lighten"))
    target = "face" if "face" in text else "subject" if " me" in text or "subject" in text else None
    if bright and target:
        regions.append(RegionAdjustment(region=target, adjustments=Adjustments(exposure=0.25)))
    elif bright:
        values["exposure"] = 0.25
    if "sky" in text:
        regions.append(
            RegionAdjustment(region="sky", adjustments=Adjustments(highlights=-0.25, vibrance=0.15))
        )
    if any(word in text for word in ("less warm", "reduce warmth", "less cool")):
        existing = current.adjustments.temperature
        values["temperature"] = existing * 0.55
    elif "less" in text or "reduce the effect" in text:
        values = {key: value * 0.6 for key, value in current.adjustments.model_dump().items()}
    if "slightly" in text or "a little" in text:
        values = {key: value * 0.6 for key, value in values.items()}
    if not values and not regions:
        return EditPlan(
            confidence=0.2,
            explanation="This manual adjustment was not recognized. Use the image chat for direct natural-language FLUX editing.",
        )
    return EditPlan(
        intent="regional" if regions else "style",
        global_adjustments=Adjustments(**values),
        regions=regions,
        confidence=0.7,
        explanation="Photographic adjustments; existing pixels and composition are preserved.",
    )


def apply_plan(current: EditState, plan: EditPlan) -> EditState:
    state = current.model_copy(deep=True)
    data = state.adjustments.model_dump()
    data.update(plan.global_adjustments.model_dump(exclude_unset=True))
    state.adjustments = Adjustments.model_validate(data)
    for region in plan.regions:
        layers = [mask for mask in state.masks if mask.kind == region.region]
        if not layers:
            raise ValueError(f"Create a {region.region} mask before applying this plan.")
        layer = layers[-1]
        local = layer.adjustments.model_dump()
        local.update(region.adjustments.model_dump(exclude_unset=True))
        layer.adjustments = Adjustments.model_validate(local)
    return state
