"""Modify — Copy command."""
from __future__ import annotations

from typing import List

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import BaseEntity, Vec2
from app.commands.modify_helpers import (
    _collect_selected, _transform_entity, _translate, _ReplaceEntitiesUndoCommand,
)


@command("copyCommand", aliases=("cp",))
class CopyCommand(CommandBase):
    """Copy selected entities by vector displacement; supports multiple placements."""

    def execute(self) -> None:
        entities = _collect_selected(self.editor)
        if not entities:
            self.editor.status_message.emit("Copy: select entities first, then run Copy")
            return

        base = self.editor.get_point("Copy: pick base point")
        self.editor.snap_from_point = base
        try:
            while True:
                def _preview(mouse: Vec2) -> List[BaseEntity]:
                    dx, dy = mouse.x - base.x, mouse.y - base.y
                    return [_transform_entity(e, lambda v, _dx=dx, _dy=dy: _translate(v, _dx, _dy))
                            for e in entities]

                with self.editor.preview(_preview):
                    vector_tip = self.editor.get_point(
                        "Copy: specify displacement vector (Escape to finish)"
                    )

                delta = vector_tip - base
                dx, dy = delta.x, delta.y
                doc = self.editor.document
                added: List[BaseEntity] = []
                for ent in entities:
                    new_ent = _transform_entity(ent, lambda v, _dx=dx, _dy=dy: _translate(v, _dx, _dy))
                    doc.add_entity(new_ent)
                    self.editor.entity_added.emit(new_ent)
                    added.append(new_ent)

                self.editor.push_undo_command(
                    _ReplaceEntitiesUndoCommand(doc, [], [], added, "Copy"))
                self.editor.notify_document()
        finally:
            self.editor.snap_from_point = None
