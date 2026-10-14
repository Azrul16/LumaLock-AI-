"""Conservative image-aware plans and clipping guardrails."""

import math

from lumalock.ai.analyzer.scene_analyzer import ImageAnalysis, analyze
from lumalock.ai.prompt.schema import EditPlan
from lumalock.project.edit_state import Adjustments


def auto_plan(analysis: ImageAnalysis) -> EditPlan:
    a = analysis
    exposure = max(-0.45, min(0.7, math.log2(0.45 / max(a.luminance_mean, 0.06)) * 0.5))
    wb = a.white_balance
    return EditPlan(
        global_adjustments=Adjustments(
            exposure=exposure,
            highlights=-min(0.4, a.white_clipping * 4 + 0.08),
            shadows=0.12 if a.luminance_mean < 0.4 else 0.04,
            contrast=0.08 if a.contrast < 0.2 else 0,
            temperature=max(-0.12, min(0.12, (wb[2] - wb[0]) * 0.15)),
            vibrance=0.08 if a.saturation < 0.5 else 0,
            sharpening=0.12,
            denoise=min(0.25, a.noise * 5),
        ),
        confidence=0.8,
        explanation="Conservative exposure, highlight, color and detail correction.",
    )


def guard_auto(source, result, state, renderer):
    before, after = analyze(source), analyze(result)
    if (
        after.white_clipping > before.white_clipping + 0.025
        or after.black_clipping > before.black_clipping + 0.04
    ):
        reduced = state.model_copy(deep=True)
        reduced.adjustments = Adjustments(
            **{k: v * 0.5 for k, v in state.adjustments.model_dump().items()}
        )
        return renderer(source, reduced), reduced
    return result, state
