"""Fillet command — round a corner between two lines with a given radius.

Workflow:
1. Enter fillet radius (0 = sharp corner trim-to-intersection).
2. Click first line (near the end to keep).
3. Click second line (near the end to keep).
4. Lines are trimmed to tangent points; an arc is inserted.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from app.editor import command
from app.editor.base_command import CommandBase
from app.editor.undo import UndoCommand
from app.entities import BaseEntity, Vec2, LineEntity, ArcEntity
from app.commands.modify_helpers import _copy_style
from app.geometry import _geo_pt_seg_dist


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _nearest_line(pt: Vec2, entities: List[BaseEntity], tol: float) -> Optional[LineEntity]:
    """Return the nearest LineEntity to pt within tol, or the globally nearest if none within tol."""
    best_d = float("inf")
    best: Optional[LineEntity] = None
    for ent in entities:
        if not isinstance(ent, LineEntity):
            continue
        d = _geo_pt_seg_dist(pt, ent.p1, ent.p2)
        if d < best_d:
            best_d, best = d, ent
    return best


def _infinite_line_intersect(a1: Vec2, a2: Vec2, b1: Vec2, b2: Vec2) -> Optional[Vec2]:
    """Intersection of two infinite lines (not bounded by segment endpoints)."""
    dx1, dy1 = a2.x - a1.x, a2.y - a1.y
    dx2, dy2 = b2.x - b1.x, b2.y - b1.y
    denom = dx1 * dy2 - dy1 * dx2
    if abs(denom) < 1e-12:
        return None
    t = ((b1.x - a1.x) * dy2 - (b1.y - a1.y) * dx2) / denom
    return Vec2(a1.x + t * dx1, a1.y + t * dy1)


def _fillet_geometry(
    line1: LineEntity, pick1: Vec2,
    line2: LineEntity, pick2: Vec2,
    radius: float,
) -> Optional[Tuple[Vec2, Vec2, Vec2, Vec2, Vec2, bool]]:
    """Return (keep_end1, tan1, arc_center, tan2, keep_end2, ccw) or None."""
    d1x = line1.p2.x - line1.p1.x; d1y = line1.p2.y - line1.p1.y
    d2x = line2.p2.x - line2.p1.x; d2y = line2.p2.y - line2.p1.y
    len1 = math.hypot(d1x, d1y); len2 = math.hypot(d2x, d2y)
    if len1 < 1e-10 or len2 < 1e-10:
        return None

    corner = _infinite_line_intersect(line1.p1, line1.p2, line2.p1, line2.p2)
    if corner is None:
        return None

    # Keep the endpoint farthest from the corner (the end NOT being trimmed).
    def _kept_end(line: LineEntity) -> Vec2:
        d1 = math.hypot(line.p1.x - corner.x, line.p1.y - corner.y)
        d2 = math.hypot(line.p2.x - corner.x, line.p2.y - corner.y)
        return line.p1 if d1 > d2 else line.p2

    keep1 = _kept_end(line1)
    keep2 = _kept_end(line2)

    # Inward unit vectors (from kept end toward corner)
    dist1 = math.hypot(keep1.x - corner.x, keep1.y - corner.y)
    dist2 = math.hypot(keep2.x - corner.x, keep2.y - corner.y)
    if dist1 < 1e-10 or dist2 < 1e-10:
        return None

    in1x = (corner.x - keep1.x) / dist1; in1y = (corner.y - keep1.y) / dist1
    in2x = (corner.x - keep2.x) / dist2; in2y = (corner.y - keep2.y) / dist2

    if radius < 1e-6:
        # Sharp corner: trim both lines to intersection point
        return keep1, corner, corner, corner, keep2, True

    cross = in1x * in2y - in1y * in2x
    dot   = in1x * in2x + in1y * in2y
    angle_between = math.atan2(abs(cross), dot)
    if abs(math.sin(angle_between / 2)) < 1e-10:
        return None

    dist_to_tan = radius / math.tan(angle_between / 2)
    tan1 = Vec2(corner.x - in1x * dist_to_tan, corner.y - in1y * dist_to_tan)
    tan2 = Vec2(corner.x - in2x * dist_to_tan, corner.y - in2y * dist_to_tan)

    # Verify tangent points lie within the segment (not beyond the far end)
    if dist_to_tan > dist1 + 1e-6 or dist_to_tan > dist2 + 1e-6:
        return None

    bis_len = math.hypot(in1x + in2x, in1y + in2y)
    if bis_len < 1e-10:
        return None
    bis_x = (in1x + in2x) / bis_len; bis_y = (in1y + in2y) / bis_len
    dist_to_center = radius / math.sin(angle_between / 2)
    arc_center = Vec2(corner.x - bis_x * dist_to_center, corner.y - bis_y * dist_to_center)

    ccw = cross < 0
    return keep1, tan1, arc_center, tan2, keep2, ccw


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------

class _FilletUndoCommand(UndoCommand):
    def __init__(self, doc, orig1, idx1, orig2, idx2, replacements) -> None:
        self._doc = doc
        self._orig1, self._idx1 = orig1, idx1
        self._orig2, self._idx2 = orig2, idx2
        self._replacements = replacements
        self.description = "Fillet"

    def redo(self) -> None:
        self._doc.remove_entity(self._orig1.id)
        self._doc.remove_entity(self._orig2.id)
        for ent in self._replacements:
            self._doc.add_entity(ent)

    def undo(self) -> None:
        for ent in self._replacements:
            self._doc.remove_entity(ent.id)
        for idx, orig in sorted([(self._idx1, self._orig1), (self._idx2, self._orig2)]):
            pos = min(idx, len(self._doc.entities))
            self._doc.entities.insert(pos, orig)
            self._doc._entity_by_id[orig.id] = orig
        self._doc.notify_changed()


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@command("filletCommand")
class FilletCommand(CommandBase):
    """Round a corner between two lines with a given radius."""

    def execute(self) -> None:
        self.editor.suppress_dynamic_input = False
        radius = self.editor.get_float("Fillet: enter radius (0 = sharp corner)")
        if radius < 0:
            self.editor.status_message.emit("Fillet: radius must be >= 0")
            return

        self.editor.suppress_osnap = True
        self.editor.suppress_dynamic_input = True
        try:
            self._run(radius)
        finally:
            self.editor.suppress_osnap = False
            self.editor.suppress_dynamic_input = False

    def _run(self, radius: float) -> None:
        tol = self.editor.settings.trim_pick_tolerance
        doc = self.editor.document

        pick1 = self.editor.get_point(f"Fillet r={radius:.4g}: click first line")
        line1 = _nearest_line(pick1, list(doc.entities), tol)
        if line1 is None:
            self.editor.status_message.emit("Fillet: no line found at first pick")
            return

        pick2 = self.editor.get_point(f"Fillet r={radius:.4g}: click second line")
        line2 = _nearest_line(pick2, list(doc.entities), tol)
        if line2 is None or line2.id == line1.id:
            self.editor.status_message.emit("Fillet: second line not found (pick a different line)")
            return

        result = _fillet_geometry(line1, pick1, line2, pick2, radius)
        if result is None:
            self.editor.status_message.emit("Fillet: lines are parallel or fillet doesn't fit on segments")
            return

        keep1, tan1, arc_center, tan2, keep2, ccw = result
        style1 = _copy_style(line1)
        style2 = _copy_style(line2)

        replacements: List[BaseEntity] = []
        if math.hypot(keep1.x - tan1.x, keep1.y - tan1.y) > 1e-6:
            replacements.append(LineEntity(p1=keep1, p2=tan1, **style1))
        if math.hypot(keep2.x - tan2.x, keep2.y - tan2.y) > 1e-6:
            replacements.append(LineEntity(p1=keep2, p2=tan2, **style2))
        if radius > 1e-6:
            sa = math.atan2(tan1.y - arc_center.y, tan1.x - arc_center.x)
            ea = math.atan2(tan2.y - arc_center.y, tan2.x - arc_center.x)
            replacements.append(ArcEntity(
                center=arc_center, radius=radius,
                start_angle=sa, end_angle=ea, ccw=ccw, **style1,
            ))

        entities = list(doc.entities)
        idx1 = next((i for i, e in enumerate(entities) if e.id == line1.id), 0)
        idx2 = next((i for i, e in enumerate(entities) if e.id == line2.id), 0)

        cmd = _FilletUndoCommand(doc, line1, idx1, line2, idx2, replacements)
        cmd.redo()
        self.editor.push_undo_command(cmd)
        self.editor.document_changed.emit()
