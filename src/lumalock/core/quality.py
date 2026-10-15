"""Quality controls set real inference work; no artificial processing delays."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CreativeQuality:
    resolution: int
    steps: int


def creative_quality(settings, retry_scale=1):
    mode = settings.quality_mode
    resolution = {"Preview": 512, "Quality": 1024, "Maximum": settings.creative_resolution}[mode]
    return CreativeQuality(
        max(256 if retry_scale < 1 else 512, int(resolution * retry_scale) // 64 * 64),
        {"Preview": 20, "Quality": 40, "Maximum": 60}[mode],
    )
