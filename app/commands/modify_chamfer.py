"""Chamfer command — bevel a corner between two lines by two distances.

Workflow:
1. Enter first chamfer distance.
2. Enter second chamfer distance (or accept same as first).
3. Click first line (near the end to keep).
4. Click second line (near the end to keep).
5. Lines are trimmed and a bevel edge is inserted.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from app.editor import command
from app.editor.base_command import CommandBase
from app.editor.undo import UndoCommand
from app.entities import BaseEntity, Vec2, LineEntity
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


def _chamfer_geometry(
    line1: LineEntity, line2: LineEntity,
    dist1: float, dist2: float,
) -> Optional[Tuple[Vec2, Vec2, Vec2, Vec2]]:
    """Return (keep1, trim1, trim2, keep2) or None."""
    d1x = line1.p2.x - line1.p1.x; d1y = line1.p2.y - line1.p1.y
    d2x = line2.p2.x - line2.p1.x; d2y = line2.p2.y - line2.p1.y
    len1 = math.hypot(d1x, d1y); len2 = math.hypot(d2x, d2y)
    if len1 < 1e-10 or len2 < 1e-10:
        return None

    corner = _infinite_line_intersect(line1.p1, line1.p2, line2.p1, line2.p2)
    if corner is None:
        return None

    # Keep the endpoint farthest from the corner (the end NOT being trimmed).
    def _kept_end(line: LineEntity) -> Tuple[Vec2, float]:
        d1 = math.hypot(line.p1.x - corner.x, line.p1.y - corner.y)
        d2 = math.hypot(line.p2.x - corner.x, line.p2.y - corner.y)
        kept = line.p1 if d1 > d2 else line.p2
        seg_len = math.hypot(kept.x - corner.x, kept.y - corner.y)
        return kept, seg_len

    keep1, seg_len1 = _kept_end(line1)
    keep2, seg_len2 = _kept_end(line2)

    if dist1 > seg_len1 + 1e-6 or dist2 > seg_len2 + 1e-6:
        return None  # chamfer exceeds segment length

    # Inward unit vectors from kept end toward corner
    in1x = (corner.x - keep1.x) / seg_len1; in1y = (corner.y - keep1.y) / seg_len1
    in2x = (corner.x - keep2.x) / seg_len2; in2y = (corner.y - keep2.y) / seg_len2

    trim1 = Vec2(corner.x - in1x * dist1, corner.y - in1y * dist1)
    trim2 = Vec2(corner.x - in2x * dist2, corner.y - in2y * dist2)

    return keep1, trim1, trim2, keep2


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------

class _ChamferUndoCommand(UndoCommand):
    def __init__(self, doc, orig1, idx1, orig2, idx2, replacements) -> None:
        self._doc = doc
        self._orig1, self._idx1 = orig1, idx1
        self._orig2, self._idx2 = orig2, idx2
        self._replacements = replacements
        self.description = "Chamfer"

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
        self._doc._notify()


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@command("chamferCommand")
class ChamferCommand(CommandBase):
    """Bevel a corner between two lines by specified chamfer distances."""

    def execute(self) -> None:
        self.editor.suppress_dynamic_input = False
        dist1 = self.editor.get_float("Chamfer: enter first distance")
        if dist1 < 0:
            self.editor.status_message.emit("Chamfer: distance must be >= 0")
            return
        dist2 = self.editor.get_float(
            f"Chamfer: enter second distance (0 = same as first: {dist1:.4g})"
        )
        if dist2 <= 0:
            dist2 = dist1

        self.editor.suppress_osnap = True
        self.editor.suppress_dynamic_input = True
        try:
            self._run(dist1, dist2)
        finally:
            self.editor.suppress_osnap = False
            self.editor.suppress_dynamic_input = False

    def _run(self, dist1: float, dist2: float) -> None:
        tol = self.editor.settings.trim_pick_tolerance
        doc = self.editor.document

        pick1 = self.editor.get_point(f"Chamfer d1={dist1:.4g} d2={dist2:.4g}: click first line")
        line1 = _nearest_line(pick1, list(doc.entities), tol)
        if line1 is None:
            self.editor.status_message.emit("Chamfer: no line found at first pick")
            return

        pick2 = self.editor.get_point(f"Chamfer: click second line")
        line2 = _nearest_line(pick2, list(doc.entities), tol)
        if line2 is None or line2.id == line1.id:
            self.editor.status_message.emit("Chamfer: second line not found (pick a different line)")
            return

        result = _chamfer_geometry(line1, line2, dist1, dist2)
        if result is None:
            self.editor.status_message.emit("Chamfer: lines are parallel or distances exceed segment lengths")
            return

        keep1, trim1, trim2, keep2 = result
        style1 = _copy_style(line1)
        style2 = _copy_style(line2)

        replacements: List[BaseEntity] = []
        if math.hypot(keep1.x - trim1.x, keep1.y - trim1.y) > 1e-6:
            replacements.append(LineEntity(p1=keep1, p2=trim1, **style1))
        if math.hypot(keep2.x - trim2.x, keep2.y - trim2.y) > 1e-6:
            replacements.append(LineEntity(p1=keep2, p2=trim2, **style2))
        if math.hypot(trim1.x - trim2.x, trim1.y - trim2.y) > 1e-6:
            replacements.append(LineEntity(p1=trim1, p2=trim2, **style1))

        entities = list(doc.entities)
        idx1 = next((i for i, e in enumerate(entities) if e.id == line1.id), 0)
        idx2 = next((i for i, e in enumerate(entities) if e.id == line2.id), 0)

        cmd = _ChamferUndoCommand(doc, line1, idx1, line2, idx2, replacements)
        cmd.redo()
        self.editor._undo_stack.push(cmd)
        self.editor.document_changed.emit()
