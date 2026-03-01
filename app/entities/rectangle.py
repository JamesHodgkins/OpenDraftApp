"""Rectangle entity — defined by two opposite corner points."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional

from app.entities.base import (
    BaseEntity, BBox, Vec2,
    _geo_pt_seg_dist, _geo_seg_intersects_rect,
)


@dataclass
class RectangleEntity(BaseEntity):
    """An axis-aligned rectangle defined by two opposite corners."""

    _entity_kind: ClassVar[str] = "rect"
    type: str = field(default="rect", init=False, repr=False)
    p1: Vec2 = field(default_factory=Vec2)
    p2: Vec2 = field(default_factory=Vec2)

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def _corners(self):
        x1, y1, x2, y2 = self.p1.x, self.p1.y, self.p2.x, self.p2.y
        return [
            Vec2(min(x1, x2), min(y1, y2)), Vec2(max(x1, x2), min(y1, y2)),
            Vec2(max(x1, x2), max(y1, y2)), Vec2(min(x1, x2), max(y1, y2)),
        ]

    def _edges(self):
        c = self._corners()
        return list(zip(c, c[1:] + [c[0]]))

    def bounding_box(self) -> Optional[BBox]:
        return BBox(
            min(self.p1.x, self.p2.x), min(self.p1.y, self.p2.y),
            max(self.p1.x, self.p2.x), max(self.p1.y, self.p2.y),
        )

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
        from PySide6.QtCore import QPointF
        s1 = world_to_screen(QPointF(self.p1.x, self.p1.y))
        s2 = world_to_screen(QPointF(self.p2.x, self.p2.y))
        left = min(s1.x(), s2.x())
        top  = min(s1.y(), s2.y())
        w = abs(s2.x() - s1.x())
        h = abs(s2.y() - s1.y())
        painter.drawRect(int(left), int(top), int(w), int(h))

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        bb = self.bounding_box()
        if bb is None:
            return False
        sel = BBox(rmin.x, rmin.y, rmax.x, rmax.y)
        if not sel.intersects(bb):
            return False
        if sel.contains(bb):
            return True
        for a, b in self._edges():
            if _geo_seg_intersects_rect(a, b, rmin, rmax):
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
        if index < 4:
            # Corner grip — remap corner index to p1/p2 adjustment.
            # corners: 0=BL, 1=BR, 2=TR, 3=TL  (from _corners)
            x1, y1, x2, y2 = self.p1.x, self.p1.y, self.p2.x, self.p2.y
            mn_x, mn_y = min(x1, x2), min(y1, y2)
            mx_x, mx_y = max(x1, x2), max(y1, y2)
            nx, ny = new_pos.x, new_pos.y
            if index == 0:    # bottom-left
                self.p1 = Vec2(nx, ny); self.p2 = Vec2(mx_x, mx_y)
            elif index == 1:  # bottom-right
                self.p1 = Vec2(mn_x, ny); self.p2 = Vec2(nx, mx_y)
            elif index == 2:  # top-right
                self.p1 = Vec2(mn_x, mn_y); self.p2 = Vec2(nx, ny)
            elif index == 3:  # top-left
                self.p1 = Vec2(nx, mx_y); self.p2 = Vec2(mx_x, ny)
        elif 4 <= index <= 7:
            # Edge midpoint grip — move entire rectangle.
            corners = self._corners()
            edges = self._edges()
            j = index - 4
            a, b = edges[j]
            mid = Vec2((a.x + b.x) / 2, (a.y + b.y) / 2)
            dx = new_pos.x - mid.x
            dy = new_pos.y - mid.y
            self.p1 = Vec2(self.p1.x + dx, self.p1.y + dy)
            self.p2 = Vec2(self.p2.x + dx, self.p2.y + dy)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["p1"] = self.p1.to_dict()
        d["p2"] = self.p2.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RectangleEntity":
        return cls(
            **cls._base_kwargs(d),
            p1=Vec2.from_dict(d["p1"]),
            p2=Vec2.from_dict(d["p2"]),
        )
