"""Modify — Extend command."""
from __future__ import annotations

import math
from typing import List, Optional

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import (
    BaseEntity, Vec2,
    LineEntity, CircleEntity, ArcEntity, RectangleEntity,
)
from app.commands.modify_helpers import _copy_style, _ReplaceEntitiesUndoCommand
from app.geometry import (
    _geo_angle_on_arc,
    _geo_pt_seg_dist,
    _line_circle_params,
    _circle_circle_angles,
)


@command("extendCommand")
class ExtendCommand(CommandBase):
    """Extend line/arc endpoints to a selected boundary edge.

    Workflow:
    1. Pick the boundary entity (edge to extend to).
    2. Click near the endpoint of an entity to extend it to the boundary.
    3. Repeat until Escape.
    """

    def execute(self) -> None:
        self.editor.suppress_osnap = True
        self.editor.suppress_dynamic_input = True
        try:
            self._run()
        finally:
            self.editor.suppress_osnap = False
            self.editor.suppress_dynamic_input = False
            self.editor.clear_dynamic()
            self.editor.clear_highlight()

    def _run(self) -> None:
        doc = self.editor.document
        sel_ids = self.editor.selection.ids

        if sel_ids:
            boundaries = [e for e in doc.entities if e.id in sel_ids]
            self.editor.set_highlight(boundaries)
            self.editor.status_message.emit(
                f"Extend: {len(boundaries)} boundary edge(s) from selection (highlighted). "
                "Click near an endpoint to extend (Escape to exit)")
        else:
            # No preselection — all entities act as boundaries (no highlight).
            boundaries = list(doc.entities)
            self.editor.status_message.emit(
                "Extend: click near the endpoint to extend (Escape to exit)")

        tol = self.editor.settings.extend_target_tolerance
        boundary_ids: Optional[set] = {e.id for e in boundaries} if sel_ids else None

        def _get_boundaries(ents: List[BaseEntity]) -> List[BaseEntity]:
            if boundary_ids is None:
                return ents
            return [e for e in ents if e.id in boundary_ids]

        def _preview(mouse: Vec2) -> List[BaseEntity]:
            ents = list(self.editor.document.entities)
            bds = _get_boundaries(ents)
            target = _pick_entity(mouse, ents, tolerance=tol)
            if target is None or (boundary_ids is not None and target.id in boundary_ids):
                return []
            for boundary in bds:
                result = _extend_entity(target, mouse, boundary, ents)
                if result is not None:
                    return [result]
            return []

        self.editor.set_dynamic(_preview)

        while True:
            pick_pt = self.editor.get_point(
                "Extend: click near the endpoint to extend (Escape to exit)")

            entities = list(doc.entities)
            bds = _get_boundaries(entities)
            target = _pick_entity(pick_pt, entities, tolerance=tol)
            if target is None or (boundary_ids is not None and target.id in boundary_ids):
                self.editor.status_message.emit("Extend: no entity at pick point")
                continue

            result = None
            for boundary in bds:
                result = _extend_entity(target, pick_pt, boundary, entities)
                if result is not None:
                    break

            if result is None:
                self.editor.status_message.emit(
                    "Extend: no intersection found with the boundary")
                continue

            orig_idx = next(
                (i for i, e in enumerate(doc.entities) if e.id == target.id), 0)

            doc.remove_entity(target.id)
            self.editor.entity_removed.emit(target.id)
            doc.add_entity(result)
            self.editor.entity_added.emit(result)
            self.editor.push_undo_command(
                _ReplaceEntitiesUndoCommand(
                    doc, [target], [orig_idx], [result], "Extend"))
            self.editor.notify_document()


def _pick_entity(pt: Vec2, entities: List[BaseEntity],
                 tolerance: float) -> Optional[BaseEntity]:
    best: Optional[BaseEntity] = None
    best_dist = float("inf")
    for ent in entities:
        if not ent.hit_test(pt, tolerance):
            continue
        d = _entity_approx_dist(ent, pt)
        if d < best_dist:
            best_dist = d
            best = ent
    return best


def _entity_approx_dist(ent: BaseEntity, pt: Vec2) -> float:
    if isinstance(ent, LineEntity):
        return _geo_pt_seg_dist(pt, ent.p1, ent.p2)
    if isinstance(ent, (CircleEntity, ArcEntity)):
        return abs(math.hypot(pt.x - ent.center.x, pt.y - ent.center.y) - ent.radius)
    bb = ent.bounding_box()
    if bb:
        return math.hypot(pt.x - (bb.min_x + bb.max_x) / 2,
                          pt.y - (bb.min_y + bb.max_y) / 2)
    return float("inf")


def _line_line_intersect(p1: Vec2, p2: Vec2, p3: Vec2, p4: Vec2) -> Optional[Vec2]:
    dx1, dy1 = p2.x - p1.x, p2.y - p1.y
    dx2, dy2 = p4.x - p3.x, p4.y - p3.y
    denom = dx1 * dy2 - dy1 * dx2
    if abs(denom) < 1e-12:
        return None
    t = ((p3.x - p1.x) * dy2 - (p3.y - p1.y) * dx2) / denom
    return Vec2(p1.x + t * dx1, p1.y + t * dy1)


def _line_circle_intersect_pts(p1: Vec2, p2: Vec2,
                                center: Vec2, radius: float) -> List[Vec2]:
    dx, dy = p2.x - p1.x, p2.y - p1.y
    fx, fy = p1.x - center.x, p1.y - center.y
    a = dx * dx + dy * dy
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    disc = b * b - 4 * a * c
    if a < 1e-12 or disc < 0:
        return []
    sqrt_d = math.sqrt(max(0.0, disc))
    pts = []
    for sign in (-1, 1):
        t = (-b + sign * sqrt_d) / (2 * a)
        pts.append(Vec2(p1.x + t * dx, p1.y + t * dy))
    return pts


def _extend_entity(target: BaseEntity, pick_pt: Vec2,
                   boundary: BaseEntity,
                   all_entities: List[BaseEntity]) -> Optional[BaseEntity]:
    style = _copy_style(target)

    if isinstance(target, LineEntity):
        d1 = math.hypot(pick_pt.x - target.p1.x, pick_pt.y - target.p1.y)
        d2 = math.hypot(pick_pt.x - target.p2.x, pick_pt.y - target.p2.y)
        moving_start = d1 < d2

        ip = _intersect_with_boundary(target.p1, target.p2, boundary)
        if ip is None:
            return None

        if moving_start:
            return LineEntity(p1=ip, p2=target.p2, **style)
        else:
            return LineEntity(p1=target.p1, p2=ip, **style)

    if isinstance(target, ArcEntity):
        cx, cy, r = target.center.x, target.center.y, target.radius
        ep_start = Vec2(cx + r * math.cos(target.start_angle),
                        cy + r * math.sin(target.start_angle))
        ep_end   = Vec2(cx + r * math.cos(target.end_angle),
                        cy + r * math.sin(target.end_angle))
        d_start = math.hypot(pick_pt.x - ep_start.x, pick_pt.y - ep_start.y)
        d_end   = math.hypot(pick_pt.x - ep_end.x,   pick_pt.y - ep_end.y)
        moving_start = d_start < d_end

        angles = _arc_boundary_angles(target, boundary)
        if not angles:
            return None

        if moving_start:
            best = min(angles, key=lambda a: abs(
                (a - target.start_angle + math.pi) % (2 * math.pi) - math.pi))
            return ArcEntity(center=target.center, radius=r,
                             start_angle=best, end_angle=target.end_angle,
                             ccw=target.ccw, **style)
        else:
            best = min(angles, key=lambda a: abs(
                (a - target.end_angle + math.pi) % (2 * math.pi) - math.pi))
            return ArcEntity(center=target.center, radius=r,
                             start_angle=target.start_angle, end_angle=best,
                             ccw=target.ccw, **style)

    return None


def _intersect_with_boundary(p1: Vec2, p2: Vec2,
                              boundary: BaseEntity) -> Optional[Vec2]:
    if isinstance(boundary, LineEntity):
        return _line_line_intersect(p1, p2, boundary.p1, boundary.p2)
    if isinstance(boundary, (CircleEntity, ArcEntity)):
        pts = _line_circle_intersect_pts(p1, p2, boundary.center, boundary.radius)
        if not pts:
            return None
        if isinstance(boundary, ArcEntity):
            pts = [pt for pt in pts
                   if _geo_angle_on_arc(
                       math.atan2(pt.y - boundary.center.y, pt.x - boundary.center.x),
                       boundary.start_angle, boundary.end_angle, boundary.ccw)]
        if not pts:
            return None
        return min(pts, key=lambda pt: math.hypot(pt.x - p2.x, pt.y - p2.y))
    if isinstance(boundary, RectangleEntity):
        best: Optional[Vec2] = None
        best_d = float("inf")
        for a, b in boundary._edges():
            pt = _line_line_intersect(p1, p2, a, b)
            if pt is None:
                continue
            d = math.hypot(pt.x - p2.x, pt.y - p2.y)
            if d < best_d:
                best_d = d
                best = pt
        return best
    return None


def _arc_boundary_angles(arc: ArcEntity, boundary: BaseEntity) -> List[float]:
    angles: List[float] = []
    cx, cy, r = arc.center.x, arc.center.y, arc.radius
    center = arc.center

    if isinstance(boundary, LineEntity):
        ts = _line_circle_params(boundary.p1, boundary.p2, center, r)
        for t in ts:
            px = boundary.p1.x + t * (boundary.p2.x - boundary.p1.x)
            py = boundary.p1.y + t * (boundary.p2.y - boundary.p1.y)
            angles.append(math.atan2(py - cy, px - cx))
    elif isinstance(boundary, (CircleEntity, ArcEntity)):
        raw = _circle_circle_angles(center, r, boundary.center, boundary.radius)
        for angle in raw:
            if isinstance(boundary, ArcEntity):
                ix = cx + r * math.cos(angle)
                iy = cy + r * math.sin(angle)
                oa = math.atan2(iy - boundary.center.y, ix - boundary.center.x)
                if not _geo_angle_on_arc(oa, boundary.start_angle,
                                         boundary.end_angle, boundary.ccw):
                    continue
            angles.append(angle)
    return angles
