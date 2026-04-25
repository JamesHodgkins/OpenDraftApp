"""Interaction helpers for CADCanvas input and selection behavior.

This module centralizes point-resolution and selection/hit-testing rules so
CADCanvas can focus on UI orchestration.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from PySide6.QtCore import QPointF

from app.editor.draftmate import DraftmateResult
from app.editor.osnap_engine import SnapResult
from app.entities import Vec2
from app.entities.base import GripPoint


def resolve_display_point(
    raw: Vec2,
    snap_result: Optional[SnapResult],
    draftmate_result: Optional[DraftmateResult],
    *,
    ortho: bool,
    from_point: Optional[Vec2],
) -> Vec2:
    """Resolve final cursor/display point with Draftmate, OSNAP, and Ortho."""
    if draftmate_result is not None and draftmate_result.snapped_point is not None:
        display = draftmate_result.snapped_point
    elif snap_result is not None:
        display = snap_result.point
    else:
        display = raw

    if (
        ortho
        and from_point is not None
        and snap_result is None
        and (draftmate_result is None or draftmate_result.snapped_point is None)
    ):
        dx = display.x - from_point.x
        dy = display.y - from_point.y
        if abs(dx) >= abs(dy):
            return Vec2(display.x, from_point.y)
        return Vec2(from_point.x, display.y)

    return display


def selection_drag_exceeds_threshold(
    origin_screen: QPointF,
    current_screen: QPointF,
    threshold: float,
) -> bool:
    """Return True when drag distance exceeds the start-selection threshold."""
    dx = current_screen.x() - origin_screen.x()
    dy = current_screen.y() - origin_screen.y()
    return (dx * dx + dy * dy) > (threshold * threshold)


def normalized_selection_rect(origin_world: Vec2, end_world: Vec2) -> tuple[Vec2, Vec2]:
    """Return normalized min/max world corners for a drag rectangle."""
    rmin = Vec2(min(origin_world.x, end_world.x), min(origin_world.y, end_world.y))
    rmax = Vec2(max(origin_world.x, end_world.x), max(origin_world.y, end_world.y))
    return rmin, rmax


def is_window_selection(origin_screen: QPointF, release_screen: QPointF) -> bool:
    """Left-to-right drag is a window selection; right-to-left is crossing."""
    return release_screen.x() >= origin_screen.x()


def find_hot_grip(
    entities: Iterable,
    selected_ids: set[str],
    cursor_world: Vec2,
    grip_tol_world: float,
) -> Optional[GripPoint]:
    """Find first selected-entity grip under the cursor in world units."""
    tol2 = grip_tol_world * grip_tol_world
    for ent in entities:
        if ent.id not in selected_ids:
            continue
        for grip in ent.grip_points():
            dx = cursor_world.x - grip.position.x
            dy = cursor_world.y - grip.position.y
            if (dx * dx + dy * dy) <= tol2:
                return grip
    return None


def find_hit_entity_id(
    entities: Iterable,
    *,
    get_layer: Callable[[str], Any],
    point_world: Vec2,
    tolerance_world: float,
    hit_test_point: Callable[..., bool],
    use_bbox_rejection: bool,
) -> Optional[str]:
    """Find first visible entity hit by point/tolerance; returns entity id."""
    for ent in entities:
        layer = get_layer(ent.layer)
        if layer is not None and not layer.visible:
            continue

        if use_bbox_rejection:
            bb = ent.bounding_box()
            if bb is not None and (
                bb.max_x + tolerance_world < point_world.x
                or bb.min_x - tolerance_world > point_world.x
                or bb.max_y + tolerance_world < point_world.y
                or bb.min_y - tolerance_world > point_world.y
            ):
                continue

        if hit_test_point(ent, point_world, tolerance_world):
            return ent.id
    return None


def collect_rect_selection_ids(
    entities: Iterable,
    *,
    get_layer: Callable[[str], Any],
    rmin: Vec2,
    rmax: Vec2,
    is_window: bool,
    entity_inside_rect: Callable[..., bool],
    entity_crosses_rect: Callable[..., bool],
) -> set[str]:
    """Collect ids matched by window or crossing rectangle selection."""
    matched: set[str] = set()
    for ent in entities:
        layer = get_layer(ent.layer)
        if layer is not None and not layer.visible:
            continue
        if is_window:
            if entity_inside_rect(ent, rmin, rmax):
                matched.add(ent.id)
        else:
            if entity_crosses_rect(ent, rmin, rmax):
                matched.add(ent.id)
    return matched
