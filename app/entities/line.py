"""Line entity — defined by two endpoints."""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional

from app.entities.base import (
    BaseEntity, BBox, Vec2,
    _geo_dist, _geo_pt_seg_dist, _geo_seg_intersects_rect,
)


@dataclass
class LineEntity(BaseEntity):
    """A straight line segment between two world-space points."""

    _entity_kind: ClassVar[str] = "line"
    type: str = field(default="line", init=False, repr=False)
    p1: Vec2 = field(default_factory=Vec2)
    p2: Vec2 = field(default_factory=Vec2)

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        return BBox(
            min(self.p1.x, self.p2.x), min(self.p1.y, self.p2.y),
            max(self.p1.x, self.p2.x), max(self.p1.y, self.p2.y),
        )

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        return _geo_pt_seg_dist(pt, self.p1, self.p2) <= tolerance

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        p1, p2, eid = self.p1, self.p2, self.id
        if SnapType.ENDPOINT in enabled:
            results.append(SnapResult(Vec2(p1.x, p1.y), SnapType.ENDPOINT, eid))
            results.append(SnapResult(Vec2(p2.x, p2.y), SnapType.ENDPOINT, eid))
        if SnapType.MIDPOINT in enabled:
            results.append(SnapResult(
                Vec2((p1.x + p2.x) / 2, (p1.y + p2.y) / 2),
                SnapType.MIDPOINT, eid,
            ))
        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        from app.entities.snap_types import SnapType, SnapResult
        p1, p2 = self.p1, self.p2
        dx, dy = p2.x - p1.x, p2.y - p1.y
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-20:
            return SnapResult(Vec2(p1.x, p1.y), SnapType.NEAREST, self.id)
        t = max(0.0, min(1.0,
            ((cursor.x - p1.x) * dx + (cursor.y - p1.y) * dy) / len_sq))
        return SnapResult(
            Vec2(p1.x + t * dx, p1.y + t * dy), SnapType.NEAREST, self.id)

    def perp_snaps(self, from_pt: Vec2) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        p1, p2 = self.p1, self.p2
        dx, dy = p2.x - p1.x, p2.y - p1.y
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-20:
            return []
        t = ((from_pt.x - p1.x) * dx + (from_pt.y - p1.y) * dy) / len_sq
        if not (0.0 <= t <= 1.0):
            return []
        return [SnapResult(
            Vec2(p1.x + t * dx, p1.y + t * dy),
            SnapType.PERPENDICULAR, self.id,
        )]

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF
        s1 = world_to_screen(QPointF(self.p1.x, self.p1.y))
        s2 = world_to_screen(QPointF(self.p2.x, self.p2.y))
        painter.drawLine(s1.x(), s1.y(), s2.x(), s2.y())

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        return _geo_seg_intersects_rect(self.p1, self.p2, rmin, rmax)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["p1"] = self.p1.to_dict()
        d["p2"] = self.p2.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LineEntity":
        return cls(
            **cls._base_kwargs(d),
            p1=Vec2.from_dict(d["p1"]),
            p2=Vec2.from_dict(d["p2"]),
        )
