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
) -> tuple[GripPoint, Any, Any, Vec2]:
    """Build initial active-grip state from a hot grip hit."""
    grip_snapshot = None
    before_snapshot = None

    if document is not None:
        for ent in document:
            if ent.id == hot_grip.entity_id:
                grip_snapshot = copy.deepcopy(ent)
                before_snapshot = copy.deepcopy(ent)
                break

    return hot_grip, grip_snapshot, before_snapshot, world_point


def update_active_grip_drag(
    raw: Vec2,
    *,
    document,
    active_grip: GripPoint,
    osnap_engine,
    osnap_master: bool,
    scale: float,
    grip_entity_snapshot,
) -> tuple[Optional[SnapResult], Vec2, Any]:
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

    updated_snapshot = grip_entity_snapshot
    if grip_entity_snapshot is not None:
        # Rebuild from original entity each frame to avoid cumulative drift.
        for ent in (document or []):
            if ent.id == active_grip.entity_id:
                updated_snapshot = copy.deepcopy(ent)
                break
        updated_snapshot.move_grip(active_grip.index, display_grip)

    return snap_result, display_grip, updated_snapshot


def commit_active_grip_edit(
    *,
    document,
    active_grip: GripPoint,
    final_pos: Vec2,
    before_snapshot,
    editor,
) -> bool:
    """Commit active grip edit to document and push undo when possible."""
    if document is None:
        return False

    from app.commands.modify_helpers import _TransformUndoCommand

    for ent in document:
        if ent.id != active_grip.entity_id:
            continue

        ent.move_grip(active_grip.index, final_pos)
        after = copy.deepcopy(ent)

        if before_snapshot is not None and editor is not None:
            editor._undo_stack.push(
                _TransformUndoCommand(document, [before_snapshot], [after], "Grip Edit")
            )
            editor.document_changed.emit()
        return True

    return False


def cleared_active_grip_state() -> tuple[None, None, None, None]:
    """Return canonical cleared active-grip state tuple."""
    return None, None, None, None
