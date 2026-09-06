"""Modify — Offset command."""
from __future__ import annotations

import copy
import math
import uuid
from typing import List

from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import BaseEntity, Vec2
from app.entities import LineEntity, CircleEntity, ArcEntity, PolylineEntity
from app.commands.modify_helpers import (
    _collect_selected, _ReplaceEntitiesUndoCommand,
)

_MODE_BOTH = "both"
_MODE_PICK_SIDE = "pick side"


def _normalize_mode(value: str | None) -> str:
    token = (value or "").strip().lower()
    if token in {"b", _MODE_BOTH}:
        return _MODE_BOTH
    if token in {"p", "pick", "side", _MODE_PICK_SIDE}:
        return _MODE_PICK_SIDE
    return token


def _offset_line(ent: LineEntity, distance: float) -> List[BaseEntity]:
    """Return two offset copies of a line (one each side) when distance < 0, or one."""
    dx = ent.p2.x - ent.p1.x
    dy = ent.p2.y - ent.p1.y
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return []
    nx = -dy / length
    ny = dx / length

    def _make(d: float) -> LineEntity:
        e = copy.deepcopy(ent)
        e.id = str(uuid.uuid4())
        e.p1 = Vec2(ent.p1.x + nx * d, ent.p1.y + ny * d)
        e.p2 = Vec2(ent.p2.x + nx * d, ent.p2.y + ny * d)
        return e

    return [_make(distance)]


def _offset_circle(ent: CircleEntity, distance: float) -> List[BaseEntity]:
    new_r = ent.radius + distance
    if new_r <= 0:
        return []
    e = copy.deepcopy(ent)
    e.id = str(uuid.uuid4())
    e.radius = new_r
    return [e]


def _offset_arc(ent: ArcEntity, distance: float) -> List[BaseEntity]:
    new_r = ent.radius + distance
    if new_r <= 0:
        return []
    e = copy.deepcopy(ent)
    e.id = str(uuid.uuid4())
    e.radius = new_r
    return [e]


def _offset_polyline(ent: PolylineEntity, distance: float) -> List[BaseEntity]:
    pts = ent.points
    if len(pts) < 2:
        return []

    # Compute per-segment normals
    normals = []
    segment_count = len(pts) if ent.closed else len(pts) - 1
    for i in range(segment_count):
        p1 = pts[i]
        p2 = pts[(i + 1) % len(pts)]
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        length = math.hypot(dx, dy)
        if length < 1e-12:
            normals.append((0.0, 0.0))
        else:
            normals.append((-dy / length, dx / length))

    # Offset each vertex by averaging adjacent segment normals
    new_pts: List[Vec2] = []
    for i, pt in enumerate(pts):
        if ent.closed:
            n1 = normals[i - 1]
            n2 = normals[i]
            nx = (n1[0] + n2[0]) / 2
            ny = (n1[1] + n2[1]) / 2
            mag = math.hypot(nx, ny)
            if mag > 1e-12:
                dot = n1[0] * n2[0] + n1[1] * n2[1]
                miter = 1.0 / max(0.01, (1.0 + dot) / 2) ** 0.5
                nx = nx / mag * miter
                ny = ny / mag * miter
        elif i == 0:
            nx, ny = normals[0]
        elif i == len(pts) - 1:
            nx, ny = normals[-1]
        else:
            n1 = normals[i - 1]
            n2 = normals[i]
            nx = (n1[0] + n2[0]) / 2
            ny = (n1[1] + n2[1]) / 2
            mag = math.hypot(nx, ny)
            if mag > 1e-12:
                # Miter correction so offset distance stays consistent
                dot = n1[0] * n2[0] + n1[1] * n2[1]
                miter = 1.0 / max(0.01, (1.0 + dot) / 2) ** 0.5
                nx = nx / mag * miter
                ny = ny / mag * miter
        new_pts.append(Vec2(pt.x + nx * distance, pt.y + ny * distance))

    e = copy.deepcopy(ent)
    e.id = str(uuid.uuid4())
    e.points = new_pts
    return [e]


def _offset_entity(ent: BaseEntity, distance: float) -> List[BaseEntity]:
    if isinstance(ent, LineEntity):
        return _offset_line(ent, distance)
    if isinstance(ent, CircleEntity):
        return _offset_circle(ent, distance)
    if isinstance(ent, ArcEntity):
        return _offset_arc(ent, distance)
    if isinstance(ent, PolylineEntity):
        return _offset_polyline(ent, distance)
    return []


def _signed_side(ent: BaseEntity, pt: Vec2) -> float:
    """Return a positive value if *pt* is on the 'positive normal' side of *ent*,
    negative otherwise. Used to determine offset direction from a picked point."""
    if isinstance(ent, LineEntity):
        dx = ent.p2.x - ent.p1.x
        dy = ent.p2.y - ent.p1.y
        # Cross product of line direction with (pt - p1)
        return dx * (pt.y - ent.p1.y) - dy * (pt.x - ent.p1.x)
    if isinstance(ent, (CircleEntity, ArcEntity)):
        # Positive = outside (farther than radius), negative = inside
        d = math.hypot(pt.x - ent.center.x, pt.y - ent.center.y)
        return d - ent.radius
    if isinstance(ent, PolylineEntity):
        # Use the first segment's normal
        pts = ent.points
        if len(pts) < 2:
            return 0.0
        dx = pts[1].x - pts[0].x
        dy = pts[1].y - pts[0].y
        return dx * (pt.y - pts[0].y) - dy * (pt.x - pts[0].x)
    return 0.0


def _distance_to_entity(ent: BaseEntity, pt: Vec2) -> float | None:
    nearest_snap = getattr(ent, "nearest_snap", None)
    if not callable(nearest_snap):
        return None
    snap = nearest_snap(pt)
    position = getattr(snap, "point", None)
    if not isinstance(position, Vec2):
        return None
    return math.hypot(pt.x - position.x, pt.y - position.y)


@command("offsetCommand")
class OffsetCommand(StatefulCommandBase):
    """Offset selected entities by a given distance."""

    distance = export(None, label="Distance", input_kind="length")
    mode = export(None, label="Mode", input_kind="choice")
    side_point = export(None, label="Side point", input_kind="point")

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._supported: list[BaseEntity] = []

    def start(self) -> bool | None:
        entities = _collect_selected(self.editor)
        self._supported = [
            entity
            for entity in entities
            if isinstance(entity, (LineEntity, CircleEntity, ArcEntity, PolylineEntity))
        ]
        if not self._supported:
            self.editor.status_message.emit(
                "Offset: select lines, arcs, circles or polylines first, then run Offset"
            )
            return False
        self.editor.suppress_osnap = True
        self.begin(active_export="distance", reset=("distance", "mode", "side_point"))
        return None

    def handle_choice_click(self, name: str, pt: Vec2) -> bool:
        """Let a viewport click on the "both/pick side" step mean "this side".

        Distance can be set by clicking (KNOWN_BUGS-style measured-distance
        support, see ``value_from_point``), so a user naturally expects the
        very next click to finish the command by indicating a side — not to
        be silently ignored while the command waits for a typed "B"/"P".
        Clicking here is unambiguous: only "pick side" needs a location at
        all, so treat the click as choosing that mode *and* supplying this
        point as ``side_point`` in one gesture.
        """
        if name != "mode":
            return False
        self.editor._stateful_set_and_advance(self, "mode", _MODE_PICK_SIDE)
        self.editor._stateful_set_and_advance(self, "side_point", pt)
        return True

    def value_from_point(self, name: str, pt: Vec2):
        if name != "distance":
            return None
        measured = self._measure_distance(pt)
        return measured if measured is not None and measured >= 1e-9 else None

    def _measure_distance(self, pt: Vec2) -> float | None:
        distances = [
            distance
            for entity in self._supported
            if (distance := _distance_to_entity(entity, pt)) is not None
        ]
        return min(distances) if distances else None

    def reject_point(self, name: str, pt: Vec2) -> bool:
        if name != "distance":
            return False
        measured = self._measure_distance(pt)
        if measured is not None and measured < 1e-9:
            # A click landing on (or a hair from) the geometry itself measures
            # a ~0 distance. Silently accepting that used to leave the command
            # stuck forever: `all_exports_set()` requires `distance > 0`, so
            # auto-commit would never fire and no status message ever
            # explained why nothing happened no matter which side was picked
            # afterwards. Veto the click outright — falling through to the
            # generic "length" handling would silently substitute a bogus
            # distance-from-origin instead.
            self.editor.status_message.emit(
                "Offset: click farther from the selected geometry to set a distance"
            )
            return True
        return False

    def advance_active_export(self) -> None:
        if self.active_export == "distance" and self.number_value("distance") is not None:
            self.active_export = "mode"
            return
        if self.active_export == "mode":
            mode = _normalize_mode(self.string_value("mode"))
            self.active_export = "" if mode == _MODE_BOTH else "side_point"
            return
        if self.active_export == "side_point" and self.point_value("side_point") is not None:
            self.active_export = ""

    def all_exports_set(self) -> bool:
        distance = self.number_value("distance")
        mode = _normalize_mode(self.string_value("mode"))
        if distance is None or distance <= 0 or self.active_export:
            return False
        if mode == _MODE_BOTH:
            return True
        if mode == _MODE_PICK_SIDE:
            return self.point_value("side_point") is not None
        return False

    def update(self) -> None:
        self.editor._choice_options = ["B", "P"] if self.active_export == "mode" else []

        distance = self.number_value("distance")
        if self.active_export == "side_point" and distance is not None and distance > 0:
            def _preview(mouse: Vec2) -> list[BaseEntity]:
                preview_entities: list[BaseEntity] = []
                for entity in self._supported:
                    sign = 1.0 if _signed_side(entity, mouse) >= 0 else -1.0
                    preview_entities.extend(_offset_entity(entity, sign * distance))
                return preview_entities

            self.editor.set_dynamic(_preview)
            return

        self.editor.clear_dynamic()

    def commit(self) -> bool | None:
        distance = self.number_value("distance")
        mode = _normalize_mode(self.string_value("mode"))
        side_pt = self.point_value("side_point")
        if distance is None or distance <= 0:
            self.editor.status_message.emit("Offset: distance must be positive")
            return False
        if mode not in {_MODE_BOTH, _MODE_PICK_SIDE}:
            self.editor.status_message.emit("Offset: choose both sides or pick side")
            return False
        if mode == _MODE_PICK_SIDE and side_pt is None:
            self.editor.status_message.emit("Offset: click to indicate which side")
            return False

        doc = self.editor.document
        added: list[BaseEntity] = []
        for entity in self._supported:
            if mode == _MODE_BOTH:
                distances = [distance, -distance]
            else:
                assert side_pt is not None
                sign = 1.0 if _signed_side(entity, side_pt) >= 0 else -1.0
                distances = [sign * distance]

            for amount in distances:
                for new_entity in _offset_entity(entity, amount):
                    doc.add_entity(new_entity)
                    self.editor.entity_added.emit(new_entity)
                    added.append(new_entity)

        if not added:
            self.editor.status_message.emit("Offset: no valid results (distance too large?)")
            return False

        self.editor.push_undo_command(
            _ReplaceEntitiesUndoCommand(doc, [], [], added, "Offset")
        )
        self.editor.notify_document()
