"""The shared, validated state used by manual controls and prompt edits."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ADJUSTMENTS = (
    "exposure",
    "brightness",
    "contrast",
    "highlights",
    "shadows",
    "whites",
    "blacks",
    "temperature",
    "tint",
    "vibrance",
    "saturation",
    "clarity",
    "texture",
    "dehaze",
    "sharpening",
    "denoise",
    "vignette",
    "grain",
)
HSL_COLORS = ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")


class Adjustments(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    exposure: float = Field(0, ge=-3, le=3)
    brightness: float = Field(0, ge=-1, le=1)
    contrast: float = Field(0, ge=-1, le=1)
    highlights: float = Field(0, ge=-1, le=1)
    shadows: float = Field(0, ge=-1, le=1)
    whites: float = Field(0, ge=-1, le=1)
    blacks: float = Field(0, ge=-1, le=1)
    temperature: float = Field(0, ge=-1, le=1)
    tint: float = Field(0, ge=-1, le=1)
    vibrance: float = Field(0, ge=-1, le=1)
    saturation: float = Field(0, ge=-1, le=1)
    clarity: float = Field(0, ge=-1, le=1)
    texture: float = Field(0, ge=-1, le=1)
    dehaze: float = Field(0, ge=-1, le=1)
    sharpening: float = Field(0, ge=0, le=1)
    denoise: float = Field(0, ge=0, le=1)
    vignette: float = Field(0, ge=-1, le=1)
    grain: float = Field(0, ge=0, le=1)


class MaskLayer(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    id: str
    name: str
    kind: Literal[
        "subject",
        "background",
        "face",
        "sky",
        "brush",
        "gradient",
        "radial",
        "rectangle",
        "ellipse",
    ]
    adjustments: Adjustments = Field(default_factory=Adjustments)
    enabled: bool = True
    inverted: bool = False
    opacity: float = Field(1, ge=0, le=1)
    feather: float = Field(0, ge=0, le=100)
    # Normalized geometry survives preview and original-resolution rendering.
    strokes: list[list[float]] = Field(default_factory=list)
    geometry: list[float] = Field(default_factory=lambda: [0.5, 0.5, 0.3, 0.3])
    mask_file: str | None = None
    protected: bool = False

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, value):
        if len(value) != 4 or any(not math.isfinite(x) or not 0 <= x <= 1 for x in value):
            raise ValueError("Mask geometry needs four normalized coordinates")
        return value

    @field_validator("strokes")
    @classmethod
    def validate_strokes(cls, value):
        for stroke in value:
            if len(stroke) != 4 or any(not math.isfinite(x) for x in stroke):
                raise ValueError("Invalid brush stroke")
            x, y, radius, erase = stroke
            if not 0 <= x <= 1 or not 0 <= y <= 1 or not 0 < radius <= 1 or erase not in (0, 1):
                raise ValueError("Invalid brush stroke coordinates")
        return value


class Geometry(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    crop: list[float] | None = None
    quarter_turns: int = Field(0, ge=0, le=3)
    straighten: float = Field(0, ge=-45, le=45)
    flip_horizontal: bool = False
    flip_vertical: bool = False

    @field_validator("crop")
    @classmethod
    def validate_crop(cls, value):
        if value is not None:
            if len(value) != 4 or any(not math.isfinite(v) for v in value):
                raise ValueError("Crop requires four finite coordinates")
            x, y, width, height = value
            if (
                x < 0
                or y < 0
                or width <= 0
                or height <= 0
                or x + width > 1.000001
                or y + height > 1.000001
            ):
                raise ValueError("Crop must stay inside the image")
        return value


class EditState(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    adjustments: Adjustments = Field(default_factory=Adjustments)
    masks: list[MaskLayer] = Field(default_factory=list)
    identity_lock: bool = True
    mode: Literal["Preserve", "Creative", "Manual Pro"] = "Preserve"
    hsl: dict[str, list[float]] = Field(default_factory=dict)
    curves: dict[str, list[list[float]]] = Field(default_factory=dict)
    generated_file: str | None = None
    geometry: Geometry = Field(default_factory=Geometry)

    @field_validator("hsl")
    @classmethod
    def validate_hsl(cls, value):
        for name, values in value.items():
            if name not in HSL_COLORS or len(values) != 3 or any(not -1 <= x <= 1 for x in values):
                raise ValueError("Invalid HSL control")
        return value

    @field_validator("curves")
    @classmethod
    def validate_curves(cls, value):
        for channel, points in value.items():
            if channel not in ("master", "red", "green", "blue") or len(points) < 2:
                raise ValueError("Invalid curve channel or points")
            if any(len(p) != 2 or any(not 0 <= v <= 1 for v in p) for p in points):
                raise ValueError("Curve points must be normalized")
            if (
                points[0][0] != 0
                or points[-1][0] != 1
                or any(a[0] >= b[0] for a, b in zip(points, points[1:]))
            ):
                raise ValueError("Curve input points must increase from 0 to 1")
        return value
