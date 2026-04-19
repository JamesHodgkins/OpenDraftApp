"""Spline entity — a smooth curve through an ordered set of control points (Catmull-Rom)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional, Tuple

from app.entities.base import (
    BaseEntity, BBox, Vec2,
    _geo_dist, _geo_pt_seg_dist, _geo_seg_intersects_rect,
)


def _catmull_rom_point(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2, t: float) -> Vec2:
    """Evaluate Catmull-Rom spline segment at parameter t in [0, 1]."""
    t2, t3 = t * t, t * t * t
    x = 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * t +
                (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 +
                (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3)
    y = 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * t +
                (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 +
                (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3)
    return Vec2(x, y)


def _spline_polyline(points: List[Vec2], steps: int = 20) -> List[Vec2]:
    """Tessellate the Catmull-Rom spline into a polyline for rendering/hit-testing."""
    n = len(points)
    if n < 2:
        return list(points)
    if n == 2:
        return [points[0], points[1]]
    result: List[Vec2] = []
    # Phantom endpoints: duplicate first and last
    pts = [points[0]] + list(points) + [points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(steps):
            result.append(_catmull_rom_point(p0, p1, p2, p3, s / steps))
    result.append(pts[-2])
    return result


@dataclass
class SplineEntity(BaseEntity):
    """A smooth Catmull-Rom spline through a sequence of control points."""

    _entity_kind: ClassVar[str] = "spline"
    type: str = field(default="spline", init=False, repr=False)
    points: List[Vec2] = field(default_factory=list)

    def _tessellated(self) -> List[Vec2]:
        return _spline_polyline(self.points)

    def _segments(self) -> List[Tuple[Vec2, Vec2]]:
        pts = self._tessellated()
        return list(zip(pts, pts[1:]))

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        pts = self._tessellated()
        if not pts:
            return None
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return BBox(min(xs), min(ys), max(xs), max(ys))

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        return any(_geo_pt_seg_dist(pt, a, b) <= tolerance for a, b in self._segments())

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        if not self.points:
            return results
        eid = self.id
        if SnapType.ENDPOINT in enabled:
            results.append(SnapResult(Vec2(self.points[0].x, self.points[0].y), SnapType.ENDPOINT, eid))
            if len(self.points) > 1:
                results.append(SnapResult(Vec2(self.points[-1].x, self.points[-1].y), SnapType.ENDPOINT, eid))
        # Midpoint snap only on the overall curve (midpoint of the tessellated arc), not each micro-segment
        if SnapType.MIDPOINT in enabled and len(self.points) >= 2:
            tess = self._tessellated()
            if tess:
                mid = tess[len(tess) // 2]
                results.append(SnapResult(Vec2(mid.x, mid.y), SnapType.MIDPOINT, eid))
        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        from app.entities.snap_types import SnapType, SnapResult
        best_d = float("inf")
        best_pt: Optional[Vec2] = None
        for p1, p2 in self._segments():
            dx, dy = p2.x - p1.x, p2.y - p1.y
            len_sq = dx * dx + dy * dy
            if len_sq < 1e-20:
                continue
            t = max(0.0, min(1.0, ((cursor.x - p1.x) * dx + (cursor.y - p1.y) * dy) / len_sq))
            pt = Vec2(p1.x + t * dx, p1.y + t * dy)
            d = _geo_dist(pt, cursor)
            if d < best_d:
                best_d, best_pt = d, pt
        if best_pt is None:
            return None
        return SnapResult(best_pt, SnapType.NEAREST, self.id)

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
            results.append(SnapResult(Vec2(p1.x + t * dx, p1.y + t * dy), SnapType.PERPENDICULAR, self.id))
        return results

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPainterPath
        pts = [world_to_screen(QPointF(p.x, p.y)) for p in self._tessellated()]
        if len(pts) < 2:
            return
        path = QPainterPath(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        painter.drawPath(path)

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
    # Grip editing
    # ------------------------------------------------------------------

    def grip_points(self):
        from app.entities.base import GripPoint, GripType
        grips = []
        for i, p in enumerate(self.points):
            grip_type = GripType.ENDPOINT if (i == 0 or i == len(self.points) - 1) else GripType.CONTROL
            grips.append(GripPoint(p, self.id, i, grip_type))
        return grips

    def move_grip(self, index: int, new_pos: Vec2) -> None:
        if 0 <= index < len(self.points):
            self.points[index] = new_pos

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["points"] = [p.to_dict() for p in self.points]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SplineEntity":
        return cls(
            **cls._base_kwargs(d),
            points=[Vec2.from_dict(p) for p in d.get("points", [])],
        )
