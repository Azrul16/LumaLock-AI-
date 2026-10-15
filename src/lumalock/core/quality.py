"""Quality controls set real inference work; no artificial processing delays."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CreativeQuality:
    resolution: int
    steps: int


def creative_quality(settings):
    mode = settings.quality_mode
    resolution = {"Preview": 512, "Quality": 1024, "Maximum": settings.creative_resolution}[mode]
    return CreativeQuality(
        max(512, int(resolution) // 64 * 64),
        {"Preview": 12, "Quality": 40, "Maximum": 50}[mode],
    )
