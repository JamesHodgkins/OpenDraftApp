"""Polyline entity — an ordered sequence of vertices (optionally closed)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.entities.base import BaseEntity, Vec2


@dataclass
class PolylineEntity(BaseEntity):
    """An open or closed polyline defined by an ordered list of vertices.

    When ``closed`` is ``True`` the last vertex is implicitly connected
    back to the first.
    """

    type: str = field(default="polyline", init=False, repr=False)
    points: List[Vec2] = field(default_factory=list)
    closed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["points"] = [p.to_dict() for p in self.points]
        d["closed"] = self.closed
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PolylineEntity":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            layer=d.get("layer", "default"),
            points=[Vec2.from_dict(p) for p in d.get("points", [])],
            closed=bool(d.get("closed", False)),
        )
