"""Pure 2-D geometry helpers shared across entities and commands.

All functions are stateless and operate only on plain Python scalars and
:class:`~app.entities.base.Vec2` values — no Qt, no entity imports.

The basic point/segment helpers (_geo_*) live in ``app.entities.base`` because
they depend on ``Vec2`` which is defined there.  This module re-exports them
for convenience and adds the arc/intersection helpers that were previously
scattered in ``app.commands.modify_trim`` (and cross-imported by
``app.commands.modify_extend``).

Importing
---------
Prefer importing from this module for all new code::

    from app.geometry import _geo_dist, _seg_seg_param, _arc_span
"""
from __future__ import annotations

import math
from typing import List, Optional

from app.entities.base import (
    Vec2,
    _geo_dist,
    _geo_pt_seg_dist,
    _geo_angle_on_arc,
    _geo_point_in_rect,
    _geo_seg_intersects_rect,
)

# Re-export base helpers so callers only need one import site.
__all__ = [
    "Vec2",
    "_geo_dist",
    "_geo_pt_seg_dist",
    "_geo_angle_on_arc",
    "_geo_point_in_rect",
    "_geo_seg_intersects_rect",
    "_normalize_angle",
    "_arc_span",
    "_arc_parameter",
    "_arc_angle_at_param",
    "_seg_seg_param",
    "_line_circle_params",
    "_circle_circle_angles",
    "_lerp",
]


# ---------------------------------------------------------------------------
# Arc helpers  (originally in app.commands.modify_trim)
# ---------------------------------------------------------------------------

def _normalize_angle(a: float) -> float:
    """Normalise an angle to [0, 2π)."""
    return a % (2.0 * math.pi)


def _arc_span(start: float, end: float, ccw: bool) -> float:
    """Return the signed angular span of an arc."""
    TWO_PI = 2.0 * math.pi
    if ccw:
        span = (end - start) % TWO_PI
        if span < 1e-12:
            span = TWO_PI
    else:
        span = -((start - end) % TWO_PI)
        if abs(span) < 1e-12:
            span = -TWO_PI
    return span


def _arc_parameter(angle: float, start: float, end: float, ccw: bool) -> float:
    """Map *angle* to a [0, 1] parameter along the arc from *start* to *end*."""
    TWO_PI = 2.0 * math.pi
    span = _arc_span(start, end, ccw)
    if abs(span) < 1e-12:
        return 0.0
    if ccw:
        t = ((angle - start) % TWO_PI) / span
    else:
        t = ((start - angle) % TWO_PI) / (-span)
    return max(0.0, min(1.0, t))


def _arc_angle_at_param(start: float, end: float, ccw: bool, t: float) -> float:
    """Return the angle at parameter *t* along the arc."""
    return start + t * _arc_span(start, end, ccw)


# ---------------------------------------------------------------------------
# Intersection helpers  (originally in app.commands.modify_trim)
# ---------------------------------------------------------------------------

def _seg_seg_param(
    a1: Vec2, a2: Vec2, b1: Vec2, b2: Vec2,
) -> Optional[float]:
    """Return t-parameter on segment a1→a2 at its intersection with b1→b2.

    Returns None if the segments do not cross.
    """
    dx1, dy1 = a2.x - a1.x, a2.y - a1.y
    dx2, dy2 = b2.x - b1.x, b2.y - b1.y
    denom = dx1 * dy2 - dy1 * dx2
    if abs(denom) < 1e-12:
        return None
    t = ((b1.x - a1.x) * dy2 - (b1.y - a1.y) * dx2) / denom
    u = ((b1.x - a1.x) * dy1 - (b1.y - a1.y) * dx1) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None


def _line_circle_params(
    p1: Vec2, p2: Vec2, center: Vec2, radius: float,
) -> List[float]:
    """Return t-parameters where the segment p1→p2 intersects the circle."""
    dx, dy = p2.x - p1.x, p2.y - p1.y
    fx, fy = p1.x - center.x, p1.y - center.y
    a = dx * dx + dy * dy
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    disc = b * b - 4.0 * a * c
    if a < 1e-12 or disc < 0:
        return []
    sqrt_disc = math.sqrt(disc)
    results = []
    for sign in (-1, 1):
        t = (-b + sign * sqrt_disc) / (2.0 * a)
        if 0.0 <= t <= 1.0:
            results.append(t)
    return results


def _circle_circle_angles(
    c1: Vec2, r1: float, c2: Vec2, r2: float,
) -> List[float]:
    """Return angles (on circle 1) where two circles intersect."""
    dx = c2.x - c1.x
    dy = c2.y - c1.y
    d = math.hypot(dx, dy)
    if d < 1e-12 or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    h_sq = r1 * r1 - a * a
    if h_sq < -1e-9:
        return []
    h = math.sqrt(max(0.0, h_sq))
    mx = c1.x + a * dx / d
    my = c1.y + a * dy / d
    if h < 1e-9:
        return [math.atan2(my - c1.y, mx - c1.x)]
    angles = []
    for sign in (1, -1):
        ix = mx + sign * h * (-dy) / d
        iy = my + sign * h * dx / d
        angles.append(math.atan2(iy - c1.y, ix - c1.x))
    return angles


def _lerp(a: Vec2, b: Vec2, t: float) -> Vec2:
    """Linear interpolation between two Vec2 points."""
    return Vec2(a.x + t * (b.x - a.x), a.y + t * (b.y - a.y))
