"""Modify — Copy command."""
from __future__ import annotations

from typing import List

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import BaseEntity, Vec2
from app.commands.modify_helpers import (
    _collect_selected, _transform_entity, _translate, _ReplaceEntitiesUndoCommand,
)


@command("copyCommand")
class CopyCommand(CommandBase):
    """Copy selected entities; supports multiple placements before Escape."""

    def execute(self) -> None:
        entities = _collect_selected(self.editor)
        if not entities:
            self.editor.status_message.emit("Copy: select entities first, then run Copy")
            return

        base = self.editor.get_point("Copy: pick base point")

        while True:
            def _preview(mouse: Vec2) -> List[BaseEntity]:
                dx, dy = mouse.x - base.x, mouse.y - base.y
                return [_transform_entity(e, lambda v, _dx=dx, _dy=dy: _translate(v, _dx, _dy))
                        for e in entities]

            self.editor.set_dynamic(_preview)
            dest = self.editor.get_point("Copy: pick destination (Escape to finish)")
            self.editor.clear_dynamic()

            dx, dy = dest.x - base.x, dest.y - base.y
            doc = self.editor.document
            added: List[BaseEntity] = []
            for ent in entities:
                new_ent = _transform_entity(ent, lambda v, _dx=dx, _dy=dy: _translate(v, _dx, _dy))
                doc.add_entity(new_ent)
                self.editor.entity_added.emit(new_ent)
                added.append(new_ent)

            self.editor._undo_stack.push(
                _ReplaceEntitiesUndoCommand(doc, [], [], added, "Copy"))
            doc._notify()
            self.editor.document_changed.emit()
