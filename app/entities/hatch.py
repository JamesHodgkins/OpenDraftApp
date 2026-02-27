"""Hatch entity — a filled or patterned region bounded by another entity."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, TYPE_CHECKING

from app.entities.base import BaseEntity

if TYPE_CHECKING:
    # avoid circular import at runtime; used only for type hints
    from app.entities import entity_from_dict


@dataclass
class HatchEntity(BaseEntity):
    """A hatch-fill applied to a closed boundary entity.

    Attributes
    ----------
    pattern:       Named hatch pattern, e.g. ``"solid"``, ``"ANSI31"``.
    pattern_scale: Uniform scale applied to the pattern geometry.
    pattern_angle: Rotation of the pattern in degrees.
    boundary:      The closed entity (rect, circle, polyline …) that forms
                   the hatch boundary.  Stored as a raw dict so this module
                   does not need to know all entity types at import time;
                   call ``resolved_boundary()`` to deserialise it.
    """

    type: str = field(default="hatch", init=False, repr=False)
    pattern: str = "solid"
    pattern_scale: float = 1.0
    pattern_angle: float = 0.0
    boundary: Optional[Dict[str, Any]] = None  # raw dict; see resolved_boundary()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolved_boundary(self) -> Optional[BaseEntity]:
        """Return the boundary deserialised as a concrete entity, or None."""
        if self.boundary is None:
            return None
        # import here to avoid circular imports at module load time
        from app.entities import entity_from_dict
        return entity_from_dict(self.boundary)

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
            id=d.get("id", str(uuid.uuid4())),
            layer=d.get("layer", "default"),
            pattern=d.get("pattern", "solid"),
            pattern_scale=float(d.get("patternScale", 1.0)),
            pattern_angle=float(d.get("patternAngle", 0.0)),
            boundary=d.get("boundary"),  # keep as raw dict
        )
