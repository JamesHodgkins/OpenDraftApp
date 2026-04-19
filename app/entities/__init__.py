"""
app.entities — drawing element models for OpenDraft.

All concrete entity classes are exported from this package.  The helper
``entity_from_dict`` deserialises any raw dict (as loaded from JSON) into
the correct typed entity object.

Entity classes register themselves automatically in ``_ENTITY_REGISTRY``
(defined in :mod:`app.entities.base`) via ``__init_subclass__``.  Importing
the concrete entity modules below is sufficient to populate the registry —
no manual mapping needs to be maintained here.
"""
from __future__ import annotations

from typing import Any, Dict

from app.entities.base import BaseEntity, Vec2, GripPoint, GripType, _ENTITY_REGISTRY
from app.entities.line import LineEntity
from app.entities.circle import CircleEntity
from app.entities.arc import ArcEntity
from app.entities.rectangle import RectangleEntity
from app.entities.polyline import PolylineEntity
from app.entities.text import TextEntity
from app.entities.dimension import DimensionEntity
from app.entities.hatch import HatchEntity
from app.entities.spline import SplineEntity
from app.entities.ellipse import EllipseEntity
from app.entities.point import PointEntity

__all__ = [
    "BaseEntity",
    "Vec2",
    "GripPoint",
    "GripType",
    "LineEntity",
    "CircleEntity",
    "ArcEntity",
    "RectangleEntity",
    "PolylineEntity",
    "TextEntity",
    "DimensionEntity",
    "HatchEntity",
    "SplineEntity",
    "EllipseEntity",
    "PointEntity",
    "entity_from_dict",
]


def entity_from_dict(d: Dict[str, Any]) -> BaseEntity:
    """Deserialise a raw dict into the appropriate typed entity.

    The mapping from ``type`` string to class is driven by ``_ENTITY_REGISTRY``
    in :mod:`app.entities.base`, which is populated automatically when each
    entity module is first imported.  Unknown ``type`` values fall back to a
    bare :class:`BaseEntity`.

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
