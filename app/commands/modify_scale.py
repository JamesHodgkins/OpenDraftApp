"""Modify — Scale command."""
from __future__ import annotations

import math

from app.editor import command
from app.editor.editor import CommandOption
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import BaseEntity, Vec2
from app.commands.modify_helpers import (
    _collect_selected, _transform_entity, _scale_pt,
    _post_scale_radius, _commit_transform,
)


@command("scaleCommand")
class ScaleCommand(StatefulCommandBase):
    """Scale selected entities about a base point by a numeric factor."""

    base_point = export(None, label="Base point", input_kind="point")
    reference_vector = export(None, label="Reference vector", input_kind="vector")
    factor = export(None, label="Factor", input_kind="float")

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._entities: list[BaseEntity] = []
        self._commit_mode: str = "vector"

    def start(self) -> bool | None:
        self._entities = _collect_selected(self.editor)
        if not self._entities:
            self.editor.status_message.emit("Scale: select entities first, then run Scale")
            return False
        self._commit_mode = "vector"
        self.begin(active_export="base_point", reset=("base_point", "reference_vector", "factor"))
        return None

    def live_preview_value(self, name, cursor):
        base = self.point_value("base_point")
        if base is None:
            return None
        if name == "reference_vector":
            return cursor - base
        if name == "factor":
            raw = math.hypot(cursor.x - base.x, cursor.y - base.y)
            return raw / 100.0 if raw > 1e-6 else 1.0
        return super().live_preview_value(name, cursor)

    def _emit_state_sync(self) -> None:
        self.editor._set_stateful_input_mode(self)
        self.editor.stateful_active_export_changed.emit(self.active_export)
        self.editor._emit_stateful_prompt(self)

    def update(self) -> None:
        base = self.point_value("base_point")
        if self.active_export == "reference_vector":
            self.editor.set_command_options_keyed(
                [CommandOption(key="a", label="Enter factor")]
            )
        else:
            self.editor.clear_command_options()

        self.set_snap_for_active(
            {
                "reference_vector": base,
            },
            default=base,
        )

        if base is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2) -> list[BaseEntity]:
            factor = self.number_value("factor")
            if self.active_export == "reference_vector":
                vector = self.vector_value("reference_vector")
                if vector is not None:
                    raw = math.hypot(vector.x, vector.y)
                else:
                    raw = math.hypot(mouse.x - base.x, mouse.y - base.y)
                factor = raw / 100.0 if raw > 1e-6 else 1.0
            if factor is None:
                return []
            cx, cy = base.x, base.y
            return [
                _transform_entity(
                    entity,
                    lambda v, _cx=cx, _cy=cy, _factor=factor: _scale_pt(v, _cx, _cy, _factor),
                    lambda e, orig, _factor=factor: _post_scale_radius(e, orig, _factor),
                )
                for entity in self._entities
            ]

        self.editor.set_dynamic(_preview)

    def advance_active_export(self) -> None:
        if self.active_export == "base_point" and self.point_value("base_point") is not None:
            self._commit_mode = "vector"
            self.active_export = "reference_vector"
            return
        if self.active_export in {"reference_vector", "factor"}:
            self.active_export = ""

    def all_exports_set(self) -> bool:
        if self.point_value("base_point") is None or self.active_export:
            return False
        if self._commit_mode == "factor":
            return self.number_value("factor") is not None
        return self.vector_value("reference_vector") is not None

    def handle_command_option(self, label: str) -> bool:
        if self.active_export != "reference_vector":
            return False
        if label == "Enter factor":
            self._commit_mode = "factor"
            self.factor = None
            self.editor.stateful_value_changed.emit("factor", None)
            self.active_export = "factor"
            self._emit_state_sync()
            return True
        return False

    def commit(self) -> None:
        base = self.point_value("base_point")
        if base is None:
            self.editor.status_message.emit("Scale: base point is required")
            return

        if self._commit_mode == "factor":
            factor = self.number_value("factor")
        else:
            vector = self.vector_value("reference_vector")
            raw = math.hypot(vector.x, vector.y) if vector is not None else 0.0
            factor = raw / 100.0 if raw > 1e-6 else raw

        if factor is None or abs(factor) < 1e-9:
            self.editor.status_message.emit("Scale: factor too small, cancelled")
            return

        cx, cy = base.x, base.y
        _commit_transform(
            self.editor,
            self._entities,
            lambda v, _cx=cx, _cy=cy, _factor=factor: _scale_pt(v, _cx, _cy, _factor),
            lambda e, orig, _factor=factor: _post_scale_radius(e, orig, _factor),
            "Scale",
        )
