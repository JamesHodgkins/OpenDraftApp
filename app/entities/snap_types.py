"""
Shared snap types used by both entity classes and the OSNAP engine.

Keeping these in the *entities* package breaks the circular-import that
would arise if entity files imported from ``app.editor.osnap_engine``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.entities.base import Vec2


class SnapType(Enum):
    ENDPOINT      = "Endpoint"
    MIDPOINT      = "Midpoint"
    CENTER        = "Center"
    QUADRANT      = "Quadrant"
    NEAREST       = "Nearest"
    INTERSECTION  = "Intersection"
    PERPENDICULAR = "Perpendicular"


@dataclass
class SnapResult:
    """A resolved snap candidate ready for display and use."""
    point:     Vec2
    snap_type: SnapType
    entity_id: str = ""
