"""Polyline entity — an ordered sequence of vertices (optionally closed)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional

from app.entities.base import (
    BaseEntity, BBox, Vec2,
    _geo_dist, _geo_pt_seg_dist, _geo_seg_intersects_rect,
)


@dataclass
class PolylineEntity(BaseEntity):
    """An open or closed polyline defined by an ordered list of vertices."""

    _entity_kind: ClassVar[str] = "polyline"
    type: str = field(default="polyline", init=False, repr=False)
    points: List[Vec2] = field(default_factory=list)
    closed: bool = False

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def _segments(self):
        pts = self.points
        segs = list(zip(pts, pts[1:]))
        if self.closed and len(pts) > 1:
            segs.append((pts[-1], pts[0]))
        return segs

    def bounding_box(self) -> Optional[BBox]:
        if not self.points:
            return None
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return BBox(min(xs), min(ys), max(xs), max(ys))

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        return any(_geo_pt_seg_dist(pt, a, b) <= tolerance for a, b in self._segments())

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        pts, eid = self.points, self.id
        if not pts:
            return results

        if SnapType.ENDPOINT in enabled:
            for i, p in enumerate(pts):
                is_end = i == 0 or i == len(pts) - 1
                if is_end or not self.closed:
                    results.append(SnapResult(Vec2(p.x, p.y), SnapType.ENDPOINT, eid))

        if SnapType.MIDPOINT in enabled:
            for a, b in self._segments():
                results.append(SnapResult(
                    Vec2((a.x + b.x) / 2, (a.y + b.y) / 2),
                    SnapType.MIDPOINT, eid,
                ))

        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        from app.entities.snap_types import SnapType, SnapResult
        best = None
        for p1, p2 in self._segments():
            dx, dy = p2.x - p1.x, p2.y - p1.y
            len_sq = dx * dx + dy * dy
            if len_sq < 1e-20:
                continue
            t = max(0.0, min(1.0,
                ((cursor.x - p1.x) * dx + (cursor.y - p1.y) * dy) / len_sq))
            pt = Vec2(p1.x + t * dx, p1.y + t * dy)
            d = _geo_dist(pt, cursor)
            if best is None or d < best[0]:
                best = (d, pt)
        if best is None:
            return None
        return SnapResult(best[1], SnapType.NEAREST, self.id)

    def perp_snaps(self, from_pt: Vec2) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        for p1, p2 in self._segments():
            dx, dy = p2.x - p1.x, p2.y - p1.y
            len_sq = dx * dx + dy * dy
            if len_sq < 1e-20:
                continue
            t = ((from_pt.x - p1.x) * dx + (from_pt.y - p1.y) * dy) / len_sq
            if not (0.0 <= t <= 1.0):
                continue
            results.append(SnapResult(
                Vec2(p1.x + t * dx, p1.y + t * dy),
                SnapType.PERPENDICULAR, self.id,
            ))
        return results

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF
        pts = [world_to_screen(QPointF(p.x, p.y)) for p in self.points]
        if len(pts) < 2:
            return
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i].x(), pts[i].y(), pts[i + 1].x(), pts[i + 1].y())
        if self.closed:
            painter.drawLine(pts[-1].x(), pts[-1].y(), pts[0].x(), pts[0].y())

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        bb = self.bounding_box()
        if bb is None:
            return False
        sel = BBox(rmin.x, rmin.y, rmax.x, rmax.y)
        if not sel.intersects(bb):
            return False
        if sel.contains(bb):
            return True
        for a, b in self._segments():
            if _geo_seg_intersects_rect(a, b, rmin, rmax):
                return True
        return False

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

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
