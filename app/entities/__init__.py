"""
app.entities — drawing element models for OpenDraft.

All concrete entity classes are exported from this package.  The helper
``entity_from_dict`` deserialises any raw dict (as loaded from JSON) into
the correct typed entity object.
"""
from __future__ import annotations

from typing import Any, Dict

from app.entities.base import BaseEntity, Vec2
from app.entities.line import LineEntity
from app.entities.circle import CircleEntity
from app.entities.arc import ArcEntity
from app.entities.rectangle import RectangleEntity
from app.entities.polyline import PolylineEntity
from app.entities.text import TextEntity
from app.entities.dimension import DimensionEntity
from app.entities.hatch import HatchEntity

__all__ = [
    "BaseEntity",
    "Vec2",
    "LineEntity",
    "CircleEntity",
    "ArcEntity",
    "RectangleEntity",
    "PolylineEntity",
    "TextEntity",
    "DimensionEntity",
    "HatchEntity",
    "entity_from_dict",
]

# ---------------------------------------------------------------------------
# Type → class registry
# ---------------------------------------------------------------------------

_ENTITY_REGISTRY: Dict[str, type] = {
    "line":      LineEntity,
    "circle":    CircleEntity,
    "arc":       ArcEntity,
    "rect":      RectangleEntity,
    "polyline":  PolylineEntity,
    "text":      TextEntity,
    "dimension": DimensionEntity,
    "hatch":     HatchEntity,
}


def entity_from_dict(d: Dict[str, Any]) -> BaseEntity:
    """Deserialise a raw dict into the appropriate typed entity.

    Unknown ``type`` values fall back to a bare :class:`BaseEntity`.

    Parameters
    ----------
    d:
        A dictionary, typically parsed from JSON, that contains at minimum
        a ``"type"`` key identifying the entity kind.

    Returns
    -------
    BaseEntity
        A fully-typed entity instance populated from *d*.
    """
    entity_type = d.get("type", "")
    cls = _ENTITY_REGISTRY.get(entity_type, BaseEntity)
    return cls.from_dict(d)
