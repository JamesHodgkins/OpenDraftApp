"""Circle entity — defined by a centre point and radius."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict

from app.entities.base import BaseEntity, Vec2


@dataclass
class CircleEntity(BaseEntity):
    """A full circle with a given centre and radius."""

    type: str = field(default="circle", init=False, repr=False)
    center: Vec2 = field(default_factory=Vec2)
    radius: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["center"] = self.center.to_dict()
        d["radius"] = self.radius
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CircleEntity":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            layer=d.get("layer", "default"),
            center=Vec2.from_dict(d["center"]),
            radius=float(d["radius"]),
        )
