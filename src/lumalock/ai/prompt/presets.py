"""Built-in photographic text presets, not additional AI models."""

PRESETS = {
    "Professional Enhance": "Balance exposure, dynamic range, highlights, shadows, color and realistic contrast. Keep natural skin tones; avoid excessive HDR, oversaturation or artificial smoothing.",
    "Natural Portrait": "Create a natural professional portrait finish. Keep realistic skin texture, facial features and believable skin tones. Balance light without changing expression or clothing.",
    "Warm Cinematic": "Apply subtle warm cinematic color and controlled contrast while retaining photographic texture and natural skin tones.",
    "Cool Cinematic": "Apply subtle cool cinematic colors, balanced contrast and realistic skin tones.",
    "Golden Hour": "Create believable golden-hour directional lighting, warm highlights and physically plausible shadows. Do not introduce a visible sun unless requested.",
    "Late Afternoon": "Create believable warm late-afternoon directional light, softer highlights and realistic shadows. Preserve the existing environment and subject.",
    "Sunset": "Create realistic sunset lighting and warm atmospheric colors with consistent light across the scene.",
    "Moody": "Create a restrained moody photographic grade with rich shadows and preserved important detail.",
    "Travel": "Enhance this travel photograph with balanced light, believable atmospheric depth and realistic vivid colors.",
    "Studio Portrait": "Create a polished studio portrait lighting look. Preserve the person's identity, pose, clothing and natural skin texture.",
    "Dramatic Sky": "Enhance existing sky depth, cloud definition where present, highlight detail and natural color richness. Do not replace the sky or invent new clouds in Natural mode.",
    "Clean Social Media": "Produce a clean photographic finish with balanced exposure, natural color, restrained clarity and realistic skin texture. Preserve composition and people.",
}


def preset_prompt(name, mode="Natural"):
    if name not in PRESETS:
        raise ValueError("Choose a built-in photographic preset.")
    if name == "Dramatic Sky" and mode == "Creative":
        return "Create a dramatic photorealistic sky, modifying realistic cloud formations if needed. Match lighting across sky, environment and subject. Preserve the subject and facial identity."
    return PRESETS[name]
