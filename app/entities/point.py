"""Point entity — a single node/marker at a world coordinate."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional

from app.entities.base import BaseEntity, BBox, Vec2, _geo_dist

_MARKER_WORLD = 2.0  # visual cross arm length in world units (for bbox/hit)


@dataclass
class PointEntity(BaseEntity):
    """A single point marker rendered as a small cross."""

    _entity_kind: ClassVar[str] = "point"
    type: str = field(default="point", init=False, repr=False)
    position: Vec2 = field(default_factory=Vec2)

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        r = _MARKER_WORLD
        return BBox(
            self.position.x - r, self.position.y - r,
            self.position.x + r, self.position.y + r,
        )

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        return _geo_dist(pt, self.position) <= tolerance

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        if SnapType.ENDPOINT in enabled:
            results.append(SnapResult(Vec2(self.position.x, self.position.y), SnapType.ENDPOINT, self.id))
        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        from app.entities.snap_types import SnapType, SnapResult
        return SnapResult(Vec2(self.position.x, self.position.y), SnapType.NEAREST, self.id)

    def perp_snaps(self, from_pt: Vec2) -> List:
        return []

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF
        sc = world_to_screen(QPointF(self.position.x, self.position.y))
        arm = max(4.0, 6.0)  # fixed pixel arm length for visibility
        sx, sy = sc.x(), sc.y()
        painter.drawLine(int(sx - arm), int(sy), int(sx + arm), int(sy))
        painter.drawLine(int(sx), int(sy - arm), int(sx), int(sy + arm))

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        return (rmin.x <= self.position.x <= rmax.x and
                rmin.y <= self.position.y <= rmax.y)

    # ------------------------------------------------------------------
    # Grip editing
    # ------------------------------------------------------------------

    def grip_points(self):
        from app.entities.base import GripPoint, GripType
        return [GripPoint(self.position, self.id, 0, GripType.CENTER)]

    def move_grip(self, index: int, new_pos: Vec2) -> None:
        if index == 0:
            self.position = new_pos

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["position"] = self.position.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PointEntity":
        return cls(
            **cls._base_kwargs(d),
            position=Vec2.from_dict(d["position"]),
        )
