"""Trim command — trims entities at their intersections with other geometry.

Workflow (AutoCAD-style "quick trim"):
1.  All visible entities in the document act as potential cutting edges.
2.  The user clicks on the portion of an entity to **remove**.
3.  The picked segment (between the two nearest intersection points, or
    between one end and an intersection) is deleted; any surviving parts
    replace the original as new entities.
4.  Repeat until the user presses Escape.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from app.editor import command
from app.editor.base_command import CommandBase
from app.editor.undo import UndoCommand
from app.entities import BaseEntity, Vec2, LineEntity, ArcEntity, CircleEntity
from app.entities.rectangle import RectangleEntity
from app.entities.ellipse import EllipseEntity
from app.commands.modify_helpers import _copy_style
from app.geometry import (
    _geo_angle_on_arc,
    _geo_pt_seg_dist,
    _normalize_angle,
    _arc_span,
    _arc_parameter,
    _arc_angle_at_param,
    _seg_seg_param,
    _line_circle_params,
    _circle_circle_angles,
    _lerp,
)


# ---------------------------------------------------------------------------
# Undo command for a single trim operation
# ---------------------------------------------------------------------------

class _TrimUndoCommand(UndoCommand):
    """Undoable replacement of one entity with zero-or-more new entities."""

    def __init__(self, document, original, original_index: int,
                 replacements: List[BaseEntity]) -> None:
        self._doc = document
        self._original = original
        self._original_index = original_index
        self._replacements = list(replacements)
        self.description = f"Trim {original.__class__.__name__}"

    def redo(self) -> None:
        self._doc.remove_entity(self._original.id)
        for ent in self._replacements:
            self._doc.add_entity(ent)

    def undo(self) -> None:
        for ent in self._replacements:
            self._doc.remove_entity(ent.id)
        pos = min(self._original_index, len(self._doc.entities))
        self._doc.entities.insert(pos, self._original)
        self._doc._entity_by_id[self._original.id] = self._original
        self._doc.notify_changed()


# ---------------------------------------------------------------------------
# Intersection parameter collectors
# ---------------------------------------------------------------------------

def _intersections_on_line(
    line: LineEntity, others: List[BaseEntity],
) -> List[float]:
    """Sorted t-parameters on *line* where it intersects any entity in *others*."""
    params: List[float] = []
    for other in others:
        if other.id == line.id:
            continue
        if isinstance(other, LineEntity):
            t = _seg_seg_param(line.p1, line.p2, other.p1, other.p2)
            if t is not None:
                params.append(t)
        elif isinstance(other, (CircleEntity, ArcEntity)):
            ts = _line_circle_params(line.p1, line.p2, other.center, other.radius)
            for t in ts:
                if isinstance(other, ArcEntity):
                    px = line.p1.x + t * (line.p2.x - line.p1.x)
                    py = line.p1.y + t * (line.p2.y - line.p1.y)
                    angle = math.atan2(py - other.center.y, px - other.center.x)
                    if not _geo_angle_on_arc(angle, other.start_angle, other.end_angle, other.ccw):
                        continue
                params.append(t)
    return sorted(set(params))


def _intersections_on_arc(
    arc: ArcEntity, others: List[BaseEntity],
) -> List[float]:
    """Sorted arc-parameters [0, 1] on *arc* where it intersects entities."""
    params: List[float] = []
    for other in others:
        if other.id == arc.id:
            continue
        if isinstance(other, LineEntity):
            ts = _line_circle_params(other.p1, other.p2, arc.center, arc.radius)
            for t in ts:
                px = other.p1.x + t * (other.p2.x - other.p1.x)
                py = other.p1.y + t * (other.p2.y - other.p1.y)
                angle = math.atan2(py - arc.center.y, px - arc.center.x)
                if _geo_angle_on_arc(angle, arc.start_angle, arc.end_angle, arc.ccw):
                    params.append(_arc_parameter(angle, arc.start_angle, arc.end_angle, arc.ccw))
        elif isinstance(other, (CircleEntity, ArcEntity)):
            angles = _circle_circle_angles(arc.center, arc.radius, other.center, other.radius)
            for angle in angles:
                if not _geo_angle_on_arc(angle, arc.start_angle, arc.end_angle, arc.ccw):
                    continue
                if isinstance(other, ArcEntity):
                    ix = arc.center.x + arc.radius * math.cos(angle)
                    iy = arc.center.y + arc.radius * math.sin(angle)
                    oa = math.atan2(iy - other.center.y, ix - other.center.x)
                    if not _geo_angle_on_arc(oa, other.start_angle, other.end_angle, other.ccw):
                        continue
                params.append(_arc_parameter(angle, arc.start_angle, arc.end_angle, arc.ccw))
    return sorted(set(params))


def _intersections_on_circle(
    circle: CircleEntity, others: List[BaseEntity],
) -> List[float]:
    """Sorted normalised angles [0, 2π) on *circle* at intersections."""
    angles: List[float] = []
    for other in others:
        if other.id == circle.id:
            continue
        if isinstance(other, LineEntity):
            ts = _line_circle_params(other.p1, other.p2, circle.center, circle.radius)
            for t in ts:
                px = other.p1.x + t * (other.p2.x - other.p1.x)
                py = other.p1.y + t * (other.p2.y - other.p1.y)
                angles.append(_normalize_angle(
                    math.atan2(py - circle.center.y, px - circle.center.x)))
        elif isinstance(other, (CircleEntity, ArcEntity)):
            raw = _circle_circle_angles(circle.center, circle.radius, other.center, other.radius)
            for angle in raw:
                if isinstance(other, ArcEntity):
                    ix = circle.center.x + circle.radius * math.cos(angle)
                    iy = circle.center.y + circle.radius * math.sin(angle)
                    oa = math.atan2(iy - other.center.y, ix - other.center.x)
                    if not _geo_angle_on_arc(oa, other.start_angle, other.end_angle, other.ccw):
                        continue
                angles.append(_normalize_angle(angle))
    return sorted(set(angles))


# ---------------------------------------------------------------------------
# Trim logic per entity type
# ---------------------------------------------------------------------------

def _line_param_of_point(line: LineEntity, pt: Vec2) -> float:
    """Project *pt* onto *line* and return t ∈ [0, 1]."""
    dx, dy = line.p2.x - line.p1.x, line.p2.y - line.p1.y
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-12:
        return 0.0
    return max(0.0, min(1.0, ((pt.x - line.p1.x) * dx + (pt.y - line.p1.y) * dy) / len_sq))


def _trim_line(
    line: LineEntity, pick_pt: Vec2, others: List[BaseEntity],
) -> Optional[List[BaseEntity]]:
    params = _intersections_on_line(line, others)
    if not params:
        return None

    boundaries = [0.0] + params + [1.0]
    pick_t = _line_param_of_point(line, pick_pt)

    # Identify the picked segment, skipping degenerate zero-length intervals
    # (which arise when an intersection lands exactly on an endpoint).
    pick_seg = -1
    for i in range(len(boundaries) - 1):
        if boundaries[i + 1] - boundaries[i] < 1e-9:
            continue
        if boundaries[i] - 1e-9 <= pick_t <= boundaries[i + 1] + 1e-9:
            pick_seg = i
            break
    if pick_seg == -1:
        return None

    style = _copy_style(line)
    result: List[BaseEntity] = []
    for i in range(len(boundaries) - 1):
        if i == pick_seg:
            continue
        t0, t1 = boundaries[i], boundaries[i + 1]
        if t1 - t0 < 1e-10:
            continue
        result.append(LineEntity(p1=_lerp(line.p1, line.p2, t0),
                                 p2=_lerp(line.p1, line.p2, t1), **style))
    return result


def _trim_arc(
    arc: ArcEntity, pick_pt: Vec2, others: List[BaseEntity],
) -> Optional[List[BaseEntity]]:
    params = _intersections_on_arc(arc, others)
    if not params:
        return None

    boundaries = [0.0] + params + [1.0]
    pick_angle = math.atan2(pick_pt.y - arc.center.y, pick_pt.x - arc.center.x)
    pick_t = _arc_parameter(pick_angle, arc.start_angle, arc.end_angle, arc.ccw)

    pick_seg = -1
    for i in range(len(boundaries) - 1):
        if boundaries[i + 1] - boundaries[i] < 1e-9:
            continue
        if boundaries[i] - 1e-9 <= pick_t <= boundaries[i + 1] + 1e-9:
            pick_seg = i
            break
    if pick_seg == -1:
        return None

    style = _copy_style(arc)
    result: List[BaseEntity] = []
    for i in range(len(boundaries) - 1):
        if i == pick_seg:
            continue
        t0, t1 = boundaries[i], boundaries[i + 1]
        if t1 - t0 < 1e-10:
            continue
        sa = _arc_angle_at_param(arc.start_angle, arc.end_angle, arc.ccw, t0)
        ea = _arc_angle_at_param(arc.start_angle, arc.end_angle, arc.ccw, t1)
        result.append(ArcEntity(center=Vec2(arc.center.x, arc.center.y),
                                radius=arc.radius,
                                start_angle=sa, end_angle=ea,
                                ccw=arc.ccw, **style))
    return result


def _trim_circle(
    circle: CircleEntity, pick_pt: Vec2, others: List[BaseEntity],
) -> Optional[List[BaseEntity]]:
    angles = _intersections_on_circle(circle, others)
    if len(angles) < 2:
        return None  # Need ≥ 2 intersections to break a full circle

    TWO_PI = 2.0 * math.pi
    pick_angle = _normalize_angle(
        math.atan2(pick_pt.y - circle.center.y, pick_pt.x - circle.center.x))

    # Build CCW arc segments between consecutive intersection angles
    n = len(angles)
    segments: List[Tuple[float, float]] = []
    for i in range(n):
        a_start = angles[i]
        a_end = angles[(i + 1) % n]
        if a_end <= a_start:
            a_end += TWO_PI
        segments.append((a_start, a_end))

    # Find which segment contains the pick angle
    pick_seg = -1
    for idx, (a_start, a_end) in enumerate(segments):
        pa = pick_angle
        if pa < a_start:
            pa += TWO_PI
        if a_start - 1e-9 <= pa <= a_end + 1e-9:
            pick_seg = idx
            break
    if pick_seg == -1:
        return None

    style = _copy_style(circle)
    result: List[BaseEntity] = []
    for idx, (a_start, a_end) in enumerate(segments):
        if idx == pick_seg:
            continue
        result.append(ArcEntity(center=Vec2(circle.center.x, circle.center.y),
                                radius=circle.radius,
                                start_angle=a_start, end_angle=a_end,
                                ccw=True, **style))
    return result


def _trim_rect(
    rect: RectangleEntity, pick_pt: Vec2, others: List[BaseEntity],
) -> Optional[List[BaseEntity]]:
    """Explode rect into its four edges, trim the clicked edge, keep the rest."""
    edges = rect._edges()
    style = _copy_style(rect)

    # Find which edge was clicked.
    clicked_edge = min(range(4), key=lambda i: _geo_pt_seg_dist(pick_pt, edges[i][0], edges[i][1]))
    p1, p2 = edges[clicked_edge]

    # Treat that edge as a temporary LineEntity to reuse _trim_line.
    temp_line = LineEntity(p1=p1, p2=p2, **style)
    trimmed = _trim_line(temp_line, pick_pt, others)
    if trimmed is None:
        return None

    result: List[BaseEntity] = []
    # Keep the three untouched edges as lines.
    for i, (a, b) in enumerate(edges):
        if i != clicked_edge:
            result.append(LineEntity(p1=a, p2=b, **style))
    # Add the surviving segment(s) from the trimmed edge.
    result.extend(trimmed)
    return result


# ---------------------------------------------------------------------------
# Ellipse trim helpers
# ---------------------------------------------------------------------------

_ELLIPSE_TESS_STEPS = 128  # tessellation resolution for intersection finding


def _ellipse_line_params(ell: "EllipseEntity", p1: Vec2, p2: Vec2) -> List[float]:
    """Return parametric angles on *ell* where segment p1→p2 crosses it."""
    params: List[float] = []
    tess = ell._tessellated(steps=_ELLIPSE_TESS_STEPS)
    span = ell._param_span()
    n = len(tess) - 1
    for i in range(n):
        t = _seg_seg_param(tess[i], tess[i + 1], p1, p2)
        if t is not None:
            # Approximate parametric angle proportionally within the arc span
            param = (ell.start_param + span * (i + t) / n) % (2 * math.pi)
            params.append(param)
    return params


def _intersections_on_ellipse(ell: "EllipseEntity", others: List[BaseEntity]) -> List[float]:
    """Sorted parametric angles on *ell* where it intersects entities in *others*."""
    params: List[float] = []
    for other in others:
        if other.id == ell.id:
            continue
        if isinstance(other, LineEntity):
            params.extend(_ellipse_line_params(ell, other.p1, other.p2))
        elif isinstance(other, (ArcEntity, CircleEntity, EllipseEntity)):
            # Tessellate the other entity and intersect segment by segment
            if isinstance(other, EllipseEntity):
                other_pts = other._tessellated(steps=_ELLIPSE_TESS_STEPS)
            else:
                # Arc or Circle — sample perimeter
                steps = 64
                if isinstance(other, ArcEntity):
                    a_span = _arc_span(other.start_angle, other.end_angle, other.ccw)
                    other_pts = [
                        Vec2(other.center.x + other.radius * math.cos(other.start_angle + a_span * i / steps),
                             other.center.y + other.radius * math.sin(other.start_angle + a_span * i / steps))
                        for i in range(steps + 1)
                    ]
                else:
                    other_pts = [
                        Vec2(other.center.x + other.radius * math.cos(2 * math.pi * i / steps),
                             other.center.y + other.radius * math.sin(2 * math.pi * i / steps))
                        for i in range(steps + 1)
                    ]
            for j in range(len(other_pts) - 1):
                params.extend(_ellipse_line_params(ell, other_pts[j], other_pts[j + 1]))
    return sorted(set(params))


def _ellipse_param_of_point(ell: "EllipseEntity", pt: Vec2) -> float:
    """Return parametric angle on *ell* closest to *pt* (within arc span)."""
    loc = ell._world_to_local(pt)
    param = ell._nearest_param(loc)
    if not ell._param_on_arc(param):
        return ell.start_param
    return param


def _trim_ellipse(ell: "EllipseEntity", pick_pt: Vec2, others: List[BaseEntity]) -> Optional[List[BaseEntity]]:
    """Return replacement entities for trimming *ell* at *pick_pt*."""
    params = _intersections_on_ellipse(ell, others)
    if not params:
        return None

    span = ell._param_span()
    # Normalise all params into [start, start+span]
    start = ell.start_param
    boundaries = [0.0] + sorted(
        ((p - start) % (2 * math.pi)) / span for p in params
        if ell._param_on_arc(p)
    ) + [1.0]
    # Deduplicate
    boundaries = [boundaries[0]] + [
        b for i, b in enumerate(boundaries[1:]) if b - boundaries[i] > 1e-9
    ]

    pick_param = _ellipse_param_of_point(ell, pick_pt)
    pick_t = ((pick_param - start) % (2 * math.pi)) / span

    pick_seg = -1
    for i in range(len(boundaries) - 1):
        if boundaries[i + 1] - boundaries[i] < 1e-9:
            continue
        if boundaries[i] - 1e-9 <= pick_t <= boundaries[i + 1] + 1e-9:
            pick_seg = i
            break
    if pick_seg == -1:
        return None

    style = _copy_style(ell)
    result: List[BaseEntity] = []
    for i in range(len(boundaries) - 1):
        if i == pick_seg:
            continue
        t0, t1 = boundaries[i], boundaries[i + 1]
        if t1 - t0 < 1e-10:
            continue
        new_start = (start + t0 * span) % (2 * math.pi)
        new_end = (start + t1 * span) % (2 * math.pi)
        result.append(EllipseEntity(
            center=ell.center, radius_x=ell.radius_x, radius_y=ell.radius_y,
            rotation=ell.rotation, start_param=new_start, end_param=new_end,
            **style,
        ))
    return result


# ---------------------------------------------------------------------------
# Pick-nearest-entity helper
# ---------------------------------------------------------------------------

_MAX_PICK_DIST = 1e12  # effectively unlimited fallback


def _nearest_entity(pt: Vec2, entities: List[BaseEntity],
                    tolerance: float) -> Optional[BaseEntity]:
    """Return the closest entity whose geometry is within *tolerance* of *pt*."""
    best: Optional[BaseEntity] = None
    best_dist = _MAX_PICK_DIST
    for ent in entities:
        if not ent.hit_test(pt, tolerance):
            continue
        # Prefer the entity whose geometry is closest to pt.
        d = _entity_dist(ent, pt)
        if d < best_dist:
            best_dist = d
            best = ent
    return best


def _entity_dist(ent: BaseEntity, pt: Vec2) -> float:
    """Approximate shortest distance from *pt* to the entity geometry."""
    if isinstance(ent, LineEntity):
        return _geo_pt_seg_dist(pt, ent.p1, ent.p2)
    if isinstance(ent, CircleEntity):
        return abs(math.hypot(pt.x - ent.center.x, pt.y - ent.center.y) - ent.radius)
    if isinstance(ent, ArcEntity):
        return abs(math.hypot(pt.x - ent.center.x, pt.y - ent.center.y) - ent.radius)
    if isinstance(ent, EllipseEntity):
        return ent._distance_to_perimeter(pt)
    # Fallback: distance to bounding-box centre
    bb = ent.bounding_box()
    if bb:
        return math.hypot(pt.x - (bb.min_x + bb.max_x) / 2,
                          pt.y - (bb.min_y + bb.max_y) / 2)
    return _MAX_PICK_DIST


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

def _trim_preview_segment(
    pt: Vec2, entities: List[BaseEntity], tolerance: float,
    cutting_edges: Optional[List[BaseEntity]] = None,
) -> List[BaseEntity]:
    """Return the segment that *would* be removed if the user clicked at *pt*.

    *entities* is the full entity list used for target picking.
    *cutting_edges* restricts which entities act as cutting boundaries;
    defaults to *entities* when None.
    """
    target = _nearest_entity(pt, entities, tolerance)
    if target is None:
        return []

    edges = cutting_edges if cutting_edges is not None else entities

    if isinstance(target, LineEntity):
        params = _intersections_on_line(target, edges)
        if not params:
            return []
        boundaries = [0.0] + params + [1.0]
        pick_t = _line_param_of_point(target, pt)
        for i in range(len(boundaries) - 1):
            if boundaries[i + 1] - boundaries[i] < 1e-9:
                continue
            if boundaries[i] - 1e-9 <= pick_t <= boundaries[i + 1] + 1e-9:
                t0, t1 = boundaries[i], boundaries[i + 1]
                if t1 - t0 < 1e-10:
                    return []
                return [LineEntity(
                    p1=_lerp(target.p1, target.p2, t0),
                    p2=_lerp(target.p1, target.p2, t1),
                    **_copy_style(target),
                )]
    elif isinstance(target, ArcEntity):
        params = _intersections_on_arc(target, edges)
        if not params:
            return []
        boundaries = [0.0] + params + [1.0]
        pick_angle = math.atan2(pt.y - target.center.y, pt.x - target.center.x)
        pick_t = _arc_parameter(pick_angle, target.start_angle, target.end_angle, target.ccw)
        for i in range(len(boundaries) - 1):
            if boundaries[i + 1] - boundaries[i] < 1e-9:
                continue
            if boundaries[i] - 1e-9 <= pick_t <= boundaries[i + 1] + 1e-9:
                t0, t1 = boundaries[i], boundaries[i + 1]
                if t1 - t0 < 1e-10:
                    return []
                sa = _arc_angle_at_param(target.start_angle, target.end_angle, target.ccw, t0)
                ea = _arc_angle_at_param(target.start_angle, target.end_angle, target.ccw, t1)
                return [ArcEntity(
                    center=Vec2(target.center.x, target.center.y),
                    radius=target.radius,
                    start_angle=sa, end_angle=ea,
                    ccw=target.ccw,
                    **_copy_style(target),
                )]
    elif isinstance(target, CircleEntity):
        angles = _intersections_on_circle(target, edges)
        if len(angles) < 2:
            return []
        TWO_PI = 2.0 * math.pi
        pick_angle = _normalize_angle(
            math.atan2(pt.y - target.center.y, pt.x - target.center.x))
        n = len(angles)
        for i in range(n):
            a_start = angles[i]
            a_end = angles[(i + 1) % n]
            if a_end <= a_start:
                a_end += TWO_PI
            pa = pick_angle
            if pa < a_start:
                pa += TWO_PI
            if a_start - 1e-9 <= pa <= a_end + 1e-9:
                return [ArcEntity(
                    center=Vec2(target.center.x, target.center.y),
                    radius=target.radius,
                    start_angle=a_start, end_angle=a_end,
                    ccw=True,
                    **_copy_style(target),
                )]
    elif isinstance(target, RectangleEntity):
        rect_edges = target._edges()
        clicked_edge = min(range(4), key=lambda i: _geo_pt_seg_dist(pt, rect_edges[i][0], rect_edges[i][1]))
        p1, p2 = rect_edges[clicked_edge]
        temp_line = LineEntity(p1=p1, p2=p2, **_copy_style(target))
        params = _intersections_on_line(temp_line, edges)
        if not params:
            return []
        boundaries = [0.0] + params + [1.0]
        pick_t = _line_param_of_point(temp_line, pt)
        for i in range(len(boundaries) - 1):
            if boundaries[i + 1] - boundaries[i] < 1e-9:
                continue
            if boundaries[i] - 1e-9 <= pick_t <= boundaries[i + 1] + 1e-9:
                t0, t1 = boundaries[i], boundaries[i + 1]
                if t1 - t0 < 1e-10:
                    return []
                return [LineEntity(
                    p1=_lerp(p1, p2, t0),
                    p2=_lerp(p1, p2, t1),
                    **_copy_style(target),
                )]
    return []


@command("trimCommand")
class TrimCommand(CommandBase):
    """Trim entities at their intersections with other geometry.

    Uses "quick trim" mode: all visible entities serve as cutting
    edges.  Click on the portion of an entity to remove it.
    """

    def execute(self) -> None:
        self.editor.suppress_osnap = True
        self.editor.suppress_dynamic_input = True
        try:
            self._run_trim_loop()
        finally:
            self.editor.suppress_osnap = False
            self.editor.suppress_dynamic_input = False
            self.editor.clear_dynamic()
            self.editor.clear_highlight()

    def _run_trim_loop(self) -> None:
        tol = self.editor.settings.trim_pick_tolerance
        doc = self.editor.document

        # If entities are preselected, use only those as cutting edges.
        sel_ids = self.editor.selection.ids
        if sel_ids:
            cutting_edges = [e for e in doc.entities if e.id in sel_ids]
            self.editor.set_highlight(cutting_edges)
            prompt = "Trim (cutting edges highlighted): click segment to remove (Escape to exit)"
        else:
            cutting_edges = None  # resolved fresh each iteration from all entities
            prompt = "Trim: click the segment to remove (Escape to exit)"

        def _preview(mouse: Vec2) -> List[BaseEntity]:
            all_ents = list(self.editor.document.entities)
            edges = cutting_edges if cutting_edges is not None else all_ents
            return _trim_preview_segment(mouse, all_ents, tolerance=tol, cutting_edges=edges)

        self.editor.set_dynamic(_preview)

        while True:
            pt = self.editor.get_point(prompt)

            doc = self.editor.document

            target = _nearest_entity(pt, list(doc.entities), tolerance=tol)
            if target is None:
                self.editor.status_message.emit("Trim: no entity at pick point")
                continue

            replacements: Optional[List[BaseEntity]] = None
            trim_edges = cutting_edges if cutting_edges is not None else list(doc.entities)
            if isinstance(target, LineEntity):
                replacements = _trim_line(target, pt, trim_edges)
            elif isinstance(target, ArcEntity):
                replacements = _trim_arc(target, pt, trim_edges)
            elif isinstance(target, CircleEntity):
                replacements = _trim_circle(target, pt, trim_edges)
            elif isinstance(target, RectangleEntity):
                replacements = _trim_rect(target, pt, trim_edges)
            elif isinstance(target, EllipseEntity):
                replacements = _trim_ellipse(target, pt, trim_edges)

            if replacements is None:
                self.editor.status_message.emit("Trim: no cutting edges intersect that entity")
                continue

            original_index = 0
            for i, ent in enumerate(doc.entities):
                if ent.id == target.id:
                    original_index = i
                    break

            doc.remove_entity(target.id)
            self.editor.selection.remove(target.id)
            self.editor.entity_removed.emit(target.id)
            for ent in replacements:
                doc.add_entity(ent)
                self.editor.entity_added.emit(ent)
            self.editor.document_changed.emit()

            self.editor.push_undo_command(
                _TrimUndoCommand(doc, target, original_index, replacements))

            # If we trimmed a cutting edge, update the highlight list.
            if cutting_edges is not None:
                cutting_edges = [e for e in cutting_edges if e.id != target.id]
                self.editor.set_highlight(cutting_edges)
