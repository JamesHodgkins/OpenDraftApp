"""
Hit-testing utilities for entity selection.

All heavy geometry is now implemented on the entity classes themselves (the
entity protocol: ``bounding_box``, ``hit_test``, ``crosses_rect``).  This
module provides thin shims so the rest of the codebase stays call-compatible.

Functions kept here
-------------------
``entity_bbox``              — delegates to ``e.bounding_box()``.
``entity_bounding_box``      — legacy tuple alias (backward compat).
``bbox_intersects_viewport`` — fast AABB check for the paint loop.
``hit_test_point``           — delegates to ``e.hit_test()``.
``entity_inside_rect``       — window (fully-inside) selection.
``entity_crosses_rect``      — delegates to ``e.crosses_rect()``.
"""
from __future__ import annotations

from typing import Optional, Tuple

from app.entities.base import BaseEntity, BBox, Vec2

# Re-export BBox so any code that imported it from here keeps working.
__all__ = [
    "BBox",
    "entity_bbox",
    "entity_bounding_box",
    "bbox_intersects_viewport",
    "hit_test_point",
    "entity_inside_rect",
    "entity_crosses_rect",
]



# ---------------------------------------------------------------------------
# Bounding box
# ---------------------------------------------------------------------------

def entity_bbox(e: BaseEntity) -> Optional[BBox]:
    """Return the axis-aligned bounding box of *e*, delegating to the entity."""
    return e.bounding_box()


_TupleBBox = Tuple[float, float, float, float]


def entity_bounding_box(e: BaseEntity) -> Optional[_TupleBBox]:
    """Return ``(min_x, min_y, max_x, max_y)`` or ``None``.

    .. deprecated::
        Use :func:`entity_bbox` / ``e.bounding_box()``.  Retained for
        paint-loop backward compatibility.
    """
    bb = e.bounding_box()
    if bb is None:
        return None
    return (bb.min_x, bb.min_y, bb.max_x, bb.max_y)


def bbox_intersects_viewport(
    bbox: _TupleBBox,
    vp_min_x: float,
    vp_min_y: float,
    vp_max_x: float,
    vp_max_y: float,
) -> bool:
    """Return ``True`` if *bbox* tuple overlaps the viewport rectangle."""
    bx0, by0, bx1, by1 = bbox
    return not (bx1 < vp_min_x or bx0 > vp_max_x or by1 < vp_min_y or by0 > vp_max_y)


# ---------------------------------------------------------------------------
# Point proximity (click selection)
# ---------------------------------------------------------------------------

def hit_test_point(e: BaseEntity, pt: Vec2, tolerance: float) -> bool:
    """Return True if *pt* is within *tolerance* world units of entity *e*."""
    return e.hit_test(pt, tolerance)


# ---------------------------------------------------------------------------
# Window containment (left-to-right drag)
# ---------------------------------------------------------------------------

def entity_inside_rect(e: BaseEntity, rmin: Vec2, rmax: Vec2) -> bool:
    """Return True if the entity is *fully* inside the rectangle [rmin, rmax]."""
    bb = e.bounding_box()
    if bb is None:
        return False
    sel = BBox(rmin.x, rmin.y, rmax.x, rmax.y)
    return sel.contains(bb)


# ---------------------------------------------------------------------------
# Crossing intersection (right-to-left drag)
# ---------------------------------------------------------------------------

def entity_crosses_rect(e: BaseEntity, rmin: Vec2, rmax: Vec2) -> bool:
    """Return True if the entity is inside *or* crosses the rectangle."""
    return e.crosses_rect(rmin, rmax)

