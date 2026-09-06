"""Modify — Rotate command."""
from __future__ import annotations

import math

from app.editor import command
from app.editor.editor import CommandOption
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import BaseEntity, Vec2
from app.commands.modify_helpers import (
    _collect_selected, _transform_entity,
    _rotate_pt,
    _post_rotate_arc, _commit_transform,
)


@command("rotateCommand")
class RotateCommand(StatefulCommandBase):
    """Rotate selected entities around a center point by an input angle."""

    center = export(None, label="Center", input_kind="point")
    rotation_vector = export(None, label="Angle", input_kind="angle")
    base_start = export(None, label="Base vector start", input_kind="point")
    base_end = export(None, label="Base vector end", input_kind="point")
    destination_start = export(None, label="Destination vector start", input_kind="point")
    destination_end = export(None, label="Destination vector end", input_kind="point")

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._entities: list[BaseEntity] = []
        self._commit_mode: str = "angle"

    def start(self) -> bool | None:
        self._entities = _collect_selected(self.editor)
        if not self._entities:
            self.editor.status_message.emit("Rotate: select entities first, then run Rotate")
            return False
        self._commit_mode = "angle"
        self.begin(
            active_export="center",
            reset=(
                "center",
                "rotation_vector",
                "base_start",
                "base_end",
                "destination_start",
                "destination_end",
            ),
        )
        return None

    def live_preview_value(self, name, cursor):
        if name == "rotation_vector":
            center = self.point_value("center")
            if center is None:
                return None
            return math.degrees(self._angle_from_center_vector(cursor - center))
        return super().live_preview_value(name, cursor)

    def _emit_state_sync(self) -> None:
        self.editor._set_stateful_input_mode(self)
        self.editor.stateful_active_export_changed.emit(self.active_export)
        self.editor._emit_stateful_prompt(self)

    def _base_vector(self) -> Vec2 | None:
        start = self.point_value("base_start")
        end = self.point_value("base_end")
        if start is None or end is None:
            return None
        vec = end - start
        return None if self._is_zero_vector(vec) else vec

    def _destination_vector(self) -> Vec2 | None:
        start = self.point_value("destination_start")
        end = self.point_value("destination_end")
        if start is None or end is None:
            return None
        vec = end - start
        return None if self._is_zero_vector(vec) else vec

    @staticmethod
    def _angle_from_vectors(a: Vec2, b: Vec2) -> float:
        return math.atan2(b.y, b.x) - math.atan2(a.y, a.x)

    @staticmethod
    def _is_zero_vector(v: Vec2) -> bool:
        return abs(v.x) < 1e-9 and abs(v.y) < 1e-9

    def _angle_from_center_vector(self, v: Vec2) -> float:
        base_vec = self._base_vector()
        if base_vec is not None and not self._is_zero_vector(v):
            return self._angle_from_vectors(base_vec, v)
        return math.atan2(v.y, v.x)

    def _preview_angle(self, mouse: Vec2) -> float | None:
        center = self.point_value("center")
        if center is None:
            return None
        if self.active_export == "rotation_vector":
            angle_deg = self.number_value("rotation_vector")
            if angle_deg is not None:
                return math.radians(angle_deg)
            return math.atan2((mouse - center).y, (mouse - center).x)
        if self.active_export == "destination_end":
            dest_start = self.point_value("destination_start")
            base_vec = self._base_vector()
            if dest_start is not None and base_vec is not None:
                dest_vec = mouse - dest_start
                if not self._is_zero_vector(dest_vec):
                    return self._angle_from_vectors(base_vec, dest_vec)
        return None

    def update(self) -> None:
        center = self.point_value("center")
        base_start = self.point_value("base_start")
        destination_start = self.point_value("destination_start")

        if self.active_export == "rotation_vector":
            self.editor.set_command_options_keyed(
                [
                    CommandOption(key="b", label="Set base vector"),
                    CommandOption(key="d", label="Set destination vector"),
                ]
            )
        else:
            self.editor.clear_command_options()

        self.set_snap_for_active(
            {
                "rotation_vector": center,
                "base_end": base_start,
                "destination_end": destination_start,
            },
            default=center,
        )

        if center is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2) -> list[BaseEntity]:
            angle = self._preview_angle(mouse)
            if angle is None:
                return []
            cx, cy = center.x, center.y
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            return [
                _transform_entity(
                    entity,
                    lambda v, _cx=cx, _cy=cy, _cos=cos_a, _sin=sin_a: _rotate_pt(
                        v, _cx, _cy, _cos, _sin
                    ),
                    lambda e, orig, _angle=angle: _post_rotate_arc(e, orig, _angle),
                )
                for entity in self._entities
            ]

        self.editor.set_dynamic(_preview)

    def advance_active_export(self) -> None:
        if self.active_export == "center" and self.point_value("center") is not None:
            self._commit_mode = "angle"
            self.active_export = "rotation_vector"
            return
        if self.active_export == "base_start" and self.point_value("base_start") is not None:
            self.active_export = "base_end"
            return
        if self.active_export == "base_end" and self.point_value("base_end") is not None:
            vec = self._base_vector()
            if vec is None:
                self.base_start = None
                self.base_end = None
                self.editor.stateful_value_changed.emit("base_start", None)
                self.editor.stateful_value_changed.emit("base_end", None)
                self.editor.status_message.emit("Rotate: base vector cannot be zero length")
                self.active_export = "base_start"
                return
            self._commit_mode = "angle"
            self.active_export = "rotation_vector"
            return
        if self.active_export == "destination_start" and self.point_value("destination_start") is not None:
            self.active_export = "destination_end"
            return
        if self.active_export == "destination_end" and self.point_value("destination_end") is not None:
            vec = self._destination_vector()
            if vec is None:
                self.destination_start = None
                self.destination_end = None
                self.editor.stateful_value_changed.emit("destination_start", None)
                self.editor.stateful_value_changed.emit("destination_end", None)
                self.editor.status_message.emit("Rotate: destination vector cannot be zero length")
                self.active_export = "destination_start"
                return
            self.active_export = ""
            return
        if self.active_export == "rotation_vector":
            self.active_export = ""

    def all_exports_set(self) -> bool:
        if self.point_value("center") is None or self.active_export:
            return False
        if self._commit_mode == "dest":
            return self._base_vector() is not None and self._destination_vector() is not None
        return self.number_value("rotation_vector") is not None

    def handle_command_option(self, label: str) -> bool:
        if self.active_export != "rotation_vector":
            return False
        if label == "Set base vector":
            self.base_start = None
            self.base_end = None
            self.destination_start = None
            self.destination_end = None
            self.editor.stateful_value_changed.emit("base_start", None)
            self.editor.stateful_value_changed.emit("base_end", None)
            self.editor.stateful_value_changed.emit("destination_start", None)
            self.editor.stateful_value_changed.emit("destination_end", None)
            self.active_export = "base_start"
            self._emit_state_sync()
            return True
        if label == "Set destination vector":
            if self._base_vector() is None:
                self.editor.status_message.emit("Rotate: set base vector first")
                return True
            self._commit_mode = "dest"
            self.destination_start = None
            self.destination_end = None
            self.editor.stateful_value_changed.emit("destination_start", None)
            self.editor.stateful_value_changed.emit("destination_end", None)
            self.active_export = "destination_start"
            self._emit_state_sync()
            return True
        return False

    def commit(self) -> None:
        center = self.point_value("center")
        if center is None:
            self.editor.status_message.emit("Rotate: center is required")
            return
        angle: float | None = None
        if self._commit_mode == "dest":
            base_vec = self._base_vector()
            dest_vec = self._destination_vector()
            if base_vec is not None and dest_vec is not None:
                angle = self._angle_from_vectors(base_vec, dest_vec)
        else:
            value = self.number_value("rotation_vector")
            if value is not None:
                base_vec = self._base_vector()
                if base_vec is not None:
                    base_angle_deg = math.degrees(math.atan2(base_vec.y, base_vec.x))
                    angle = math.radians(value - base_angle_deg)
                else:
                    angle = math.radians(value)

        if angle is None:
            self.editor.status_message.emit("Rotate: rotation input is incomplete")
            return

        cx, cy = center.x, center.y
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        _commit_transform(
            self.editor,
            self._entities,
            lambda v, _cx=cx, _cy=cy, _cos=cos_a, _sin=sin_a: _rotate_pt(
                v, _cx, _cy, _cos, _sin
            ),
            lambda e, orig, _angle=angle: _post_rotate_arc(e, orig, _angle),
            "Rotate",
        )

