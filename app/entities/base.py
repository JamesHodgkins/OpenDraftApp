"""
Base types shared by all drawing entities.

Provides Vec2 (a simple 2-D point/vector), BBox (axis-aligned bounding box),
and BaseEntity, the abstract root from which every concrete entity inherits.

Entity subclasses are automatically registered in ``_ENTITY_REGISTRY`` by
setting a ``_entity_kind`` ClassVar.  ``entity_from_dict`` (in the package
``__init__``) uses this registry, so adding a new entity type requires no
central edits — just declare the class with the appropriate ``_entity_kind``.

Protocol methods
----------------
Each entity subclass should override the following methods to participate in
the common dispatch without requiring edits in hit_testing.py, osnap_engine.py
or canvas.py when a new type is added:

  * ``bounding_box()``     — axis-aligned AABB in world coords.
  * ``hit_test()``         — point proximity check.
  * ``snap_candidates()``  — cursor-independent snap points.
  * ``nearest_snap()``     — closest point on entity to cursor.
  * ``perp_snaps()``       — perpendicular foot from a reference point.
  * ``draw()``             — render self onto a QPainter.
  * ``crosses_rect()``     — geometry-accurate rectangle-crossing test.
"""
from __future__ import annotations

import enum
import math
import uuid
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING, AbstractSet, Any, Callable, ClassVar,
    Dict, List, Optional, Tuple, Type,
)

if TYPE_CHECKING:
    # Resolved at type-check time only; avoids runtime Qt import in entities.
    from PySide6.QtGui import QPainter
    from PySide6.QtCore import QPointF


# ---------------------------------------------------------------------------
# Grip types — used by the grip-editing system
# ---------------------------------------------------------------------------

class GripType(enum.Enum):
    """Classification of a grip point on an entity."""
    ENDPOINT = "endpoint"       # dragging moves a single vertex/endpoint
    MIDPOINT = "midpoint"       # dragging moves the entire entity
    CENTER   = "center"         # dragging moves the entity (circles/arcs)
    QUADRANT = "quadrant"       # dragging resizes (radius change)
    CONTROL  = "control"        # generic control point


@dataclass(frozen=True)
class GripPoint:
    """A single grip point exposed by an entity for interactive editing.

    Attributes
    ----------
    position   — world-space location of the grip.
    entity_id  — ID of the owning entity.
    index      — ordinal grip index on the entity (used by ``move_grip``).
    grip_type  — semantic classification (endpoint / midpoint / centre …).
    """
    position: Vec2
    entity_id: str
    index: int
    grip_type: GripType = GripType.CONTROL


# ---------------------------------------------------------------------------
# Entity type registry (populated via BaseEntity.__init_subclass__)
# ---------------------------------------------------------------------------

_ENTITY_REGISTRY: Dict[str, Type["BaseEntity"]] = {}


# ---------------------------------------------------------------------------
# 2-D coordinate helper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Vec2:
    """An immutable 2-D point or vector.

    ``frozen=True`` enforces immutability and provides a hash, making
    Vec2 safe to use as a dict key or set member.
    """
    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Vec2":
        return cls(x=float(d["x"]), y=float(d["y"]))

    def __iter__(self):
        yield self.x
        yield self.y

    def __repr__(self) -> str:          # noqa: D105
        return f"Vec2({self.x}, {self.y})"


# ---------------------------------------------------------------------------
# Axis-aligned bounding box
# ---------------------------------------------------------------------------

@dataclass
class BBox:
    """Axis-aligned bounding box in world coordinates."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def contains(self, other: "BBox") -> bool:
        """Is *other* fully inside this box?"""
        return (self.min_x <= other.min_x and self.min_y <= other.min_y and
                self.max_x >= other.max_x and self.max_y >= other.max_y)

    def intersects(self, other: "BBox") -> bool:
        """Do the two boxes overlap?"""
        return not (self.max_x < other.min_x or other.max_x < self.min_x or
                    self.max_y < other.min_y or other.max_y < self.min_y)

    def intersects_viewport(
        self,
        vp_min_x: float, vp_min_y: float,
        vp_max_x: float, vp_max_y: float,
    ) -> bool:
        """AABB overlap test against a viewport rectangle."""
        return not (
            self.max_x < vp_min_x or self.min_x > vp_max_x or
            self.max_y < vp_min_y or self.min_y > vp_max_y
        )


# ---------------------------------------------------------------------------
# Shared 2-D geometry helpers (used by entity protocol implementations)
# ---------------------------------------------------------------------------

def _geo_dist(a: Vec2, b: Vec2) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


def _geo_pt_seg_dist(p: Vec2, a: Vec2, b: Vec2) -> float:
    """Shortest distance from point *p* to segment *a*–*b*."""
    dx, dy = b.x - a.x, b.y - a.y
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-12:
        return _geo_dist(p, a)
    t = max(0.0, min(1.0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len_sq))
    return _geo_dist(p, Vec2(a.x + t * dx, a.y + t * dy))


def _geo_angle_on_arc(angle: float, start: float, end: float, ccw: bool) -> bool:
    """Return True if *angle* (radians) lies within the arc sweep."""
    TWO_PI = 2.0 * math.pi
    angle = angle % TWO_PI
    start = start % TWO_PI
    end   = end   % TWO_PI
    if ccw:
        return (start <= angle <= end) if start <= end else (angle >= start or angle <= end)
    else:
        return (end <= angle <= start) if start >= end else (angle <= start or angle >= end)


def _geo_point_in_rect(p: Vec2, rmin: Vec2, rmax: Vec2) -> bool:
    return rmin.x <= p.x <= rmax.x and rmin.y <= p.y <= rmax.y


def _geo_seg_intersects_rect(a: Vec2, b: Vec2, rmin: Vec2, rmax: Vec2) -> bool:
    if _geo_point_in_rect(a, rmin, rmax) or _geo_point_in_rect(b, rmin, rmax):
        return True
    corners = [
        Vec2(rmin.x, rmin.y), Vec2(rmax.x, rmin.y),
        Vec2(rmax.x, rmax.y), Vec2(rmin.x, rmax.y),
    ]
    def _cross(o: Vec2, u: Vec2, v: Vec2) -> float:
        return (u.x - o.x) * (v.y - o.y) - (u.y - o.y) * (v.x - o.x)
    def _on_seg(p: Vec2, q: Vec2, r: Vec2) -> bool:
        return (min(p.x, r.x) <= q.x <= max(p.x, r.x) and
                min(p.y, r.y) <= q.y <= max(p.y, r.y))
    for i in range(4):
        c1, c2 = corners[i], corners[(i + 1) % 4]
        d1 = _cross(c1, c2, a); d2 = _cross(c1, c2, b)
        d3 = _cross(a, b, c1);  d4 = _cross(a, b, c2)
        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
                (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            return True
        if abs(d1) < 1e-12 and _on_seg(c1, a, c2): return True
        if abs(d2) < 1e-12 and _on_seg(c1, b, c2): return True
        if abs(d3) < 1e-12 and _on_seg(a, c1, b):  return True
        if abs(d4) < 1e-12 and _on_seg(a, c2, b):  return True
    return False


# ---------------------------------------------------------------------------
# Entity base
# ---------------------------------------------------------------------------

@dataclass
class BaseEntity:
    """Root class for all drawing entities.

    Subclasses must set ``type`` as a class-level default and implement
    ``to_dict`` / ``from_dict``.

    To participate in the automatic entity registry set a class-level
    ``_entity_kind`` ClassVar to the entity's type string::

        @dataclass
        class LineEntity(BaseEntity):
            _entity_kind: ClassVar[str] = "line"
            ...

    This causes the subclass to be registered in ``_ENTITY_REGISTRY``
    automatically when the module is first imported — no central mapping
    needs to be maintained.
    """

    # Subclasses override this ClassVar to register themselves.
    _entity_kind: ClassVar[str] = ""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    layer: str = "default"
    # Per-entity style overrides.  ``None`` means "ByLayer" — inherit from
    # the layer's settings.  Set to a concrete value to override.
    color: Optional[str]         = field(default=None, compare=False)
    line_weight: Optional[float] = field(default=None, compare=False)
    line_style: Optional[str]    = field(default=None, compare=False)

    # ------------------------------------------------------------------
    # Auto-registration
    # ------------------------------------------------------------------

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # ``_entity_kind`` is a ClassVar assignment, visible in __dict__
        # before @dataclass processes the class.
        kind = cls.__dict__.get("_entity_kind", "")
        if kind:
            _ENTITY_REGISTRY[kind] = cls

    # ------------------------------------------------------------------
    # Serialisation helpers (overridden by subclasses for their fields)
    # ------------------------------------------------------------------

    def _base_dict(self) -> Dict[str, Any]:
        """Return the base fields shared by every entity."""
        result: Dict[str, Any] = {"id": self.id, "type": self.type, "layer": self.layer}
        if self.color is not None:
            result["color"] = self.color
        if self.line_weight is not None:
            result["lineWeight"] = self.line_weight
        if self.line_style is not None:
            result["lineStyle"] = self.line_style
        return result

    def to_dict(self) -> Dict[str, Any]:
        return self._base_dict()

    @staticmethod
    def _base_kwargs(d: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the common constructor kwargs from a serialised dict.

        Subclass ``from_dict`` implementations can unpack the result
        (``**cls._base_kwargs(d)``) to avoid repeating the ``id`` /
        ``layer`` / ``line_weight`` / ``line_style`` extraction.
        """
        kwargs: Dict[str, Any] = {
            "id": d.get("id", str(uuid.uuid4())),
            "layer": d.get("layer", "default"),
        }
        ec = d.get("color")
        lw = d.get("lineWeight")
        ls = d.get("lineStyle")
        if ec is not None:
            kwargs["color"] = str(ec)
        if lw is not None:
            kwargs["line_weight"] = float(lw)
        if ls is not None:
            kwargs["line_style"] = str(ls)
        return kwargs

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BaseEntity":
        return cls(**cls._base_kwargs(d))

    def __repr__(self) -> str:          # noqa: D105
        return f"<{self.__class__.__name__} id={self.id!r}>"

    # ------------------------------------------------------------------
    # Entity protocol — override in every concrete subclass.
    #
    # These defaults are safe no-ops so that the protocol is non-breaking
    # for any existing subclass that has not yet been updated.  Each
    # implementation should be self-contained: adding a new entity type
    # only requires changes inside the new entity file.
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        """Return the axis-aligned bounding box in world space, or None."""
        return None

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        """Return True if *pt* is within *tolerance* world-units of this entity."""
        return False

    def snap_candidates(
        self,
        enabled: AbstractSet["SnapType"],  # noqa: F821 – resolved at runtime
    ) -> "List[SnapResult]":              # noqa: F821
        """Return cursor-independent snap candidates (endpoint/mid/centre/quad)."""
        return []

    def nearest_snap(self, cursor: Vec2) -> "Optional[SnapResult]":  # noqa: F821
        """Return the closest point on this entity's geometry to *cursor*."""
        return None

    def perp_snaps(self, from_pt: Vec2) -> "List[SnapResult]":  # noqa: F821
        """Return perpendicular-foot snap candidates from *from_pt* onto this entity."""
        return []

    def draw(
        self,
        painter: "QPainter",
        world_to_screen: "Callable[[QPointF], QPointF]",
        scale: float,
    ) -> None:
        """Render this entity onto *painter* using *world_to_screen* for the transform."""

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        """Return True if this entity's geometry intersects or is inside [rmin, rmax].

        The default implementation uses the bounding box as a conservative
        approximation — entities with curved or multi-segment geometry should
        override this for accurate crossing selection.
        """
        bb = self.bounding_box()
        if bb is None:
            return False
        sel = BBox(rmin.x, rmin.y, rmax.x, rmax.y)
        return sel.intersects(bb)

    # ------------------------------------------------------------------
    # Grip editing protocol
    # ------------------------------------------------------------------

    def grip_points(self) -> List[GripPoint]:
        """Return the list of grip points for this entity.

        Each concrete subclass should override this to return meaningful
        grips (endpoints, midpoints, centres, etc.).
        """
        return []

    def move_grip(self, index: int, new_pos: Vec2) -> None:
        """Move grip *index* to *new_pos*, mutating the entity in place.

        Subclasses must override this to handle each grip index returned
        by ``grip_points()``.
        """
