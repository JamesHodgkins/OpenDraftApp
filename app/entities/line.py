"""Line entity — defined by two endpoints."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict

from app.entities.base import BaseEntity, Vec2


@dataclass
class LineEntity(BaseEntity):
    """A straight line segment between two world-space points."""

    type: str = field(default="line", init=False, repr=False)
    p1: Vec2 = field(default_factory=Vec2)
    p2: Vec2 = field(default_factory=Vec2)

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["p1"] = self.p1.to_dict()
        d["p2"] = self.p2.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LineEntity":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            layer=d.get("layer", "default"),
            p1=Vec2.from_dict(d["p1"]),
            p2=Vec2.from_dict(d["p2"]),
        )
