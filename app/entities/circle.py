"""Circle entity — defined by a centre point and radius."""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional

from app.entities.base import BaseEntity, BBox, Vec2, _geo_dist


@dataclass
class CircleEntity(BaseEntity):
    """A full circle with a given centre and radius."""

    _entity_kind: ClassVar[str] = "circle"
    type: str = field(default="circle", init=False, repr=False)
    center: Vec2 = field(default_factory=Vec2)
    radius: float = 1.0

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        r = self.radius
        return BBox(
            self.center.x - r, self.center.y - r,
            self.center.x + r, self.center.y + r,
        )

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        return abs(_geo_dist(pt, self.center) - self.radius) <= tolerance

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        cx, cy, r, eid = self.center.x, self.center.y, self.radius, self.id
        if SnapType.CENTER in enabled:
            results.append(SnapResult(Vec2(cx, cy), SnapType.CENTER, eid))
        if SnapType.QUADRANT in enabled:
            for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r)):
                results.append(SnapResult(Vec2(cx + dx, cy + dy), SnapType.QUADRANT, eid))
        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        from app.entities.snap_types import SnapType, SnapResult
        dx = cursor.x - self.center.x
        dy = cursor.y - self.center.y
        d = math.hypot(dx, dy)
        if d < 1e-12:
            return None
        return SnapResult(
            Vec2(self.center.x + dx / d * self.radius,
                 self.center.y + dy / d * self.radius),
            SnapType.NEAREST, self.id,
        )

    def perp_snaps(self, from_pt: Vec2) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        dx = from_pt.x - self.center.x
        dy = from_pt.y - self.center.y
        d = math.hypot(dx, dy)
        if d < 1e-12:
            return []
        return [SnapResult(
            Vec2(self.center.x + dx / d * self.radius,
                 self.center.y + dy / d * self.radius),
            SnapType.PERPENDICULAR, self.id,
        )]

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF, QRectF
        sc = world_to_screen(QPointF(self.center.x, self.center.y))
        r_px = self.radius * scale
        painter.drawEllipse(QRectF(sc.x() - r_px, sc.y() - r_px, 2 * r_px, 2 * r_px))

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        # Closest point on rect to circle centre
        cx_clamp = max(rmin.x, min(self.center.x, rmax.x))
        cy_clamp = max(rmin.y, min(self.center.y, rmax.y))
        return math.hypot(cx_clamp - self.center.x, cy_clamp - self.center.y) <= self.radius

    # ------------------------------------------------------------------
    # Grip editing
    # ------------------------------------------------------------------

    def grip_points(self):
        from app.entities.base import GripPoint, GripType
        cx, cy, r = self.center.x, self.center.y, self.radius
        return [
            GripPoint(self.center, self.id, 0, GripType.CENTER),
            GripPoint(Vec2(cx + r, cy), self.id, 1, GripType.QUADRANT),
            GripPoint(Vec2(cx - r, cy), self.id, 2, GripType.QUADRANT),
            GripPoint(Vec2(cx, cy + r), self.id, 3, GripType.QUADRANT),
            GripPoint(Vec2(cx, cy - r), self.id, 4, GripType.QUADRANT),
        ]

    def move_grip(self, index: int, new_pos: Vec2) -> None:
        if index == 0:
            # Move entire circle
            self.center = new_pos
        elif index in (1, 2, 3, 4):
            # Resize: set radius to distance from center to new position
            self.radius = max(1e-6, math.hypot(
                new_pos.x - self.center.x, new_pos.y - self.center.y))

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["center"] = self.center.to_dict()
        d["radius"] = self.radius
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CircleEntity":
        return cls(
            **cls._base_kwargs(d),
            center=Vec2.from_dict(d["center"]),
            radius=float(d["radius"]),
        )
