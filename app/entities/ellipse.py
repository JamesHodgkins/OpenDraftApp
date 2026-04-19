"""Ellipse / elliptical-arc entity.

A full ellipse has start_param=0, end_param=2π.
An elliptical arc has start_param and end_param in [0, 2π), always traversed CCW
in the local frame (matching DXF ELLIPSE entity convention).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional

from app.entities.base import BaseEntity, BBox, Vec2, _geo_dist

_TWO_PI = 2 * math.pi


@dataclass
class EllipseEntity(BaseEntity):
    """An ellipse or elliptical arc.

    Parameters follow the DXF ELLIPSE entity convention:
    - ``start_param`` / ``end_param`` are parametric angles in the *local* frame,
      traversed CCW; 0 → right end of major axis.
    - A full ellipse has start_param=0.0, end_param=2π.
    """

    _entity_kind: ClassVar[str] = "ellipse"
    type: str = field(default="ellipse", init=False, repr=False)
    center: Vec2 = field(default_factory=Vec2)
    radius_x: float = 1.0       # semi-major axis (local X)
    radius_y: float = 0.5       # semi-minor axis (local Y)
    rotation: float = 0.0       # rotation of major axis from world X, radians
    start_param: float = 0.0    # parametric start angle, CCW in local frame
    end_param: float = _TWO_PI  # parametric end angle

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def is_full(self) -> bool:
        return abs(self.end_param - self.start_param - _TWO_PI) < 1e-9

    def _param_span(self) -> float:
        span = (self.end_param - self.start_param) % _TWO_PI
        return span if span > 1e-9 else _TWO_PI

    def _param_on_arc(self, param: float) -> bool:
        """True if parametric angle *param* lies within the arc span."""
        if self.is_full:
            return True
        span = self._param_span()
        p = (param - self.start_param) % _TWO_PI
        return p <= span + 1e-9

    def _world_to_local(self, pt: Vec2) -> Vec2:
        dx = pt.x - self.center.x
        dy = pt.y - self.center.y
        cos_r, sin_r = math.cos(-self.rotation), math.sin(-self.rotation)
        return Vec2(dx * cos_r - dy * sin_r, dx * sin_r + dy * cos_r)

    def _local_to_world(self, lx: float, ly: float) -> Vec2:
        cos_r, sin_r = math.cos(self.rotation), math.sin(self.rotation)
        return Vec2(
            self.center.x + lx * cos_r - ly * sin_r,
            self.center.y + lx * sin_r + ly * cos_r,
        )

    def point_at_param(self, param: float) -> Vec2:
        """World point on ellipse perimeter at parametric angle *param*."""
        return self._local_to_world(
            self.radius_x * math.cos(param),
            self.radius_y * math.sin(param),
        )

    def _nearest_param(self, loc: Vec2) -> float:
        """Parametric angle of the ellipse point closest to local-frame point *loc*."""
        angle = math.atan2(loc.y * self.radius_x, loc.x * self.radius_y)
        for _ in range(8):
            px = self.radius_x * math.cos(angle)
            py = self.radius_y * math.sin(angle)
            dx, dy = loc.x - px, loc.y - py
            dpx = -self.radius_x * math.sin(angle)
            dpy = self.radius_y * math.cos(angle)
            num = dx * dpx + dy * dpy
            d2px = -self.radius_x * math.cos(angle)
            d2py = -self.radius_y * math.sin(angle)
            denom = dpx * dpx + dpy * dpy + dx * d2px + dy * d2py
            if abs(denom) < 1e-12:
                break
            angle -= num / denom
        return angle % _TWO_PI

    def _distance_to_perimeter(self, pt: Vec2) -> float:
        loc = self._world_to_local(pt)
        best_param = self._nearest_param(loc)
        if not self._param_on_arc(best_param):
            # Check both endpoints
            d1 = _geo_dist(pt, self.point_at_param(self.start_param))
            d2 = _geo_dist(pt, self.point_at_param(self.end_param))
            return min(d1, d2)
        px = self.radius_x * math.cos(best_param)
        py = self.radius_y * math.sin(best_param)
        return math.hypot(loc.x - px, loc.y - py)

    def _tessellated(self, steps: int = 64) -> List[Vec2]:
        span = self._param_span()
        n = max(4, int(steps * span / _TWO_PI))
        return [self.point_at_param(self.start_param + span * i / n) for i in range(n + 1)]

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
        return self._distance_to_perimeter(pt) <= tolerance

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        eid = self.id
        if SnapType.CENTER in enabled and self.is_full:
            results.append(SnapResult(Vec2(self.center.x, self.center.y), SnapType.CENTER, eid))
        if SnapType.ENDPOINT in enabled and not self.is_full:
            results.append(SnapResult(self.point_at_param(self.start_param), SnapType.ENDPOINT, eid))
            results.append(SnapResult(self.point_at_param(self.end_param), SnapType.ENDPOINT, eid))
        if SnapType.QUADRANT in enabled:
            for param in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
                if self._param_on_arc(param):
                    results.append(SnapResult(self.point_at_param(param), SnapType.QUADRANT, eid))
        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        from app.entities.snap_types import SnapType, SnapResult
        loc = self._world_to_local(cursor)
        param = self._nearest_param(loc)
        if not self._param_on_arc(param):
            d1 = _geo_dist(cursor, self.point_at_param(self.start_param))
            d2 = _geo_dist(cursor, self.point_at_param(self.end_param))
            pt = self.point_at_param(self.start_param if d1 < d2 else self.end_param)
        else:
            pt = self.point_at_param(param)
        return SnapResult(pt, SnapType.NEAREST, self.id)

    def perp_snaps(self, from_pt: Vec2) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        loc = self._world_to_local(from_pt)
        param = self._nearest_param(loc)
        if not self._param_on_arc(param):
            return []
        return [SnapResult(self.point_at_param(param), SnapType.PERPENDICULAR, self.id)]

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPainterPath
        pts = [world_to_screen(QPointF(p.x, p.y)) for p in self._tessellated()]
        if len(pts) < 2:
            return
        path = QPainterPath(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        if self.is_full:
            path.closeSubpath()
        painter.drawPath(path)

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        from app.entities.base import _geo_seg_intersects_rect
        bb = self.bounding_box()
        if bb is None:
            return False
        sel = BBox(rmin.x, rmin.y, rmax.x, rmax.y)
        if not sel.intersects(bb):
            return False
        if sel.contains(bb):
            return True
        pts = self._tessellated()
        for a, b in zip(pts, pts[1:]):
            if _geo_seg_intersects_rect(a, b, rmin, rmax):
                return True
        return False

    # ------------------------------------------------------------------
    # Grip editing
    # ------------------------------------------------------------------

    def grip_points(self):
        from app.entities.base import GripPoint, GripType
        grips = [GripPoint(self.center, self.id, 0, GripType.CENTER)]
        # Major/minor axis grips for full ellipse
        grips.append(GripPoint(self.point_at_param(0.0), self.id, 1, GripType.QUADRANT))
        grips.append(GripPoint(self.point_at_param(math.pi / 2), self.id, 2, GripType.QUADRANT))
        if not self.is_full:
            grips.append(GripPoint(self.point_at_param(self.start_param), self.id, 3, GripType.ENDPOINT))
            grips.append(GripPoint(self.point_at_param(self.end_param), self.id, 4, GripType.ENDPOINT))
        return grips

    def move_grip(self, index: int, new_pos: Vec2) -> None:
        if index == 0:
            self.center = new_pos
        elif index == 1:
            dx = new_pos.x - self.center.x
            dy = new_pos.y - self.center.y
            self.rotation = math.atan2(dy, dx)
            self.radius_x = max(1e-6, math.hypot(dx, dy))
        elif index == 2:
            loc = self._world_to_local(new_pos)
            self.radius_y = max(1e-6, math.hypot(loc.x, loc.y))
        elif index == 3:
            loc = self._world_to_local(new_pos)
            self.start_param = math.atan2(loc.y / max(self.radius_y, 1e-6),
                                          loc.x / max(self.radius_x, 1e-6)) % _TWO_PI
        elif index == 4:
            loc = self._world_to_local(new_pos)
            self.end_param = math.atan2(loc.y / max(self.radius_y, 1e-6),
                                        loc.x / max(self.radius_x, 1e-6)) % _TWO_PI

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["center"] = self.center.to_dict()
        d["radiusX"] = self.radius_x
        d["radiusY"] = self.radius_y
        d["rotation"] = self.rotation
        d["startParam"] = self.start_param
        d["endParam"] = self.end_param
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EllipseEntity":
        return cls(
            **cls._base_kwargs(d),
            center=Vec2.from_dict(d["center"]),
            radius_x=float(d.get("radiusX", 1.0)),
            radius_y=float(d.get("radiusY", 0.5)),
            rotation=float(d.get("rotation", 0.0)),
            start_param=float(d.get("startParam", 0.0)),
            end_param=float(d.get("endParam", _TWO_PI)),
        )
