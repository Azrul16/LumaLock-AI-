"""Validated editing-director output; no executable model instructions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lumalock.project.edit_state import Adjustments


class EditingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["natural", "creative"]
    user_request: str
    flux_prompt: str = Field(min_length=10, max_length=5000)
    strength: float = Field(0.45, ge=0, le=1)
    preserve_identity: bool = True
    preserve_composition: bool = True
    allow_environment_changes: bool = False
    allow_object_addition: bool = False
    allow_object_removal: bool = False
    explicit_changes: list[str] = Field(default_factory=list, max_length=20)
    prohibited_changes: list[str] = Field(default_factory=list, max_length=20)
    manual_adjustments: dict[str, float] = Field(default_factory=dict)

    @field_validator("manual_adjustments")
    @classmethod
    def validate_adjustments(cls, value):
        Adjustments.model_validate(value)
        return value
