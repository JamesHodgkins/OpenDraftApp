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
from typing import Iterable, List, Optional, Tuple

from app.entities import BaseEntity, Vec2
# SnapType / SnapResult now live in the entities package to avoid circular
# imports when entity classes reference them.  Re-exported here so that any
# existing code importing from osnap_engine continues to work unchanged.
from app.entities.snap_types import SnapResult, SnapType

__all__ = ["OsnapEngine", "SnapResult", "SnapType"]

# Public types — now imported from entities.snap_types


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

        tol = self.radius_px / scale        # world-space snap radius

        # Pre-filter: only consider entities whose bounding box is within
        # the snap aperture of the cursor.  This avoids running expensive
        # snap-candidate computation for far-away entities.
        nearby: List[BaseEntity] = []
        for e in entities:
            bb = e.bounding_box()
            if bb is None:
                nearby.append(e)          # unknown geometry — include as fallback
                continue
            if (bb.min_x - tol <= cursor.x <= bb.max_x + tol and
                    bb.min_y - tol <= cursor.y <= bb.max_y + tol):
                nearby.append(e)

        candidates: List[Tuple[float, SnapResult]] = []

        # Cursor-independent snaps (endpoint, midpoint, center, quadrant)
        for e in nearby:
            for result in self._candidates_for(e):
                dist = _dist(result.point, cursor)
                if dist <= tol:
                    candidates.append((dist, result))

        # Intersection snaps (pairwise) — limited to nearby entities
        if SnapType.INTERSECTION in self.enabled:
            for i, a in enumerate(nearby):
                for b in nearby[i + 1:]:
                    for pt in self._intersections(a, b):
                        dist = _dist(pt, cursor)
                        if dist <= tol:
                            candidates.append((
                                dist,
                                SnapResult(pt, SnapType.INTERSECTION, a.id),
                            ))

        # PERPENDICULAR — foot of perpendicular from from_point onto entity
        if SnapType.PERPENDICULAR in self.enabled and from_point is not None:
            for e in nearby:
                for result in self._perp_on_entity(e, from_point):
                    dist = _dist(result.point, cursor)
                    if dist <= tol:
                        candidates.append((dist, result))

        # NEAREST is a true fallback — only considered when nothing else snapped.
        if not candidates and SnapType.NEAREST in self.enabled:
            for e in nearby:
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
        """Cursor-independent snap candidates — delegates to entity protocol."""
        return e.snap_candidates(self.enabled)

    # ------------------------------------------------------------------
    # NEAREST — delegates to entity protocol

    def _nearest_on_entity(self, e: BaseEntity, cursor: Vec2) -> Optional[SnapResult]:
        """Closest point on *e*'s geometry to *cursor* — delegates to entity."""
        return e.nearest_snap(cursor)

    # ------------------------------------------------------------------
    # PERPENDICULAR — delegates to entity protocol

    def _perp_on_entity(self, e: BaseEntity, from_pt: Vec2) -> List[SnapResult]:
        """Perpendicular snap candidates on *e* — delegates to entity."""
        return e.perp_snaps(from_pt)

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
