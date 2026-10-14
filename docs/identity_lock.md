# Identity Lock

No neural recognition/segmentation models are used. OpenCV frontal-face/eye cascades provide
approximate boxes; manual brush, rectangle and ellipse protection remains available.
Inspect overlays because classical detection can miss faces or include false candidates.

AI prompt instructions preserve identity, composition, skin texture, hair and clothing.
Generation excludes all protected pixels, composites only allowed regions, recovers exact
original protected pixels and verifies equality before saving. Strong scene relighting can
still mismatch the original protected region; inspect before export.

Photographic controls transform existing pixels without facial geometry synthesis.
Check face against original provides conventional structural comparison, not identity
probability or neural recognition. No embeddings or face crops are stored in logs.
