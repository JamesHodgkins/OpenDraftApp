"""Modify — Move command."""
from __future__ import annotations

from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import BaseEntity, Vec2
from app.commands.modify_helpers import (
    _collect_selected, _transform_entity, _translate, _commit_transform,
)


@command("moveCommand", aliases=("m", "mv"))
class MoveCommand(StatefulCommandBase):
    """Translate selected entities by a displacement vector from a base point."""

    base_point = export(None, label="Base point", input_kind="point")
    displacement = export(None, label="Displacement", input_kind="vector")

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._entities: list[BaseEntity] = []

    def start(self) -> bool | None:
        self._entities = _collect_selected(self.editor)
        if not self._entities:
            self.editor.status_message.emit("Move: select entities first, then run Move")
            return False
        self.begin(active_export="base_point", reset=("base_point", "displacement"))
        return None

    def live_preview_value(self, name, cursor):
        if name == "displacement":
            base = self.point_value("base_point")
            if base is None:
                return None
            return cursor - base
        return super().live_preview_value(name, cursor)

    def update(self) -> None:
        base = self.point_value("base_point")
        vector = self.vector_value("displacement")
        tip = base + vector if base is not None and vector is not None else None

        self.set_snap_for_active(
            {
                "displacement": base,
                "base_point": tip,
            },
            default=(base, tip),
        )

        if base is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2) -> list[BaseEntity]:
            tip_point = tip if tip is not None else mouse
            dx = tip_point.x - base.x
            dy = tip_point.y - base.y
            return [
                _transform_entity(
                    entity,
                    lambda v, _dx=dx, _dy=dy: _translate(v, _dx, _dy),
                )
                for entity in self._entities
            ]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        base = self.point_value("base_point")
        vector = self.vector_value("displacement")
        if base is None or vector is None:
            self.editor.status_message.emit("Move: base point and displacement are required")
            return
        _commit_transform(
            self.editor,
            self._entities,
            lambda v, _dx=vector.x, _dy=vector.y: _translate(v, _dx, _dy),
            description="Move",
        )

