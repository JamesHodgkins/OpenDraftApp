"""Rectangle entity — defined by two opposite corner points."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict

from app.entities.base import BaseEntity, Vec2


@dataclass
class RectangleEntity(BaseEntity):
    """An axis-aligned rectangle defined by two opposite corners.

    ``p1`` is conventionally the top-left / first-clicked corner;
    ``p2`` the bottom-right / second-clicked corner — but no ordering
    is enforced so consumers should handle either arrangement.
    """

    type: str = field(default="rect", init=False, repr=False)
    p1: Vec2 = field(default_factory=Vec2)
    p2: Vec2 = field(default_factory=Vec2)

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["p1"] = self.p1.to_dict()
        d["p2"] = self.p2.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RectangleEntity":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            layer=d.get("layer", "default"),
            p1=Vec2.from_dict(d["p1"]),
            p2=Vec2.from_dict(d["p2"]),
        )
