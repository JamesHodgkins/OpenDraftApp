"""Rectangle entity — rotated rectangle without polyline conversion."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional, Tuple

from app.entities.base import (
    BaseEntity, BBox, Vec2,
    _geo_pt_seg_dist, _geo_seg_intersects_rect,
)


@dataclass
class RectangleEntity(BaseEntity):
    """A rectangle defined by center, size, and rotation (radians).

    This keeps rectangles as true rectangles when rotated (instead of being
    "baked" into a polyline).
    """

    _entity_kind: ClassVar[str] = "rect"
    type: str = field(default="rect", init=False, repr=False)
    center: Vec2 = field(default_factory=Vec2)
    width: float = 0.0
    height: float = 0.0
    rotation: float = 0.0  # radians, CCW

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    @classmethod
    def from_corners(
        cls,
        p1: Vec2,
        p2: Vec2,
        *,
        rotation: float = 0.0,
        **kwargs: Any,
    ) -> "RectangleEntity":
        """Construct a rectangle from two opposite corners (axis-aligned before rotation)."""
        x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
        mnx, mny = min(x1, x2), min(y1, y2)
        mxx, mxy = max(x1, x2), max(y1, y2)
        c = Vec2((mnx + mxx) / 2.0, (mny + mxy) / 2.0)
        return cls(center=c, width=(mxx - mnx), height=(mxy - mny), rotation=rotation, **kwargs)

    def _cos_sin(self) -> Tuple[float, float]:
        return math.cos(self.rotation), math.sin(self.rotation)

    def _world_from_local(self, v: Vec2) -> Vec2:
        """Map local (rect-frame) point to world."""
        cos_a, sin_a = self._cos_sin()
        return Vec2(
            self.center.x + v.x * cos_a - v.y * sin_a,
            self.center.y + v.x * sin_a + v.y * cos_a,
        )

    def _local_from_world(self, v: Vec2) -> Vec2:
        """Map world point to local (rect-frame) point."""
        cos_a, sin_a = self._cos_sin()
        dx = v.x - self.center.x
        dy = v.y - self.center.y
        # inverse rotation (transpose)
        return Vec2(dx * cos_a + dy * sin_a, -dx * sin_a + dy * cos_a)

    def _local_corners(self) -> List[Vec2]:
        hx = self.width / 2.0
        hy = self.height / 2.0
        # 0=BL,1=BR,2=TR,3=TL
        return [Vec2(-hx, -hy), Vec2(hx, -hy), Vec2(hx, hy), Vec2(-hx, hy)]

    def _corners(self) -> List[Vec2]:
        return [self._world_from_local(c) for c in self._local_corners()]

    def _edges(self):
        c = self._corners()
        return list(zip(c, c[1:] + [c[0]]))

    def bounding_box(self) -> Optional[BBox]:
        if self.width <= 0.0 or self.height <= 0.0:
            return None
        corners = self._corners()
        xs = [p.x for p in corners]
        ys = [p.y for p in corners]
        return BBox(min(xs), min(ys), max(xs), max(ys))

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        return any(_geo_pt_seg_dist(pt, a, b) <= tolerance for a, b in self._edges())

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        corners = self._corners()
        eid = self.id
        if SnapType.ENDPOINT in enabled:
            for c in corners:
                results.append(SnapResult(Vec2(c.x, c.y), SnapType.ENDPOINT, eid))
        if SnapType.MIDPOINT in enabled:
            for a, b in zip(corners, corners[1:] + [corners[0]]):
                results.append(SnapResult(
                    Vec2((a.x + b.x) / 2, (a.y + b.y) / 2),
                    SnapType.MIDPOINT, eid,
                ))
        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        from app.entities.snap_types import SnapType, SnapResult
        best = None
        for p1, p2 in self._edges():
            dx, dy = p2.x - p1.x, p2.y - p1.y
            len_sq = dx * dx + dy * dy
            if len_sq < 1e-20:
                continue
            t = max(0.0, min(1.0,
                ((cursor.x - p1.x) * dx + (cursor.y - p1.y) * dy) / len_sq))
            pt = Vec2(p1.x + t * dx, p1.y + t * dy)
            from app.entities.base import _geo_dist
            d = _geo_dist(pt, cursor)
            if best is None or d < best[0]:
                best = (d, pt)
        if best is None:
            return None
        return SnapResult(best[1], SnapType.NEAREST, self.id)

    def perp_snaps(self, from_pt: Vec2) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        for p1, p2 in self._edges():
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
        if self.width <= 0.0 or self.height <= 0.0:
            return
        from PySide6.QtCore import QPointF
        corners = self._corners()
        pts = [world_to_screen(QPointF(p.x, p.y)) for p in corners]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            painter.drawLine(a, b)

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        bb = self.bounding_box()
        if bb is None:
            return False
        sel = BBox(rmin.x, rmin.y, rmax.x, rmax.y)
        if not sel.intersects(bb):
            return False

        # Fully inside selection window if all corners are inside.
        corners = self._corners()
        if all(rmin.x <= p.x <= rmax.x and rmin.y <= p.y <= rmax.y for p in corners):
            return True

        # Edge intersects selection rect.
        for a, b in self._edges():
            if _geo_seg_intersects_rect(a, b, rmin, rmax):
                return True

        # Selection rect corner inside rotated rect (selection fully inside entity).
        if self.width > 0.0 and self.height > 0.0:
            hx = self.width / 2.0
            hy = self.height / 2.0
            for p in (Vec2(rmin.x, rmin.y), Vec2(rmax.x, rmin.y), Vec2(rmax.x, rmax.y), Vec2(rmin.x, rmax.y)):
                q = self._local_from_world(p)
                if abs(q.x) <= hx and abs(q.y) <= hy:
                    return True
        return False

    # ------------------------------------------------------------------
    # Grip editing
    # ------------------------------------------------------------------

    def grip_points(self):
        from app.entities.base import GripPoint, GripType
        corners = self._corners()
        edges = self._edges()
        grips = []
        # 4 corner grips (index 0-3)
        for i, c in enumerate(corners):
            grips.append(GripPoint(c, self.id, i, GripType.ENDPOINT))
        # 4 edge midpoint grips (index 4-7)
        for j, (a, b) in enumerate(edges):
            mid = Vec2((a.x + b.x) / 2, (a.y + b.y) / 2)
            grips.append(GripPoint(mid, self.id, 4 + j, GripType.MIDPOINT))
        return grips

    def move_grip(self, index: int, new_pos: Vec2) -> None:
        if self.width <= 0.0 or self.height <= 0.0:
            # Degenerate; treat as moved center.
            self.center = new_pos
            return

        if index < 4:
            # Corner grip: update width/height/center in local frame, keep rotation fixed.
            local_new = self._local_from_world(new_pos)
            local_corners = self._local_corners()
            opp = (index + 2) % 4
            local_opp = local_corners[opp]
            local_center_offset = (local_new + local_opp) / 2.0
            dx = abs(local_new.x - local_opp.x)
            dy = abs(local_new.y - local_opp.y)
            self.width = max(0.0, dx)
            self.height = max(0.0, dy)
            # Move center by the rotated local offset.
            self.center = self._world_from_local(local_center_offset)
        elif 4 <= index <= 7:
            # Edge midpoint grip — move entire rectangle.
            edges = self._edges()
            j = index - 4
            a, b = edges[j]
            mid = Vec2((a.x + b.x) / 2.0, (a.y + b.y) / 2.0)
            self.center = Vec2(self.center.x + (new_pos.x - mid.x), self.center.y + (new_pos.y - mid.y))

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["center"] = self.center.to_dict()
        d["width"] = self.width
        d["height"] = self.height
        d["rotation"] = self.rotation
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RectangleEntity":
        # Backward compatible: older docs stored p1/p2 only (axis-aligned).
        if "center" in d:
            return cls(
                **cls._base_kwargs(d),
                center=Vec2.from_dict(d["center"]),
                width=float(d.get("width", 0.0)),
                height=float(d.get("height", 0.0)),
                rotation=float(d.get("rotation", 0.0)),
            )
        p1 = Vec2.from_dict(d["p1"])
        p2 = Vec2.from_dict(d["p2"])
        return cls.from_corners(p1, p2, rotation=float(d.get("rotation", 0.0)), **cls._base_kwargs(d))
