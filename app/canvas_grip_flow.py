"""Grip-edit lifecycle helpers for CADCanvas.

These helpers isolate grip activation, drag preview updates, and commit/reset
logic so canvas event handlers stay focused on high-level orchestration.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

from app.editor.osnap_engine import SnapResult
from app.entities import Vec2
from app.entities.base import GripPoint


def _is_coincident(a: Vec2, b: Vec2, tol: float) -> bool:
    return a.distance_to(b) <= tol


def collect_linked_grips(
    document,
    *,
    selected_ids: set[str],
    active_grip: GripPoint,
    coincidence_tol: float = 1e-9,
) -> list[GripPoint]:
    """Return grips on *selected* entities that coincide with *active_grip*.

    This is used for "move coincident grips together" behaviour: if two selected
    entities expose grip points at the same world position, dragging one should
    move all coincident grips as a linked group.
    """
    if document is None or not selected_ids:
        return [active_grip]

    anchor = active_grip.position
    linked: list[GripPoint] = []
    seen: set[tuple[str, int]] = set()

    for ent in document:
        if ent.id not in selected_ids:
            continue
        for gp in ent.grip_points():
            if not _is_coincident(gp.position, anchor, coincidence_tol):
                continue
            key = (gp.entity_id, gp.index)
            if key in seen:
                continue
            linked.append(gp)
            seen.add(key)

    # Always include the active grip, even if something odd happened.
    if (active_grip.entity_id, active_grip.index) not in seen:
        linked.insert(0, active_grip)

    return linked


def resolve_grip_final_position(
    world_point: Vec2,
    snap_result: Optional[SnapResult],
    grip_drag_world: Optional[Vec2],
) -> Vec2:
    """Resolve final grip placement point with snap and drag fallback."""
    if snap_result is not None:
        return snap_result.point
    if grip_drag_world is not None:
        return grip_drag_world
    return world_point


def activate_hot_grip(
    document,
    hot_grip: GripPoint,
    world_point: Vec2,
    *,
    selected_ids: set[str],
    coincidence_tol: float = 1e-9,
) -> tuple[GripPoint, dict[str, Any], list[Any], Vec2, list[GripPoint]]:
    """Build initial active-grip state from a hot grip hit."""
    linked_grips = collect_linked_grips(
        document,
        selected_ids=selected_ids,
        active_grip=hot_grip,
        coincidence_tol=coincidence_tol,
    )

    snapshots: dict[str, Any] = {}
    before: list[Any] = []

    if document is not None:
        linked_ids = {g.entity_id for g in linked_grips}
        for ent in document:
            if ent.id not in linked_ids:
                continue
            snapshots[ent.id] = copy.deepcopy(ent)
            before.append(copy.deepcopy(ent))

    return hot_grip, snapshots, before, world_point, linked_grips


def update_active_grip_drag(
    raw: Vec2,
    *,
    document,
    active_grip: GripPoint,
    linked_grips: list[GripPoint],
    osnap_engine,
    osnap_master: bool,
    scale: float,
    grip_entity_snapshots: dict[str, Any],
) -> tuple[Optional[SnapResult], Vec2, dict[str, Any]]:
    """Update grip drag preview state for the current cursor position."""
    if document is not None and osnap_master:
        snap_entities = [
            ent for ent in document.entities
            if ent.id != active_grip.entity_id
        ]
        snap_result = osnap_engine.snap(raw, snap_entities, scale)
    else:
        snap_result = None

    display_grip = snap_result.point if snap_result is not None else raw

    updated_snapshots: dict[str, Any] = dict(grip_entity_snapshots or {})
    if document is not None and linked_grips:
        # Rebuild from live entities each frame to avoid cumulative drift.
        linked_by_id: dict[str, list[GripPoint]] = {}
        for gp in linked_grips:
            linked_by_id.setdefault(gp.entity_id, []).append(gp)

        for ent in document:
            if ent.id not in linked_by_id:
                continue
            ecopy = copy.deepcopy(ent)
            for gp in linked_by_id[ent.id]:
                ecopy.move_grip(gp.index, display_grip)
            updated_snapshots[ent.id] = ecopy

    return snap_result, display_grip, updated_snapshots


def commit_active_grip_edit(
    *,
    document,
    active_grip: GripPoint,
    linked_grips: list[GripPoint],
    final_pos: Vec2,
    before_snapshots: list[Any],
    editor,
) -> bool:
    """Commit active grip edit to document and push undo when possible."""
    if document is None:
        return False

    from app.commands.modify_helpers import _TransformUndoCommand

    linked_by_id: dict[str, list[GripPoint]] = {}
    for gp in (linked_grips or [active_grip]):
        linked_by_id.setdefault(gp.entity_id, []).append(gp)

    after_snapshots: list[Any] = []
    any_applied = False

    for ent in document:
        if ent.id not in linked_by_id:
            continue
        for gp in linked_by_id[ent.id]:
            ent.move_grip(gp.index, final_pos)
        after_snapshots.append(copy.deepcopy(ent))
        any_applied = True

    if any_applied and before_snapshots and editor is not None:
        editor._undo_stack.push(
            _TransformUndoCommand(document, before_snapshots, after_snapshots, "Grip Edit")
        )
        editor.document_changed.emit()
        return True

    return False


def cleared_active_grip_state() -> tuple[None, dict, list, None, list]:
    """Return canonical cleared active-grip state tuple."""
    return None, {}, [], None, []
