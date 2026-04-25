"""Modify — Move command."""
from __future__ import annotations

import copy
from typing import List

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import (
    BaseEntity, Vec2,
    LineEntity, CircleEntity, ArcEntity, RectangleEntity, PolylineEntity,
)
from app.commands.modify_helpers import (
    _collect_selected, _transform_entity, _translate, _TransformUndoCommand,
)


@command("moveCommand")
class MoveCommand(CommandBase):
    """Translate selected entities by a displacement vector from a base point."""

    def execute(self) -> None:
        entities = _collect_selected(self.editor)
        if not entities:
            self.editor.status_message.emit("Move: select entities first, then run Move")
            return

        base = self.editor.get_point("Move: pick base point")
        self.editor.snap_from_point = base
        try:
            def _preview(mouse: Vec2) -> List[BaseEntity]:
                dx, dy = mouse.x - base.x, mouse.y - base.y
                return [_transform_entity(e, lambda v, _dx=dx, _dy=dy: _translate(v, _dx, _dy))
                        for e in entities]

            with self.editor.preview(_preview):
                vector_tip = self.editor.get_point("Move: specify displacement vector")
        finally:
            self.editor.snap_from_point = None

        delta = vector_tip - base
        dx, dy = delta.x, delta.y
        doc = self.editor.document

        before = [copy.deepcopy(e) for e in entities]
        for ent in entities:
            if isinstance(ent, LineEntity):
                ent.p1 = _translate(ent.p1, dx, dy)
                ent.p2 = _translate(ent.p2, dx, dy)
            elif isinstance(ent, (CircleEntity, ArcEntity)):
                ent.center = _translate(ent.center, dx, dy)
            elif isinstance(ent, RectangleEntity):
                ent.p1 = _translate(ent.p1, dx, dy)
                ent.p2 = _translate(ent.p2, dx, dy)
            elif isinstance(ent, PolylineEntity):
                ent.points = [_translate(p, dx, dy) for p in ent.points]
            else:
                for attr in ("p1", "p2", "center", "start", "end"):
                    v = getattr(ent, attr, None)
                    if isinstance(v, Vec2):
                        setattr(ent, attr, _translate(v, dx, dy))
                if hasattr(ent, "points"):
                    ent.points = [_translate(p, dx, dy) for p in ent.points]

        after = [copy.deepcopy(e) for e in entities]
        self.editor.push_undo_command(_TransformUndoCommand(doc, before, after, "Move"))
        self.editor.selection.clear()
        self.editor.notify_document()
