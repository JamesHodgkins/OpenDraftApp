"""Modify — Mirror command."""
from __future__ import annotations

import copy
import math
import uuid

from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
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
            # Reflection maps the point that was at start_angle/end_angle to
            # the same reflected angle (2*axis - angle) — start and end keep
            # their roles, they don't swap — and reverses the sense of
            # travel between them, so ccw flips. Swapping start/end *and*
            # flipping ccw (the previous behaviour) canceled out and left
            # the arc traversing the *outside* of its span, e.g. a 90°
            # arc came out as the remaining 270° of the circle.
            axis_angle = math.atan2(by - ay, bx - ax)
            e.start_angle = 2 * axis_angle - ent.start_angle
            e.end_angle   = 2 * axis_angle - ent.end_angle
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
class MirrorCommand(StatefulCommandBase):
    """Mirror selected entities across a two-point axis."""

    axis_start = export(None, label="Axis start", input_kind="point")
    axis_end = export(None, label="Axis end", input_kind="point")
    keep_originals = export(None, label="Keep originals", input_kind="choice")

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._entities: list[BaseEntity] = []

    def start(self) -> bool | None:
        self._entities = _collect_selected(self.editor)
        if not self._entities:
            self.editor.status_message.emit("Mirror: select entities first, then run Mirror")
            return False
        self.begin(active_export="axis_start", reset=("axis_start", "axis_end", "keep_originals"))
        return None

    def advance_active_export(self) -> None:
        if self.active_export == "axis_start" and self.point_value("axis_start") is not None:
            self.active_export = "axis_end"
            return
        if self.active_export == "axis_end" and self.point_value("axis_end") is not None:
            self.active_export = "keep_originals"
            return
        if self.active_export == "keep_originals" and self.string_value("keep_originals") is not None:
            self.active_export = ""

    def all_exports_set(self) -> bool:
        return (
            not self.active_export
            and self.point_value("axis_start") is not None
            and self.point_value("axis_end") is not None
            and self.string_value("keep_originals") is not None
        )

    def update(self) -> None:
        p1 = self.point_value("axis_start")
        p2 = self.point_value("axis_end")

        self.editor._choice_options = ["Y", "N"] if self.active_export == "keep_originals" else []
        self.set_snap_for_active(
            {
                "axis_end": p1,
            },
            default=(p1, p2),
        )

        if p1 is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2) -> list[BaseEntity]:
            end = p2 if p2 is not None else mouse
            ax, ay = p1.x, p1.y
            bx, by = end.x, end.y
            return [_mirror_entity(entity, ax, ay, bx, by) for entity in self._entities]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        p1 = self.point_value("axis_start")
        p2 = self.point_value("axis_end")
        keep = (self.string_value("keep_originals") or "").upper()
        if p1 is None or p2 is None or keep not in {"Y", "N"}:
            self.editor.status_message.emit("Mirror: axis and keep-originals choice are required")
            return

        ax, ay = p1.x, p1.y
        bx, by = p2.x, p2.y
        doc = self.editor.document
        mirrored = [_mirror_entity(entity, ax, ay, bx, by) for entity in self._entities]

        if keep == "Y":
            for entity in mirrored:
                doc.add_entity(entity)
                self.editor.entity_added.emit(entity)
            self.editor.push_undo_command(
                _ReplaceEntitiesUndoCommand(doc, [], [], mirrored, "Mirror (keep)")
            )
        else:
            orig_indices: list[int] = []
            for entity in self._entities:
                for index, current in enumerate(doc.entities):
                    if current.id == entity.id:
                        orig_indices.append(index)
                        break
            for entity in self._entities:
                doc.remove_entity(entity.id)
                self.editor.entity_removed.emit(entity.id)
            for entity in mirrored:
                doc.add_entity(entity)
                self.editor.entity_added.emit(entity)
            self.editor.push_undo_command(
                _ReplaceEntitiesUndoCommand(
                    doc,
                    self._entities,
                    orig_indices,
                    mirrored,
                    "Mirror (delete originals)",
                )
            )

        self.editor.selection.clear()
        self.editor.notify_document()
