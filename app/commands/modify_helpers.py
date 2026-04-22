"""Shared helpers for modify commands — geometry transforms and undo commands."""
from __future__ import annotations

import copy
import math
import uuid
from typing import List, Optional

from app.editor.undo import UndoCommand
from app.entities import (
    BaseEntity, Vec2,
    LineEntity, CircleEntity, ArcEntity, RectangleEntity, PolylineEntity,
)


def _copy_style(ent: BaseEntity) -> dict:
    return dict(layer=ent.layer, color=ent.color,
                line_weight=ent.line_weight, line_style=ent.line_style)


def _collect_selected(editor) -> List[BaseEntity]:
    doc = editor.document
    ids = editor.selection.ids
    return [e for e in doc.entities if e.id in ids]


def _transform_entity(ent: BaseEntity, fn, post_fn=None) -> BaseEntity:
    """Return a deep-copied, transformed version of *ent*.

    Parameters
    ----------
    ent:
        The source entity (not mutated).
    fn:
        A callable ``Vec2 → Vec2`` applied to every point attribute.
    post_fn:
        Optional callable ``(copy, original) → None`` invoked after all
        point transforms.  Use it to adjust non-point attributes such as
        arc angles or radii that depend on the specific transform type.
    """
    e = copy.deepcopy(ent)
    e.id = str(uuid.uuid4())
    if isinstance(e, LineEntity):
        e.p1 = fn(e.p1)
        e.p2 = fn(e.p2)
    elif isinstance(e, CircleEntity):
        e.center = fn(e.center)
    elif isinstance(e, ArcEntity):
        e.center = fn(e.center)
    elif isinstance(e, RectangleEntity):
        e.p1 = fn(e.p1)
        e.p2 = fn(e.p2)
    elif isinstance(e, PolylineEntity):
        e.points = [fn(p) for p in e.points]
    else:
        for attr in ("p1", "p2", "p3", "center", "start", "end"):
            v = getattr(e, attr, None)
            if isinstance(v, Vec2):
                setattr(e, attr, fn(v))
        if hasattr(e, "points"):
            e.points = [fn(p) for p in e.points]
    if post_fn is not None:
        post_fn(e, ent)
    return e


def _translate(v: Vec2, dx: float, dy: float) -> Vec2:
    return Vec2(v.x + dx, v.y + dy)


def _rotate_pt(v: Vec2, cx: float, cy: float, cos_a: float, sin_a: float) -> Vec2:
    rx = v.x - cx
    ry = v.y - cy
    return Vec2(cx + rx * cos_a - ry * sin_a,
                cy + rx * sin_a + ry * cos_a)


def _mirror_pt(v: Vec2, ax: float, ay: float, bx: float, by: float) -> Vec2:
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    if d2 < 1e-20:
        return v
    t = ((v.x - ax) * dx + (v.y - ay) * dy) / d2
    fx = ax + t * dx
    fy = ay + t * dy
    return Vec2(2 * fx - v.x, 2 * fy - v.y)


def _scale_pt(v: Vec2, cx: float, cy: float, factor: float) -> Vec2:
    return Vec2(cx + (v.x - cx) * factor, cy + (v.y - cy) * factor)


def _rotate_angle(a: float, angle: float) -> float:
    return a + angle


class _TransformUndoCommand(UndoCommand):
    """Undoable bulk transformation — stores before/after snapshots."""

    def __init__(self, document, before: List[BaseEntity],
                 after: List[BaseEntity], desc: str) -> None:
        self._doc = document
        self._before = before
        self._after = after
        # Keep original IDs (from before) so redo() can locate live entities
        # even though after snapshots carry a different UUID from _transform_entity.
        self._original_ids = [e.id for e in before]
        self.description = desc

    def redo(self) -> None:
        self._apply_pairs(self._original_ids, self._after)

    def undo(self) -> None:
        self._apply_pairs(self._original_ids, self._before)

    def _apply_pairs(
        self, ids: List[str], snapshots: List[BaseEntity]
    ) -> None:
        for orig_id, snap in zip(ids, snapshots):
            live = self._doc.get_entity(orig_id)
            if live is None:
                continue
            for attr in vars(snap):
                if not attr.startswith("_") and attr not in ("type", "id"):
                    try:
                        setattr(live, attr, getattr(snap, attr))
                    except Exception:
                        pass
        self._doc._notify()


class _ReplaceEntitiesUndoCommand(UndoCommand):
    """Undoable removal of originals + addition of copies."""

    def __init__(self, document, removed: List[BaseEntity],
                 removed_indices: List[int],
                 added: List[BaseEntity], desc: str) -> None:
        self._doc = document
        self._removed = removed
        self._removed_indices = removed_indices
        self._added = added
        self._has_removed = bool(removed)
        self.description = desc

    def redo(self) -> None:
        for ent in self._removed:
            self._doc.remove_entity(ent.id)
        for ent in self._added:
            self._doc.add_entity(ent)
        self._doc._notify()

    def undo(self) -> None:
        for ent in self._added:
            self._doc.remove_entity(ent.id)
        for idx, ent in zip(self._removed_indices, self._removed):
            pos = min(idx, len(self._doc.entities))
            self._doc.entities.insert(pos, ent)
        self._doc._notify()


# ---------------------------------------------------------------------------
# Post-transform hooks for arc/radius attributes
# ---------------------------------------------------------------------------

def _post_rotate_arc(e: BaseEntity, orig: BaseEntity, angle: float) -> None:
    """Post-transform hook: rotate arc angles and convert linear→aligned on rotate."""
    if isinstance(e, ArcEntity):
        e.start_angle = _rotate_angle(orig.start_angle, angle)
        e.end_angle = _rotate_angle(orig.end_angle, angle)
    # Ellipse orientation is stored as a world-frame rotation of its local axes.
    # Rotating the entity in world space therefore adds to this rotation.
    from app.entities.ellipse import EllipseEntity
    if isinstance(e, EllipseEntity):
        e.rotation = orig.rotation + angle
    # A rotated linear dimension is no longer axis-aligned — promote to aligned.
    from app.entities.dimension import DimensionEntity
    if isinstance(e, DimensionEntity) and e.dim_type == "linear":
        e.dim_type = "aligned"


def _post_scale_radius(e: BaseEntity, orig: BaseEntity, factor: float) -> None:
    """Post-transform hook: scale ``radius`` on circles and arcs."""
    if hasattr(orig, "radius"):
        e.radius = orig.radius * abs(factor)


# ---------------------------------------------------------------------------
# Unified commit helper
# ---------------------------------------------------------------------------

def _commit_transform(
    editor,
    entities: List[BaseEntity],
    pt_fn,
    post_fn=None,
    description: str = "Transform",
) -> None:
    """Apply *pt_fn* (and optional *post_fn*) to *entities* in-place.

    Builds before/after snapshots, applies the transform to the live
    document entities by attribute-copying from the after snapshots, pushes
    a single :class:`_TransformUndoCommand`, clears the selection, and
    emits ``document_changed``.

    This replaces the repetitive per-entity-type if/elif mutation blocks
    that previously appeared in each modify command's ``execute()`` method.
    """
    doc = editor.document
    before = [copy.deepcopy(e) for e in entities]
    after = [_transform_entity(e, pt_fn, post_fn) for e in entities]

    # Apply snapshots to live entities without replacing the object identity
    # (canvas and other subsystems hold references to the live objects).
    # Use the original IDs (from *entities*) for lookup — after snapshots carry
    # a different UUID because _transform_entity always assigns a fresh one.
    for orig, snap in zip(entities, after):
        live = doc.get_entity(orig.id)
        if live is None:
            continue
        for attr in vars(snap):
            if not attr.startswith("_") and attr not in ("type", "id"):
                try:
                    setattr(live, attr, getattr(snap, attr))
                except Exception:
                    pass
    doc._notify()

    editor._undo_stack.push(_TransformUndoCommand(doc, before, after, description))
    editor.selection.clear()
    editor.document_changed.emit()
