"""Dimension entities — linear and aligned annotations."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Literal

from app.entities.base import BaseEntity, Vec2

DimType = Literal["linear", "aligned"]
ArrowheadType = Literal["arrow", "dot", "tick", "none"]
TextPosition = Literal["above", "inline", "below"]


@dataclass
class DimensionEntity(BaseEntity):
    """A linear or aligned dimension annotation.

    Geometry
    --------
    ``p1`` and ``p2`` are the two measurement points (annotation origins).
    ``p3`` is the dimension-line offset point — it controls how far the
    dimension line sits away from the measured geometry.

    Attributes
    ----------
    dim_type:        ``"linear"`` (horizontal/vertical) or ``"aligned"``
                     (parallel to the p1–p2 vector).
    text_height:     Height of the dimension text in world units.
    arrowhead_type:  Style of the arrowhead terminator.
    arrowhead_size:  Size of the arrowhead in world units.
    text_position:   Where the text sits relative to the dimension line.
    text_offset:     Additional offset applied to the text along the
                     dimension line normal.
    """

    type: str = field(default="dimension", init=False, repr=False)
    p1: Vec2 = field(default_factory=Vec2)
    p2: Vec2 = field(default_factory=Vec2)
    p3: Vec2 = field(default_factory=Vec2)
    dim_type: DimType = "linear"
    text_height: float = 2.5
    arrowhead_type: ArrowheadType = "arrow"
    arrowhead_size: float = 2.5
    text_position: TextPosition = "above"
    text_offset: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["p1"] = self.p1.to_dict()
        d["p2"] = self.p2.to_dict()
        d["p3"] = self.p3.to_dict()
        d["dimType"] = self.dim_type
        d["textHeight"] = self.text_height
        d["arrowheadType"] = self.arrowhead_type
        d["arrowheadSize"] = self.arrowhead_size
        d["textPosition"] = self.text_position
        d["textOffset"] = self.text_offset
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DimensionEntity":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            layer=d.get("layer", "default"),
            p1=Vec2.from_dict(d["p1"]),
            p2=Vec2.from_dict(d["p2"]),
            p3=Vec2.from_dict(d["p3"]),
            dim_type=d.get("dimType", "linear"),
            text_height=float(d.get("textHeight", 2.5)),
            arrowhead_type=d.get("arrowheadType", "arrow"),
            arrowhead_size=float(d.get("arrowheadSize", 2.5)),
            text_position=d.get("textPosition", "above"),
            text_offset=float(d.get("textOffset", 0.0)),
        )
