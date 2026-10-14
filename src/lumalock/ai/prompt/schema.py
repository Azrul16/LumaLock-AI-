"""Untrusted model output must pass this schema before entering the edit state."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lumalock.project.edit_state import Adjustments


class RegionAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    region: Literal["subject", "face", "sky", "background", "custom"]
    adjustments: Adjustments = Field(default_factory=Adjustments)


class RestorationOptions(BaseModel):
    enabled: bool = False
    strength: float = Field(0.35, ge=0, le=1)


class GenerativeOptions(BaseModel):
    enabled: bool = False
    prompt: str = ""
    strength: float = Field(0.4, ge=0, le=1)


class EditPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["correction", "style", "regional", "restoration", "content_change"] = (
        "correction"
    )
    preserve_identity: bool = True
    preserve_composition: bool = True
    global_adjustments: Adjustments = Field(default_factory=Adjustments)
    regions: list[RegionAdjustment] = Field(default_factory=list)
    restoration: RestorationOptions = Field(default_factory=RestorationOptions)
    generative: GenerativeOptions = Field(default_factory=GenerativeOptions)
    confidence: float = Field(0.7, ge=0, le=1)
    explanation: str = ""
