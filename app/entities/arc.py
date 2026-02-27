"""Arc entity — a circular arc defined by centre, radius and angle range."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict

from app.entities.base import BaseEntity, Vec2


@dataclass
class ArcEntity(BaseEntity):
    """A circular arc.

    Angles are stored in **radians**.  ``ccw=True`` means the arc sweeps
    counter-clockwise from ``startAngle`` to ``endAngle``.
    """

    type: str = field(default="arc", init=False, repr=False)
    center: Vec2 = field(default_factory=Vec2)
    radius: float = 1.0
    start_angle: float = 0.0   # radians
    end_angle: float = 1.5707963267948966   # π/2 radians
    ccw: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["center"] = self.center.to_dict()
        d["radius"] = self.radius
        d["startAngle"] = self.start_angle
        d["endAngle"] = self.end_angle
        d["ccw"] = self.ccw
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArcEntity":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            layer=d.get("layer", "default"),
            center=Vec2.from_dict(d["center"]),
            radius=float(d["radius"]),
            start_angle=float(d["startAngle"]),
            end_angle=float(d["endAngle"]),
            ccw=bool(d.get("ccw", True)),
        )
