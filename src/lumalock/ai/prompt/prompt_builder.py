"""Ordinary Python prompt construction. User language is preserved verbatim."""

from lumalock.ai.prompt.presets import preset_prompt
from lumalock.ai.prompt.schema import EditPlan, GenerativeOptions
from lumalock.ai.prompt.templates import CREATIVE, IDENTITY, NATURAL
from lumalock.core.exceptions import UserError


def auto_enhance_prompt(analysis):
    changes = [
        "Professionally enhance this exact photograph; keep the people, scene and composition."
    ]
    if analysis.luminance_mean < 0.3:
        changes.append("Improve underexposure and lift available shadow detail naturally.")
    elif analysis.luminance_mean > 0.7:
        changes.append("Reduce excessive brightness while preserving natural tones.")
    if analysis.black_clipping > 0.02:
        changes.append("Balance deep shadows without inventing texture in clipped areas.")
    if analysis.white_clipping > 0.01:
        changes.append("Soften bright highlights and retain available highlight detail.")
    if analysis.contrast < 0.15:
        changes.append("Increase realistic contrast slightly.")
    if analysis.saturation < 0.25:
        changes.append("Improve color richness without oversaturation.")
    if max(analysis.white_balance) - min(analysis.white_balance) > 0.25:
        changes.append("Balance the color cast while retaining natural skin tones.")
    if analysis.noise > 0.02:
        changes.append("Reduce visible noise subtly while preserving photographic texture.")
    if analysis.blur_score < 50:
        changes.append("Improve perceived clarity subtly; do not invent subject detail.")
    return " ".join(changes)


def build_flux_prompt(
    user_prompt,
    mode="Natural",
    identity_lock=True,
    preserve_composition=True,
    protected_regions=False,
    preset=None,
    analysis=None,
):
    if mode not in ("Natural", "Creative"):
        raise UserError("Choose Natural or Creative mode.")
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        raise UserError("Tell LumaLock what you want to change.")
    if len(user_prompt) > 12000:
        raise UserError("Keep the prompt within 12,000 characters.")
    parts = [
        "USER REQUEST:\n" + user_prompt.strip(),
        "EDITING REQUIREMENTS:\n" + (NATURAL if mode == "Natural" else CREATIVE),
    ]
    if preserve_composition:
        parts.append(
            "Keep the overall composition unless the user's specific request requires a change."
        )
    if identity_lock:
        parts.append(IDENTITY)
    if protected_regions:
        parts.append(
            "Do not modify the protected areas. Original protected pixels will be restored after editing."
        )
    if preset:
        parts.append(preset_prompt(preset, mode))
    if analysis is not None and (
        preset == "Professional Enhance"
        or user_prompt.strip().lower() in ("auto enhance", "professional enhance")
    ):
        parts.append(auto_enhance_prompt(analysis))
    parts.append("Produce a professionally edited photograph. Avoid unrelated changes.")
    return "\n\n".join(parts)


def build_edit_plan(prompt, analysis, state, mode="Natural", preset=None, protected_regions=False):
    return EditPlan(
        intent="content_change" if mode == "Creative" else "correction",
        preserve_identity=state.identity_lock,
        preserve_composition=True,
        generative=GenerativeOptions(
            enabled=True,
            prompt=build_flux_prompt(
                prompt,
                mode,
                state.identity_lock,
                True,
                protected_regions or bool(state.masks),
                preset,
                analysis,
            ),
            strength=0.4 if mode == "Natural" else 0.65,
        ),
        explanation="Deterministic prompt requirements; no separate prompt model or translation.",
    )
