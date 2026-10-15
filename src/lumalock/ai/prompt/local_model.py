"""Offline CPU GGUF Qwen director; closes its mmap before FLUX starts."""

import json
import os

from lumalock.ai.prompt.director_schema import EditingRequest
from lumalock.ai.prompt.parser import parse_prompt
from lumalock.ai.prompt.schema import EditPlan, GenerativeOptions
from lumalock.core.exceptions import Cancelled, UserError
from lumalock.core.model_manager import MODEL_SPECS
from lumalock.project.edit_state import EditState

IDENTITY_INSTRUCTION = (
    "Preserve the exact identity of every person. Keep the same facial structure, eyes, eyebrows, "
    "nose, mouth, jaw, expression, skin features, hair, clothing and body. Do not beautify, reconstruct "
    "or redesign faces. Keep realistic skin tones and natural photographic texture."
)


def direct(prompt, analysis, models, cancelled, progress):
    if not models.available("prompt"):
        raise UserError("Install Qwen Editing Director in Models & settings before AI generation.")
    from llama_cpp import Llama

    grammar_schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["natural", "creative"]},
            "user_request": {"type": "string"},
            "flux_prompt": {"type": "string"},
            "strength": {"type": "number"},
        },
        "required": ["mode", "user_request", "flux_prompt", "strength"],
        "additionalProperties": False,
    }

    progress(-1, "Qwen is preparing the edit plan locally on CPU…")
    if cancelled():
        raise Cancelled("Prompt planning cancelled.")
    messages = [
        {
            "role": "system",
            "content": "You are LumaLock's professional photographic editing director. Return a JSON editing request. "
            "Natural edits improve lighting/color and preserve people/content/composition. "
            "Afternoon, golden hour and cinematic grading are natural unless additions are explicitly requested. "
            "Adding visible sunlight/rays/clouds or removing objects/persons is creative. "
            "Never invent unrequested additions/removals. You receive statistics, not image pixels. "
            "Write a precise FLUX reference-image editing instruction. Always preserve identity. "
            + IDENTITY_INSTRUCTION,
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": prompt,
                    "required_output_example": {
                        "mode": "natural",
                        "user_request": prompt,
                        "flux_prompt": "Professionally enhance the supplied photograph while preserving all people and composition.",
                        "strength": 0.45,
                        "preserve_identity": True,
                        "preserve_composition": True,
                        "allow_environment_changes": False,
                        "allow_object_addition": False,
                        "allow_object_removal": False,
                        "explicit_changes": [],
                        "prohibited_changes": ["redesign faces"],
                        "manual_adjustments": {},
                    },
                    "image_statistics": {
                        k: v for k, v in analysis.to_dict().items() if k != "histogram"
                    },
                }
            ),
        },
    ]
    with models.session(
        "prompt",
        lambda path: Llama(
            model_path=str(path / MODEL_SPECS["prompt"]["file"]),
            n_ctx=4096,
            n_batch=128,
            n_threads=min(6, os.cpu_count() or 2),
            n_gpu_layers=0,
            use_mmap=True,
            verbose=False,
            chat_format="chatml",
        ),
    ) as model:
        output = model.create_chat_completion(
            messages=messages,
            temperature=0,
            max_tokens=1100,
            response_format={"type": "json_object", "schema": grammar_schema},
            stream=True,
        )
        parts = []
        try:
            for chunk in output:
                if cancelled():
                    raise Cancelled("Prompt planning cancelled.")
                parts.append(chunk["choices"][0].get("delta", {}).get("content", ""))
        finally:
            output.close()
        try:
            request = EditingRequest.model_validate_json("".join(parts))
        except ValueError as exc:
            raise UserError(
                "Qwen returned an invalid edit plan; nothing was applied. Try a clearer request."
            ) from exc
    request.preserve_identity = True
    # Known content-changing verbs remain authoritative over a small LLM's classification.
    routed = parse_prompt(prompt, analysis, EditState())
    if routed.generative.enabled:
        request.mode = "creative"
    elif routed.confidence >= 0.4:
        request.mode = "natural"
    text = prompt.lower()
    request.allow_environment_changes = request.mode == "creative"
    request.allow_object_addition = request.mode == "creative" and any(
        word in text for word in ("add ", "insert ")
    )
    request.allow_object_removal = request.mode == "creative" and any(
        word in text for word in ("remove ", "erase ")
    )
    request.explicit_changes = [prompt]
    request.prohibited_changes = ["alter facial identity", "unrequested additions or removals"]
    if request.mode == "natural":
        request.preserve_composition = True
        request.allow_object_addition = False
        request.allow_object_removal = False
        request.flux_prompt += (
            " Preserve the existing scene and composition. Add/remove no objects."
        )
    request.flux_prompt += " " + IDENTITY_INSTRUCTION
    return request


def interpret(prompt, analysis, state, models, cancelled, progress):
    if not models.available("prompt"):
        plan = parse_prompt(prompt, analysis, state)
        plan.explanation = "Rule-based preview (Qwen is not installed). " + plan.explanation
        return plan
    request = direct(prompt, analysis, models, cancelled, progress)
    return EditPlan(
        intent="content_change" if request.mode == "creative" else "correction",
        preserve_identity=True,
        preserve_composition=request.preserve_composition,
        generative=GenerativeOptions(
            enabled=True, prompt=request.flux_prompt, strength=request.strength
        ),
        explanation=f"Planned {request.mode} edit: {', '.join(request.explicit_changes) or request.user_request}. "
        "Review the plan, then Generate. Identity Lock remains active.",
    )
