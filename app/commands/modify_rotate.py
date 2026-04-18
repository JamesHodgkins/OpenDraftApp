"""Modify — Rotate command."""
from __future__ import annotations

import math
from typing import List

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import BaseEntity, Vec2
from app.commands.modify_helpers import (
    _collect_selected, _transform_entity,
    _rotate_pt,
    _post_rotate_arc, _commit_transform,
)


@command("rotateCommand")
class RotateCommand(CommandBase):
    """Rotate selected entities around a center point by an input angle."""

    def execute(self) -> None:
        entities = _collect_selected(self.editor)
        if not entities:
            self.editor.status_message.emit("Rotate: select entities first, then run Rotate")
            return

        center = self.editor.get_point("Rotate: pick rotation center")
        cx, cy = center.x, center.y

        def _preview(mouse: Vec2) -> List[BaseEntity]:
            angle = math.atan2(mouse.y - center.y, mouse.x - center.x)
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            def pt_fn(v): return _rotate_pt(v, cx, cy, cos_a, sin_a)
            def post_fn(e, orig): return _post_rotate_arc(e, orig, angle)
            transformed_entities = [_transform_entity(ent, pt_fn, post_fn) for ent in entities]
            return transformed_entities

        self.editor.set_dynamic(_preview)
        angle_deg = self.editor.get_angle(
            "Rotate: pick a point or enter angle (degrees)", center=center)
        self.editor.clear_dynamic()

        angle = math.radians(angle_deg)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        def pt_fn(v): return _rotate_pt(v, cx, cy, cos_a, sin_a)
        def post_fn(e, orig): return _post_rotate_arc(e, orig, angle)
        _commit_transform(self.editor, entities, pt_fn, post_fn, "Rotate")

