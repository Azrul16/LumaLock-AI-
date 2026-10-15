"""Deterministic editing requirements; no model calls or translation."""

NATURAL = """Edit this exact photograph naturally and realistically. Preserve important scene
structure, facial geometry, expression, body proportions and clothing. Do not introduce
unrequested objects, artificial skin smoothing or unrelated changes. Keep photographic texture."""

CREATIVE = """Apply the requested creative transformation. Modify the environment, atmosphere,
lighting, sky or specified scene elements only as requested. Preserve important subject details
and recognizable identity. Keep the result photorealistic unless another style is requested."""

IDENTITY = """IDENTITY PRESERVATION REQUIREMENT:
Preserve the exact recognizable identity of protected people. Do not redesign, beautify,
replace or reconstruct their faces. Keep their eyes, eyebrows, nose, mouth, jaw, facial
proportions, expression and recognizable skin features consistent with the original."""
