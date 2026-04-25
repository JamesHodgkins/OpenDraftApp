"""Modify — Scale command."""
from __future__ import annotations

import math
from typing import List

from app.editor import command
from app.editor.base_command import CommandBase
from app.editor.editor import CommandOptionSelection
from app.entities import BaseEntity, Vec2
from app.commands.modify_helpers import (
    _collect_selected, _transform_entity, _scale_pt,
    _post_scale_radius, _commit_transform,
)


@command("scaleCommand")
class ScaleCommand(CommandBase):
    """Scale selected entities about a base point by a numeric factor."""

    def execute(self) -> None:
        entities = _collect_selected(self.editor)
        if not entities:
            self.editor.status_message.emit("Scale: select entities first, then run Scale")
            return

        base = self.editor.get_point("Scale: pick base point")
        self.editor.snap_from_point = base
        cx, cy = base.x, base.y

        def _preview(mouse: Vec2) -> List[BaseEntity]:
            ref_dist = math.hypot(mouse.x - base.x, mouse.y - base.y)
            factor = ref_dist / 100.0 if ref_dist > 1e-6 else 1.0
            def pt_fn(v): return _scale_pt(v, cx, cy, factor)
            def post_fn(e, orig): return _post_scale_radius(e, orig, factor)
            return [_transform_entity(ent, pt_fn, post_fn) for ent in entities]

        factor: float | None = None
        while factor is None:
            self.editor.set_command_options(["Enter factor"])
            try:
                with self.editor.preview(_preview):
                    result = self.editor.get_point(
                        "Scale: specify reference vector or choose option",
                        allow_command_options=True,
                    )
            finally:
                self.editor.clear_command_options()

            if isinstance(result, CommandOptionSelection):
                if result.label == "Enter factor":
                    factor = self.editor.get_float("Scale: enter scale factor")
                continue

            raw = math.hypot(result.x - base.x, result.y - base.y)
            factor = raw / 100.0 if raw > 1e-6 else raw

        assert factor is not None

        if abs(factor) < 1e-9:
            self.editor.status_message.emit("Scale: factor too small, cancelled")
            return

        def pt_fn(v): return _scale_pt(v, cx, cy, factor)
        def post_fn(e, orig): return _post_scale_radius(e, orig, factor)
        _commit_transform(self.editor, entities, pt_fn, post_fn, "Scale")
