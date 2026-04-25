"""Modify — Rotate command."""
from __future__ import annotations

import math
from typing import List

from app.editor import command
from app.editor.base_command import CommandBase
from app.editor.editor import CommandOptionSelection
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
        self.editor.snap_from_point = center
        cx, cy = center.x, center.y

        base_vec: Vec2 | None = None
        dest_vec: Vec2 | None = None

        def _angle_from_vectors(a: Vec2, b: Vec2) -> float:
            """Signed angle (radians) from vector a to vector b."""
            return math.atan2(b.y, b.x) - math.atan2(a.y, a.x)

        def _is_zero_vector(v: Vec2) -> bool:
            return abs(v.x) < 1e-9 and abs(v.y) < 1e-9

        def _angle_from_center_vector(v: Vec2) -> float:
            """Rotation angle derived from center->cursor vector.

            If a base vector has been set, treat that as the zero-angle axis.
            """
            if base_vec is not None and not _is_zero_vector(v):
                return _angle_from_vectors(base_vec, v)
            return math.atan2(v.y, v.x)

        def _preview(mouse: Vec2) -> List[BaseEntity]:
            vec = mouse - center
            angle = _angle_from_center_vector(vec)
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            def pt_fn(v): return _rotate_pt(v, cx, cy, cos_a, sin_a)
            def post_fn(e, orig): return _post_rotate_arc(e, orig, angle)
            transformed_entities = [_transform_entity(ent, pt_fn, post_fn) for ent in entities]
            return transformed_entities

        angle: float | None = None
        while angle is None:
            has_base_reference = base_vec is not None
            enter_angle_label = (
                "Enter angle (relative to base vector)"
                if has_base_reference
                else "Enter angle"
            )
            rotation_prompt = (
                "Rotate: specify rotation vector (relative to base vector) or choose option"
                if has_base_reference
                else "Rotate: specify rotation vector or choose option"
            )
            self.editor.set_command_options([
                enter_angle_label,
                "Set base vector",
                "Set destination vector",
            ])
            try:
                with self.editor.preview(_preview):
                    result = self.editor.get_point(
                        rotation_prompt,
                        allow_command_options=True,
                    )
            finally:
                self.editor.clear_command_options()

            if not isinstance(result, CommandOptionSelection):
                vec = result - center
                angle = _angle_from_center_vector(vec)
                break

            choice = result.label

            if choice in {
                "Enter angle",
                "Enter angle (relative to base vector)",
            }:
                angle_prompt = (
                    "Rotate: enter angle (degrees, relative to base vector)"
                    if has_base_reference
                    else "Rotate: enter angle (degrees)"
                )
                angle_deg = self.editor.get_float(angle_prompt)
                angle = math.radians(angle_deg)
                self.editor.snap_from_point = center
                continue

            if choice == "Set base vector":
                a = self.editor.get_point("Rotate: base vector start point")
                self.editor.snap_from_point = a
                b = self.editor.get_point("Rotate: specify base vector")
                base_vec = b - a
                if _is_zero_vector(base_vec):
                    base_vec = None
                    self.editor.status_message.emit("Rotate: base vector cannot be zero length")
                self.editor.snap_from_point = center
                continue

            if choice == "Set destination vector":
                a = self.editor.get_point("Rotate: destination vector start point")
                self.editor.snap_from_point = a
                b = self.editor.get_point("Rotate: specify destination vector")
                dest_vec = b - a
                if _is_zero_vector(dest_vec):
                    dest_vec = None
                    self.editor.status_message.emit("Rotate: destination vector cannot be zero length")
                    self.editor.snap_from_point = center
                    continue
                if base_vec is not None:
                    angle = _angle_from_vectors(base_vec, dest_vec)
                else:
                    self.editor.status_message.emit("Rotate: set base vector first")
                self.editor.snap_from_point = center
                continue

        assert angle is not None
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        def pt_fn(v): return _rotate_pt(v, cx, cy, cos_a, sin_a)
        def post_fn(e, orig): return _post_rotate_arc(e, orig, angle)
        _commit_transform(self.editor, entities, pt_fn, post_fn, "Rotate")

