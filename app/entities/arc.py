"""Arc entity — a circular arc defined by centre, radius and angle range."""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional

from app.entities.base import (
    BaseEntity, BBox, Vec2,
    _geo_dist, _geo_angle_on_arc, _geo_seg_intersects_rect,
)


def _arc_span(start: float, end: float, ccw: bool) -> float:
    TWO_PI = 2 * math.pi
    if ccw:
        span = (end - start) % TWO_PI
        if span == 0:
            span = TWO_PI
    else:
        span = -((start - end) % TWO_PI)
        if span == 0:
            span = -TWO_PI
    return span


@dataclass
class ArcEntity(BaseEntity):
    """A circular arc.

    Angles are stored in **radians**.  ``ccw=True`` means the arc sweeps
    counter-clockwise from ``startAngle`` to ``endAngle``.
    """

    _entity_kind: ClassVar[str] = "arc"
    type: str = field(default="arc", init=False, repr=False)
    center: Vec2 = field(default_factory=Vec2)
    radius: float = 1.0
    start_angle: float = 0.0
    end_angle: float = 1.5707963267948966   # π/2
    ccw: bool = True

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        # Conservative: full circle AABB (accurate enough for culling/selection)
        r = self.radius
        return BBox(
            self.center.x - r, self.center.y - r,
            self.center.x + r, self.center.y + r,
        )

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        d = _geo_dist(pt, self.center)
        if abs(d - self.radius) > tolerance:
            return False
        angle = math.atan2(pt.y - self.center.y, pt.x - self.center.x)
        return _geo_angle_on_arc(angle, self.start_angle, self.end_angle, self.ccw)

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        cx, cy, r = self.center.x, self.center.y, self.radius
        sa, ea, ccw, eid = self.start_angle, self.end_angle, self.ccw, self.id

        if SnapType.CENTER in enabled:
            results.append(SnapResult(Vec2(cx, cy), SnapType.CENTER, eid))

        if SnapType.ENDPOINT in enabled:
            results.append(SnapResult(
                Vec2(cx + r * math.cos(sa), cy + r * math.sin(sa)),
                SnapType.ENDPOINT, eid,
            ))
            results.append(SnapResult(
                Vec2(cx + r * math.cos(ea), cy + r * math.sin(ea)),
                SnapType.ENDPOINT, eid,
            ))

        if SnapType.MIDPOINT in enabled:
            span = _arc_span(sa, ea, ccw)
            mid = sa + span / 2
            results.append(SnapResult(
                Vec2(cx + r * math.cos(mid), cy + r * math.sin(mid)),
                SnapType.MIDPOINT, eid,
            ))

        if SnapType.QUADRANT in enabled:
            for angle in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
                if _geo_angle_on_arc(angle, sa, ea, ccw):
                    results.append(SnapResult(
                        Vec2(cx + r * math.cos(angle), cy + r * math.sin(angle)),
                        SnapType.QUADRANT, eid,
                    ))

        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        from app.entities.snap_types import SnapType, SnapResult
        cx, cy, r = self.center.x, self.center.y, self.radius
        dx = cursor.x - cx; dy = cursor.y - cy
        if math.hypot(dx, dy) < 1e-12:
            return None
        angle = math.atan2(dy, dx)
        if _geo_angle_on_arc(angle, self.start_angle, self.end_angle, self.ccw):
            return SnapResult(
                Vec2(cx + r * math.cos(angle), cy + r * math.sin(angle)),
                SnapType.NEAREST, self.id,
            )
        ep1 = Vec2(cx + r * math.cos(self.start_angle), cy + r * math.sin(self.start_angle))
        ep2 = Vec2(cx + r * math.cos(self.end_angle),   cy + r * math.sin(self.end_angle))
        return SnapResult(
            ep1 if _geo_dist(ep1, cursor) <= _geo_dist(ep2, cursor) else ep2,
            SnapType.NEAREST, self.id,
        )

    def perp_snaps(self, from_pt: Vec2) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        dx = from_pt.x - self.center.x
        dy = from_pt.y - self.center.y
        d = math.hypot(dx, dy)
        if d < 1e-12:
            return []
        angle = math.atan2(dy, dx)
        if not _geo_angle_on_arc(angle, self.start_angle, self.end_angle, self.ccw):
            return []
        return [SnapResult(
            Vec2(self.center.x + self.radius * math.cos(angle),
                 self.center.y + self.radius * math.sin(angle)),
            SnapType.PERPENDICULAR, self.id,
        )]

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF, QRectF
        sc = world_to_screen(QPointF(self.center.x, self.center.y))
        r_px = self.radius * scale
        rect = QRectF(sc.x() - r_px, sc.y() - r_px, 2 * r_px, 2 * r_px)
        start_deg = self.start_angle * 180.0 / math.pi
        end_deg   = self.end_angle   * 180.0 / math.pi
        span = (end_deg - start_deg) % 360.0 if self.ccw else -((start_deg - end_deg) % 360.0)
        painter.drawArc(rect, int(start_deg * 16), int(span * 16))

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        bb = self.bounding_box()
        if bb is None:
            return False
        sel = __import__('app.entities.base', fromlist=['BBox']).BBox(
            rmin.x, rmin.y, rmax.x, rmax.y)
        if not sel.intersects(bb):
            return False
        if sel.contains(bb):
            return True
        # Sample arc segments and test each one
        n = max(16, int(abs(self.end_angle - self.start_angle) / (math.pi / 16)))
        span = _arc_span(self.start_angle, self.end_angle, self.ccw)
        points = [
            Vec2(self.center.x + self.radius * math.cos(self.start_angle + i / n * span),
                 self.center.y + self.radius * math.sin(self.start_angle + i / n * span))
            for i in range(n + 1)
        ]
        for i in range(len(points) - 1):
            if _geo_seg_intersects_rect(points[i], points[i + 1], rmin, rmax):
                return True
        return False

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

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
            **cls._base_kwargs(d),
            center=Vec2.from_dict(d["center"]),
            radius=float(d["radius"]),
            start_angle=float(d["startAngle"]),
            end_angle=float(d["endAngle"]),
            ccw=bool(d.get("ccw", True)),
        )
