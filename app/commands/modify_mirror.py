"""Modify — Mirror command."""
from __future__ import annotations

import copy
import math
import uuid
from typing import List

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import (
    BaseEntity, Vec2,
    LineEntity, CircleEntity, ArcEntity, RectangleEntity, PolylineEntity,
)
from app.commands.modify_helpers import (
    _collect_selected, _mirror_pt, _ReplaceEntitiesUndoCommand,
)


def _mirror_entity(ent: BaseEntity, ax: float, ay: float,
                   bx: float, by: float) -> BaseEntity:
    e = copy.deepcopy(ent)
    e.id = str(uuid.uuid4())
    fn = lambda v: _mirror_pt(v, ax, ay, bx, by)
    if isinstance(e, LineEntity):
        e.p1 = fn(e.p1)
        e.p2 = fn(e.p2)
    elif isinstance(e, (CircleEntity, ArcEntity)):
        e.center = fn(e.center)
        if isinstance(e, ArcEntity):
            axis_angle = math.atan2(by - ay, bx - ax)
            e.start_angle = 2 * axis_angle - ent.end_angle
            e.end_angle   = 2 * axis_angle - ent.start_angle
            e.ccw = not ent.ccw
    elif isinstance(e, RectangleEntity):
        mirrored_corners = [fn(c) for c in ent._corners()]
        poly = PolylineEntity(
            points=mirrored_corners,
            closed=True,
        )
        poly.layer      = ent.layer
        poly.color      = ent.color
        poly.line_weight = ent.line_weight
        poly.line_style  = ent.line_style
        return poly
    elif isinstance(e, PolylineEntity):
        e.points = [fn(p) for p in e.points]
    else:
        for attr in ("p1", "p2", "center", "start", "end"):
            v = getattr(e, attr, None)
            if isinstance(v, Vec2):
                setattr(e, attr, fn(v))
        if hasattr(e, "points"):
            e.points = [fn(p) for p in e.points]
    return e


@command("mirrorCommand")
class MirrorCommand(CommandBase):
    """Mirror selected entities across a two-point axis."""

    def execute(self) -> None:
        entities = _collect_selected(self.editor)
        if not entities:
            self.editor.status_message.emit("Mirror: select entities first, then run Mirror")
            return

        p1 = self.editor.get_point("Mirror: pick first point of mirror axis")
        self.editor.snap_from_point = p1

        def _preview(mouse: Vec2) -> List[BaseEntity]:
            ax, ay = p1.x, p1.y
            bx, by = mouse.x, mouse.y
            return [_mirror_entity(e, ax, ay, bx, by) for e in entities]

        with self.editor.preview(_preview):
            p2 = self.editor.get_point("Mirror: pick second point of mirror axis")

        ax, ay = p1.x, p1.y
        bx, by = p2.x, p2.y
        doc = self.editor.document

        mirrored = [_mirror_entity(e, ax, ay, bx, by) for e in entities]

        keep_originals = (self.editor.get_choice(
            "Mirror: keep originals?", ["Y", "N"]) == "Y")

        if keep_originals:
            for ent in mirrored:
                doc.add_entity(ent)
                self.editor.entity_added.emit(ent)
            self.editor.push_undo_command(
                _ReplaceEntitiesUndoCommand(doc, [], [], mirrored, "Mirror (keep)"))
        else:
            orig_indices: List[int] = []
            for ent in entities:
                for i, e in enumerate(doc.entities):
                    if e.id == ent.id:
                        orig_indices.append(i)
                        break
            for ent in entities:
                doc.remove_entity(ent.id)
                self.editor.entity_removed.emit(ent.id)
            for ent in mirrored:
                doc.add_entity(ent)
                self.editor.entity_added.emit(ent)
            self.editor.push_undo_command(
                _ReplaceEntitiesUndoCommand(
                    doc, entities, orig_indices, mirrored, "Mirror (delete originals)"))

        self.editor.selection.clear()
        self.editor.notify_document()
