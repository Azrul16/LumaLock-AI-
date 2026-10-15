"""User-authored protection geometry in normalized original-image coordinates."""

from typing import Annotated, Literal

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

Coordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class ProtectionShape(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["brush", "erase", "ellipse", "rectangle"]
    points: list[tuple[Coordinate, Coordinate]] = Field(min_length=1, max_length=2048)
    radius: float = Field(0.035, ge=0.002, le=0.2, allow_inf_nan=False)

    @model_validator(mode="after")
    def shape_endpoints(self):
        if self.tool in ("ellipse", "rectangle") and len(self.points) != 2:
            raise ValueError("Shapes need exactly two corners.")
        return self


def protection_mask(size, shapes):
    width, height = size
    mask = np.zeros((height, width), dtype=np.float32)
    for raw in shapes:
        shape = raw if isinstance(raw, ProtectionShape) else ProtectionShape.model_validate(raw)
        points = [(round(x * (width - 1)), round(y * (height - 1))) for x, y in shape.points]
        radius = max(1, round(shape.radius * min(width, height)))
        if shape.tool in ("brush", "erase"):
            color = 0 if shape.tool == "erase" else 1
            for point in points:
                cv2.circle(mask, point, radius, color, -1)
            for first, second in zip(points, points[1:]):
                cv2.line(mask, first, second, color, 2 * radius)
        else:
            first, second = points
            left, right = sorted((first[0], second[0]))
            top, bottom = sorted((first[1], second[1]))
            if shape.tool == "rectangle":
                cv2.rectangle(mask, (left, top), (right, bottom), 1, -1)
            else:
                cv2.ellipse(
                    mask,
                    ((left + right) // 2, (top + bottom) // 2),
                    (max(1, (right - left) // 2), max(1, (bottom - top) // 2)),
                    0,
                    0,
                    360,
                    1,
                    -1,
                )
    return mask
