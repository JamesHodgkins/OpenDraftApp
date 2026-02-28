"""Hatch entity — a filled or patterned region bounded by another entity."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Optional, TYPE_CHECKING

from app.entities.base import BaseEntity, Vec2

if TYPE_CHECKING:
    from app.entities.base import BBox


@dataclass
class HatchEntity(BaseEntity):
    """A hatch-fill applied to a closed boundary entity."""

    _entity_kind: ClassVar[str] = "hatch"
    type: str = field(default="hatch", init=False, repr=False)
    pattern: str = "solid"
    pattern_scale: float = 1.0
    pattern_angle: float = 0.0
    boundary: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolved_boundary(self) -> Optional[BaseEntity]:
        """Return the boundary deserialised as a concrete entity, or None."""
        if self.boundary is None:
            return None
        from app.entities import entity_from_dict
        return entity_from_dict(self.boundary)

    # ------------------------------------------------------------------
    # Entity protocol — delegate to the boundary entity
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional["BBox"]:
        b = self.resolved_boundary()
        return b.bounding_box() if b is not None else None

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        b = self.resolved_boundary()
        return b.hit_test(pt, tolerance) if b is not None else False

    def snap_candidates(self, enabled: AbstractSet) -> List:
        return []

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        return None

    def perp_snaps(self, from_pt: Vec2) -> List:
        return []

    def draw(self, painter, world_to_screen, scale: float) -> None:
        pass  # hatch fill rendering not yet implemented

    def crosses_rect(self, rmin: Vec2, rmax: Vec2) -> bool:
        b = self.resolved_boundary()
        return b.crosses_rect(rmin, rmax) if b is not None else False

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["pattern"] = self.pattern
        d["patternScale"] = self.pattern_scale
        d["patternAngle"] = self.pattern_angle
        d["boundary"] = self.boundary
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HatchEntity":
        return cls(
            **cls._base_kwargs(d),
            pattern=d.get("pattern", "solid"),
            pattern_scale=float(d.get("patternScale", 1.0)),
            pattern_angle=float(d.get("patternAngle", 0.0)),
            boundary=d.get("boundary"),
        )
