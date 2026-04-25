"""Modify — Offset command."""
from __future__ import annotations

import copy
import math
import uuid
from typing import List, Optional

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import BaseEntity, Vec2
from app.entities import LineEntity, CircleEntity, ArcEntity, PolylineEntity
from app.commands.modify_helpers import (
    _collect_selected, _copy_style, _ReplaceEntitiesUndoCommand,
)


def _offset_line(ent: LineEntity, distance: float) -> List[LineEntity]:
    """Return two offset copies of a line (one each side) when distance < 0, or one."""
    dx = ent.p2.x - ent.p1.x
    dy = ent.p2.y - ent.p1.y
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return []
    nx = -dy / length
    ny = dx / length

    def _make(d: float) -> LineEntity:
        e = copy.deepcopy(ent)
        e.id = str(uuid.uuid4())
        e.p1 = Vec2(ent.p1.x + nx * d, ent.p1.y + ny * d)
        e.p2 = Vec2(ent.p2.x + nx * d, ent.p2.y + ny * d)
        return e

    return [_make(distance)]


def _offset_circle(ent: CircleEntity, distance: float) -> List[CircleEntity]:
    new_r = ent.radius + distance
    if new_r <= 0:
        return []
    e = copy.deepcopy(ent)
    e.id = str(uuid.uuid4())
    e.radius = new_r
    return [e]


def _offset_arc(ent: ArcEntity, distance: float) -> List[ArcEntity]:
    new_r = ent.radius + distance
    if new_r <= 0:
        return []
    e = copy.deepcopy(ent)
    e.id = str(uuid.uuid4())
    e.radius = new_r
    return [e]


def _offset_polyline(ent: PolylineEntity, distance: float) -> List[PolylineEntity]:
    pts = ent.points
    if len(pts) < 2:
        return []

    # Compute per-segment normals
    normals = []
    for i in range(len(pts) - 1):
        dx = pts[i + 1].x - pts[i].x
        dy = pts[i + 1].y - pts[i].y
        length = math.hypot(dx, dy)
        if length < 1e-12:
            normals.append((0.0, 0.0))
        else:
            normals.append((-dy / length, dx / length))

    # Offset each vertex by averaging adjacent segment normals
    new_pts: List[Vec2] = []
    for i, pt in enumerate(pts):
        if i == 0:
            nx, ny = normals[0]
        elif i == len(pts) - 1:
            nx, ny = normals[-1]
        else:
            n1 = normals[i - 1]
            n2 = normals[i]
            nx = (n1[0] + n2[0]) / 2
            ny = (n1[1] + n2[1]) / 2
            mag = math.hypot(nx, ny)
            if mag > 1e-12:
                # Miter correction so offset distance stays consistent
                dot = n1[0] * n2[0] + n1[1] * n2[1]
                miter = 1.0 / max(0.01, (1.0 + dot) / 2) ** 0.5
                nx = nx / mag * miter
                ny = ny / mag * miter
        new_pts.append(Vec2(pt.x + nx * distance, pt.y + ny * distance))

    e = copy.deepcopy(ent)
    e.id = str(uuid.uuid4())
    e.points = new_pts
    return [e]


def _offset_entity(ent: BaseEntity, distance: float) -> List[BaseEntity]:
    if isinstance(ent, LineEntity):
        return _offset_line(ent, distance)
    if isinstance(ent, CircleEntity):
        return _offset_circle(ent, distance)
    if isinstance(ent, ArcEntity):
        return _offset_arc(ent, distance)
    if isinstance(ent, PolylineEntity):
        return _offset_polyline(ent, distance)
    return []


def _signed_side(ent: BaseEntity, pt: Vec2) -> float:
    """Return a positive value if *pt* is on the 'positive normal' side of *ent*,
    negative otherwise. Used to determine offset direction from a picked point."""
    if isinstance(ent, LineEntity):
        dx = ent.p2.x - ent.p1.x
        dy = ent.p2.y - ent.p1.y
        # Cross product of line direction with (pt - p1)
        return dx * (pt.y - ent.p1.y) - dy * (pt.x - ent.p1.x)
    if isinstance(ent, (CircleEntity, ArcEntity)):
        # Positive = outside (farther than radius), negative = inside
        d = math.hypot(pt.x - ent.center.x, pt.y - ent.center.y)
        return d - ent.radius
    if isinstance(ent, PolylineEntity):
        # Use the first segment's normal
        pts = ent.points
        if len(pts) < 2:
            return 0.0
        dx = pts[1].x - pts[0].x
        dy = pts[1].y - pts[0].y
        return dx * (pt.y - pts[0].y) - dy * (pt.x - pts[0].x)
    return 0.0


@command("offsetCommand")
class OffsetCommand(CommandBase):
    """Offset selected entities by a given distance."""

    def execute(self) -> None:
        entities = _collect_selected(self.editor)
        supported = [e for e in entities
                     if isinstance(e, (LineEntity, CircleEntity, ArcEntity, PolylineEntity))]

        if not supported:
            self.editor.status_message.emit(
                "Offset: select lines, arcs, circles or polylines first, then run Offset")
            return

        distance = self.editor.get_length("Offset: enter offset distance")
        if distance <= 0:
            self.editor.status_message.emit("Offset: distance must be positive")
            return

        mode = self.editor.get_choice(
            "Offset: both sides, or pick a side?", ["both", "pick side"])

        if mode == "pick side":
            side_pt = self.editor.get_point("Offset: click to indicate which side")

        doc = self.editor.document
        added: List[BaseEntity] = []

        for ent in supported:
            if mode == "both":
                distances = [distance, -distance]
            else:
                sign = 1.0 if _signed_side(ent, side_pt) >= 0 else -1.0
                distances = [sign * distance]

            for d in distances:
                for new_ent in _offset_entity(ent, d):
                    doc.add_entity(new_ent)
                    self.editor.entity_added.emit(new_ent)
                    added.append(new_ent)

        if added:
            self.editor.push_undo_command(
                _ReplaceEntitiesUndoCommand(doc, [], [], added, "Offset"))
            self.editor.notify_document()
        else:
            self.editor.status_message.emit("Offset: no valid results (distance too large?)")
