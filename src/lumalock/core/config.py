"""Validated settings and portable writable storage."""

import logging
import os
import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


def resource_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    return root / name


class Settings(BaseModel):
    preview_size: int = Field(1400, ge=256, le=4096)
    tile_size: int = Field(384, ge=128, le=1024)
    identity_lock: bool = True
    face_expansion: float = Field(0.25, ge=0, le=1)
    export_quality: int = Field(95, ge=1, le=100)
    preserve_metadata: bool = True
    prompt_logging: bool = False
    autosave: bool = True
    device: str = Field("auto", pattern="^(auto|cpu|cuda)$")
    use_fp16: bool = True
    generative_backend: str = Field("flux", pattern="^flux$")
    flux_license_accepted: bool = False
    first_run_done: bool = False
    ai_setup_requested: list[Literal["flux"]] = Field(default_factory=list)
    quality_mode: str = Field("Quality", pattern="^(Preview|Quality|Maximum)$")
    pipeline_version: int = 3
    allow_slow_models: bool = True
    creative_resolution: int = Field(1536, ge=1024, le=2048)


def data_dir() -> Path:
    portable = resource_path("data")
    path = Path(os.getenv("LUMALOCK_DATA_DIR", str(portable)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def model_dir() -> Path:
    portable = resource_path("models")
    path = Path(os.getenv("LUMALOCK_MODEL_DIR", str(portable)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_settings(path: Path | None = None) -> Settings:
    path = path or data_dir() / "settings.yaml"
    if not path.exists():
        path = resource_path("config/app.yaml")
    if not path.exists():
        return Settings()
    try:
        values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(values, dict):
            raise ValueError("Settings must be a mapping")
        if values.get("pipeline_version", 1) < 3:
            values["quality_mode"] = "Quality"
            values["creative_resolution"] = max(1536, values.get("creative_resolution", 1536))
            values["pipeline_version"] = 3
        # Retire the former execution watchdog, including persisted 1800-second values.
        values.pop("edit_budget_seconds", None)
        requested = values.get("ai_setup_requested", [])
        values["ai_setup_requested"] = (
            [key for key in requested if key == "flux"] if isinstance(requested, list) else []
        )
        return Settings.model_validate(values)
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        logging.getLogger("lumalock.config").warning("Invalid settings; using safe defaults")
        return Settings()


def save_settings(settings: Settings) -> None:
    path = data_dir() / "settings.yaml"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(yaml.safe_dump(settings.model_dump()), encoding="utf-8")
    temporary.replace(path)
