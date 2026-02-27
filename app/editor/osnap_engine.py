"""
OSNAP (Object Snap) engine for OpenDraft.

Computes snap candidates from existing drawing entities and returns the
nearest candidate within a configurable pixel-radius aperture.

Supported snap modes
--------------------
ENDPOINT      — endpoints of lines, arcs, polyline vertices, rectangle corners.
MIDPOINT      — midpoint of each segment (line, polyline edge, rect edge, arc).
CENTER        — centre point of circles and arcs.
QUADRANT      — 0°, 90°, 180°, 270° points of circles / arcs (where on arc).
NEAREST       — closest point on any entity geometry to the cursor.
INTERSECTION  — intersection between two segments.
PERPENDICULAR — point on entity where a line from *from_point* would be
                 perpendicular to the entity.  Requires a ``from_point`` to be
                 set on the engine (Editor.snap_from_point).

Usage
-----
The engine is instantiated once and attached to the :class:`~app.canvas.CADCanvas`.
On every ``mouseMoveEvent`` the canvas calls :meth:`OsnapEngine.snap` with
the current world-space cursor position and the list of document entities.
The returned :class:`SnapResult` (or ``None``) is cached and:

* Used to override the raw click point in ``mousePressEvent``.
* Drawn as a visual marker in ``paintEvent``.
* Used to update the coordinate display so it reflects the snapped position.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional, Tuple

from app.entities import BaseEntity, Vec2


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class SnapType(Enum):
    ENDPOINT      = "Endpoint"
    MIDPOINT      = "Midpoint"
    CENTER        = "Center"
    QUADRANT      = "Quadrant"
    NEAREST       = "Nearest"
    INTERSECTION  = "Intersection"
    PERPENDICULAR = "Perpendicular"


@dataclass
class SnapResult:
    """A resolved snap candidate ready for display and use."""
    point:     Vec2
    snap_type: SnapType
    entity_id: str = ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class OsnapEngine:
    """Compute OSNAP candidates for a given cursor position.

    Parameters
    ----------
    radius_px:
        Snap aperture in *screen pixels*.  Only candidates whose projected
        screen distance from the cursor is within this radius are returned.
    enabled:
        Collection of :class:`SnapType` values to test.  Pass ``None`` to use
        the default set (all types except NEAREST).
    """

    _DEFAULT_ENABLED = frozenset({
        SnapType.ENDPOINT,
        SnapType.MIDPOINT,
        SnapType.CENTER,
        SnapType.QUADRANT,
        SnapType.INTERSECTION,
        SnapType.PERPENDICULAR,
        SnapType.NEAREST,
    })

    # Priority order — lower number wins when candidates are equidistant.
    _PRIORITY = {
        SnapType.INTERSECTION:  0,
        SnapType.ENDPOINT:      1,
        SnapType.CENTER:        2,
        SnapType.MIDPOINT:      3,
        SnapType.QUADRANT:      4,
        SnapType.PERPENDICULAR: 5,
        SnapType.NEAREST:       6,
    }

    def __init__(
        self,
        radius_px: float = 12.0,
        enabled: Optional[Iterable[SnapType]] = None,
    ) -> None:
        self.radius_px: float = radius_px
        self.enabled: set[SnapType] = (
            set(enabled) if enabled is not None else set(self._DEFAULT_ENABLED)
        )

    # ------------------------------------------------------------------
    # Public API

    def snap(
        self,
        cursor: Vec2,
        entities: Iterable[BaseEntity],
        scale: float,
        from_point: Optional[Vec2] = None,
    ) -> Optional[SnapResult]:
        """Return the best snap candidate near *cursor*, or ``None``.

        Parameters
        ----------
        cursor:
            Current mouse position in world space.
        entities:
            All document entities to test.
        scale:
            Viewport scale (pixels per world unit) used to convert the
            pixel aperture to a world-space tolerance.
        from_point:
            The previously selected point (e.g. start of a line being drawn).
            Required for PERPENDICULAR snapping; ignored otherwise.
        """
        if scale <= 0:
            return None

        entity_list = list(entities)
        tol = self.radius_px / scale        # world-space snap radius

        candidates: List[Tuple[float, SnapResult]] = []

        # Cursor-independent snaps (endpoint, midpoint, center, quadrant)
        for e in entity_list:
            for result in self._candidates_for(e):
                dist = _dist(result.point, cursor)
                if dist <= tol:
                    candidates.append((dist, result))

        # Intersection snaps (pairwise)
        if SnapType.INTERSECTION in self.enabled:
            for i, a in enumerate(entity_list):
                for b in entity_list[i + 1:]:
                    for pt in self._intersections(a, b):
                        dist = _dist(pt, cursor)
                        if dist <= tol:
                            candidates.append((
                                dist,
                                SnapResult(pt, SnapType.INTERSECTION, a.id),
                            ))

        # PERPENDICULAR — foot of perpendicular from from_point onto entity
        if SnapType.PERPENDICULAR in self.enabled and from_point is not None:
            for e in entity_list:
                for result in self._perp_on_entity(e, from_point):
                    dist = _dist(result.point, cursor)
                    if dist <= tol:
                        candidates.append((dist, result))

        # NEAREST is a true fallback — only considered when nothing else snapped.
        if not candidates and SnapType.NEAREST in self.enabled:
            for e in entity_list:
                result = self._nearest_on_entity(e, cursor)
                if result is not None:
                    dist = _dist(result.point, cursor)
                    if dist <= tol:
                        candidates.append((dist, result))

        if not candidates:
            return None

        candidates.sort(key=lambda t: (self._PRIORITY.get(t[1].snap_type, 9), t[0]))
        return candidates[0][1]

    # ------------------------------------------------------------------
    # Per-entity candidate generation

    def _candidates_for(self, e: BaseEntity) -> List[SnapResult]:
        t = getattr(e, "type", "")
        dispatch = {
            "line":     self._line_candidates,
            "circle":   self._circle_candidates,
            "arc":      self._arc_candidates,
            "rect":     self._rect_candidates,
            "polyline": self._polyline_candidates,
        }
        fn = dispatch.get(t)
        return fn(e) if fn else []

    # ---- line -------------------------------------------------------

    def _line_candidates(self, e) -> List[SnapResult]:
        results: List[SnapResult] = []
        p1, p2, eid = e.p1, e.p2, e.id

        if SnapType.ENDPOINT in self.enabled:
            results.append(SnapResult(Vec2(p1.x, p1.y), SnapType.ENDPOINT, eid))
            results.append(SnapResult(Vec2(p2.x, p2.y), SnapType.ENDPOINT, eid))

        if SnapType.MIDPOINT in self.enabled:
            results.append(SnapResult(
                Vec2((p1.x + p2.x) / 2, (p1.y + p2.y) / 2),
                SnapType.MIDPOINT, eid,
            ))

        return results

    # ---- circle -----------------------------------------------------

    def _circle_candidates(self, e) -> List[SnapResult]:
        results: List[SnapResult] = []
        cx, cy, r, eid = e.center.x, e.center.y, e.radius, e.id

        if SnapType.CENTER in self.enabled:
            results.append(SnapResult(Vec2(cx, cy), SnapType.CENTER, eid))

        if SnapType.QUADRANT in self.enabled:
            for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r)):
                results.append(SnapResult(Vec2(cx + dx, cy + dy), SnapType.QUADRANT, eid))

        return results

    # ---- arc --------------------------------------------------------

    def _arc_candidates(self, e) -> List[SnapResult]:
        results: List[SnapResult] = []
        cx, cy, r = e.center.x, e.center.y, e.radius
        sa, ea, ccw, eid = e.start_angle, e.end_angle, e.ccw, e.id

        if SnapType.CENTER in self.enabled:
            results.append(SnapResult(Vec2(cx, cy), SnapType.CENTER, eid))

        if SnapType.ENDPOINT in self.enabled:
            results.append(SnapResult(
                Vec2(cx + r * math.cos(sa), cy + r * math.sin(sa)),
                SnapType.ENDPOINT, eid,
            ))
            results.append(SnapResult(
                Vec2(cx + r * math.cos(ea), cy + r * math.sin(ea)),
                SnapType.ENDPOINT, eid,
            ))

        if SnapType.MIDPOINT in self.enabled:
            span = _arc_span(sa, ea, ccw)
            mid = sa + span / 2
            results.append(SnapResult(
                Vec2(cx + r * math.cos(mid), cy + r * math.sin(mid)),
                SnapType.MIDPOINT, eid,
            ))

        if SnapType.QUADRANT in self.enabled:
            for angle in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
                if _angle_on_arc(angle, sa, ea, ccw):
                    results.append(SnapResult(
                        Vec2(cx + r * math.cos(angle), cy + r * math.sin(angle)),
                        SnapType.QUADRANT, eid,
                    ))

        return results

    # ---- rectangle --------------------------------------------------

    def _rect_candidates(self, e) -> List[SnapResult]:
        results: List[SnapResult] = []
        x1, y1 = e.p1.x, e.p1.y
        x2, y2 = e.p2.x, e.p2.y
        eid = e.id

        corners = [Vec2(x1, y1), Vec2(x2, y1), Vec2(x2, y2), Vec2(x1, y2)]

        if SnapType.ENDPOINT in self.enabled:
            for c in corners:
                results.append(SnapResult(Vec2(c.x, c.y), SnapType.ENDPOINT, eid))

        if SnapType.MIDPOINT in self.enabled:
            for a, b in zip(corners, corners[1:] + [corners[0]]):
                results.append(SnapResult(
                    Vec2((a.x + b.x) / 2, (a.y + b.y) / 2),
                    SnapType.MIDPOINT, eid,
                ))

        return results

    # ---- polyline ---------------------------------------------------

    def _polyline_candidates(self, e) -> List[SnapResult]:
        results: List[SnapResult] = []
        pts, eid = e.points, e.id

        if not pts:
            return results

        if SnapType.ENDPOINT in self.enabled:
            # First and last vertices of open polyline; all vertices
            for i, p in enumerate(pts):
                is_end = (i == 0 or i == len(pts) - 1)
                if is_end or not getattr(e, "closed", False):
                    results.append(SnapResult(Vec2(p.x, p.y), SnapType.ENDPOINT, eid))

        if SnapType.MIDPOINT in self.enabled:
            pairs = list(zip(pts, pts[1:]))
            if getattr(e, "closed", False) and len(pts) > 1:
                pairs.append((pts[-1], pts[0]))
            for a, b in pairs:
                results.append(SnapResult(
                    Vec2((a.x + b.x) / 2, (a.y + b.y) / 2),
                    SnapType.MIDPOINT, eid,
                ))

        return results

    # ------------------------------------------------------------------
    # NEAREST — closest point on entity geometry to the cursor

    def _nearest_on_entity(self, e: BaseEntity, cursor: Vec2) -> Optional[SnapResult]:
        """Return the closest point on *e*'s geometry to *cursor*."""
        t = getattr(e, "type", "")
        eid = e.id

        if t == "line":
            return self._nearest_on_seg(e.p1, e.p2, cursor, eid, SnapType.NEAREST)

        if t == "circle":
            return self._nearest_on_circle(e.center, e.radius, cursor, eid)

        if t == "arc":
            return self._nearest_on_arc(
                e.center, e.radius, e.start_angle, e.end_angle, e.ccw, cursor, eid,
            )

        if t == "rect":
            segs = _rect_segments(e)
            return self._nearest_of_segs(segs, cursor, eid, SnapType.NEAREST)

        if t == "polyline":
            segs = _polyline_segments(e)
            return self._nearest_of_segs(segs, cursor, eid, SnapType.NEAREST)

        return None

    def _nearest_on_seg(
        self, p1: Vec2, p2: Vec2, pt: Vec2, eid: str, stype: SnapType,
        clamp: bool = True,
    ) -> Optional[SnapResult]:
        """Foot of perpendicular from *pt* onto the line through p1-p2.

        If *clamp* is True the foot is clamped to [p1, p2] (nearest-on-segment).
        If *clamp* is False the foot is on the infinite line; the caller is
        responsible for any segment-boundary check it needs.
        """
        dx, dy = p2.x - p1.x, p2.y - p1.y
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-20:
            return SnapResult(Vec2(p1.x, p1.y), stype, eid)
        t = ((pt.x - p1.x) * dx + (pt.y - p1.y) * dy) / seg_len_sq
        if clamp:
            t = max(0.0, min(1.0, t))
        return SnapResult(Vec2(p1.x + t * dx, p1.y + t * dy), stype, eid)

    def _nearest_on_circle(
        self, center: Vec2, radius: float, cursor: Vec2, eid: str,
    ) -> Optional[SnapResult]:
        """Closest point on circle circumference to *cursor*."""
        dx, dy = cursor.x - center.x, cursor.y - center.y
        d = math.hypot(dx, dy)
        if d < 1e-12:
            return None  # cursor exactly at centre — no unique nearest
        return SnapResult(
            Vec2(center.x + dx / d * radius, center.y + dy / d * radius),
            SnapType.NEAREST, eid,
        )

    def _nearest_on_arc(
        self,
        center: Vec2, radius: float,
        start: float, end: float, ccw: bool,
        cursor: Vec2, eid: str,
    ) -> Optional[SnapResult]:
        """Closest point on arc sweep to *cursor*."""
        dx, dy = cursor.x - center.x, cursor.y - center.y
        if math.hypot(dx, dy) < 1e-12:
            return None
        angle = math.atan2(dy, dx)
        if _angle_on_arc(angle, start, end, ccw):
            return SnapResult(
                Vec2(center.x + radius * math.cos(angle),
                     center.y + radius * math.sin(angle)),
                SnapType.NEAREST, eid,
            )
        # Cursor outside arc sweep — return closer endpoint
        ep1 = Vec2(center.x + radius * math.cos(start),
                   center.y + radius * math.sin(start))
        ep2 = Vec2(center.x + radius * math.cos(end),
                   center.y + radius * math.sin(end))
        return SnapResult(
            ep1 if _dist(ep1, cursor) <= _dist(ep2, cursor) else ep2,
            SnapType.NEAREST, eid,
        )

    def _nearest_of_segs(
        self,
        segs: List[Tuple[Vec2, Vec2]],
        cursor: Vec2,
        eid: str,
        stype: SnapType,
    ) -> Optional[SnapResult]:
        """Return the closest candidate across a list of segments."""
        best: Optional[Tuple[float, SnapResult]] = None
        for p1, p2 in segs:
            r = self._nearest_on_seg(p1, p2, cursor, eid, stype)
            if r is None:
                continue
            d = _dist(r.point, cursor)
            if best is None or d < best[0]:
                best = (d, r)
        return best[1] if best else None

    # ------------------------------------------------------------------
    # PERPENDICULAR — foot of perpendicular from from_pt onto entity

    def _perp_on_entity(
        self, e: BaseEntity, from_pt: Vec2,
    ) -> List[SnapResult]:
        """Return perpendicular snap candidates on *e* given *from_pt*."""
        t = getattr(e, "type", "")
        eid = e.id
        results: List[SnapResult] = []

        if t == "line":
            # Perpendicular foot on the infinite line through p1-p2 (no clamping).
            r = self._nearest_on_seg(e.p1, e.p2, from_pt, eid,
                                     SnapType.PERPENDICULAR, clamp=False)
            if r:
                results.append(r)

        elif t in ("rect", "polyline"):
            # Restrict to the actual segment bounds for multi-segment entities.
            segs = _rect_segments(e) if t == "rect" else _polyline_segments(e)
            for p1, p2 in segs:
                dx, dy = p2.x - p1.x, p2.y - p1.y
                seg_len_sq = dx * dx + dy * dy
                if seg_len_sq < 1e-20:
                    continue
                param_t = ((from_pt.x - p1.x) * dx + (from_pt.y - p1.y) * dy) / seg_len_sq
                if not (0.0 <= param_t <= 1.0):
                    continue   # foot outside this edge
                results.append(SnapResult(
                    Vec2(p1.x + param_t * dx, p1.y + param_t * dy),
                    SnapType.PERPENDICULAR, eid,
                ))

        elif t == "circle":
            # Perpendicular from from_pt to circle = point along center→from_pt
            dx, dy = from_pt.x - e.center.x, from_pt.y - e.center.y
            d = math.hypot(dx, dy)
            if d > 1e-12:
                results.append(SnapResult(
                    Vec2(e.center.x + dx / d * e.radius,
                         e.center.y + dy / d * e.radius),
                    SnapType.PERPENDICULAR, eid,
                ))

        elif t == "arc":
            # Same as circle, but only if the foot angle is within the arc
            dx, dy = from_pt.x - e.center.x, from_pt.y - e.center.y
            d = math.hypot(dx, dy)
            if d > 1e-12:
                angle = math.atan2(dy, dx)
                if _angle_on_arc(angle, e.start_angle, e.end_angle, e.ccw):
                    results.append(SnapResult(
                        Vec2(e.center.x + e.radius * math.cos(angle),
                             e.center.y + e.radius * math.sin(angle)),
                        SnapType.PERPENDICULAR, eid,
                    ))

        return results

    # ------------------------------------------------------------------
    # Intersection helpers

    def _intersections(self, a: BaseEntity, b: BaseEntity) -> List[Vec2]:
        ta, tb = getattr(a, "type", ""), getattr(b, "type", "")
        if ta == "line" and tb == "line":
            pt = _line_line_intersection(a.p1, a.p2, b.p1, b.p2)
            return [pt] if pt else []
        if ta in ("line", "rect", "polyline") and tb in ("line", "rect", "polyline"):
            # Decompose both into segments and check all pairs
            segs_a = _entity_segments(a)
            segs_b = _entity_segments(b)
            results: List[Vec2] = []
            for (p1, p2) in segs_a:
                for (p3, p4) in segs_b:
                    pt = _line_line_intersection(p1, p2, p3, p4)
                    if pt:
                        results.append(pt)
            return results
        return []


# ---------------------------------------------------------------------------
# Module-level geometry helpers
# ---------------------------------------------------------------------------

def _dist(a: Vec2, b: Vec2) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _arc_span(start: float, end: float, ccw: bool) -> float:
    """Signed angular span of an arc (always positive magnitude)."""
    TWO_PI = 2 * math.pi
    if ccw:
        span = (end - start) % TWO_PI
    else:
        span = -((start - end) % TWO_PI)
    return span


def _angle_on_arc(angle: float, start: float, end: float, ccw: bool) -> bool:
    """Return True if *angle* lies within the arc sweep."""
    TWO_PI = 2 * math.pi
    angle = angle % TWO_PI
    start = start % TWO_PI
    end   = end   % TWO_PI
    if ccw:
        if start <= end:
            return start <= angle <= end
        return angle >= start or angle <= end
    else:
        if start >= end:
            return end <= angle <= start
        return angle <= start or angle >= end


def _line_line_intersection(p1: Vec2, p2: Vec2, p3: Vec2, p4: Vec2) -> Optional[Vec2]:
    """Intersection of segment p1-p2 with p3-p4, or None if outside either."""
    denom = (p1.x - p2.x) * (p3.y - p4.y) - (p1.y - p2.y) * (p3.x - p4.x)
    if abs(denom) < 1e-12:
        return None   # parallel / collinear
    t = ((p1.x - p3.x) * (p3.y - p4.y) - (p1.y - p3.y) * (p3.x - p4.x)) / denom
    u = -((p1.x - p2.x) * (p1.y - p3.y) - (p1.y - p2.y) * (p1.x - p3.x)) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return Vec2(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y))
    return None


def _entity_segments(e: BaseEntity) -> List[Tuple[Vec2, Vec2]]:
    """Decompose an entity into line segments for intersection testing."""
    t = getattr(e, "type", "")
    if t == "line":
        return [(e.p1, e.p2)]
    if t == "rect":
        return _rect_segments(e)
    if t == "polyline":
        return _polyline_segments(e)
    return []


def _rect_segments(e) -> List[Tuple[Vec2, Vec2]]:
    x1, y1, x2, y2 = e.p1.x, e.p1.y, e.p2.x, e.p2.y
    c = [Vec2(x1, y1), Vec2(x2, y1), Vec2(x2, y2), Vec2(x1, y2)]
    return list(zip(c, c[1:] + [c[0]]))


def _polyline_segments(e) -> List[Tuple[Vec2, Vec2]]:
    pts = e.points
    segs = list(zip(pts, pts[1:]))
    if getattr(e, "closed", False) and len(pts) > 1:
        segs.append((pts[-1], pts[0]))
    return segs
