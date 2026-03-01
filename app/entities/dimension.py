"""Dimension entities — linear and aligned annotations."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Literal, Optional

from app.entities.base import BaseEntity, BBox, Vec2, _geo_pt_seg_dist

DimType = Literal["linear", "aligned"]
ArrowheadType = Literal["arrow", "dot", "tick", "none"]
TextPosition = Literal["above", "inline", "below"]


@dataclass
class DimensionEntity(BaseEntity):
    """A linear or aligned dimension annotation."""

    _entity_kind: ClassVar[str] = "dimension"
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

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        xs = [self.p1.x, self.p2.x, self.p3.x]
        ys = [self.p1.y, self.p2.y, self.p3.y]
        return BBox(min(xs), min(ys), max(xs), max(ys))

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        for a, b in [(self.p1, self.p2), (self.p1, self.p3), (self.p2, self.p3)]:
            if _geo_pt_seg_dist(pt, a, b) <= tolerance:
                return True
        return False

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        if SnapType.ENDPOINT in enabled:
            for p in (self.p1, self.p2, self.p3):
                results.append(SnapResult(Vec2(p.x, p.y), SnapType.ENDPOINT, self.id))
        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        return None  # complex geometry — not implemented

    def perp_snaps(self, from_pt: Vec2) -> List:
        return []

    def draw(self, painter, world_to_screen, scale: float) -> None:
        pass  # dimension rendering not yet implemented

    # ------------------------------------------------------------------
    # Grip editing
    # ------------------------------------------------------------------

    def grip_points(self):
        from app.entities.base import GripPoint, GripType
        return [
            GripPoint(self.p1, self.id, 0, GripType.ENDPOINT),
            GripPoint(self.p2, self.id, 1, GripType.ENDPOINT),
            GripPoint(self.p3, self.id, 2, GripType.ENDPOINT),
        ]

    def move_grip(self, index: int, new_pos: Vec2) -> None:
        if index == 0:
            self.p1 = new_pos
        elif index == 1:
            self.p2 = new_pos
        elif index == 2:
            self.p3 = new_pos

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

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
            **cls._base_kwargs(d),
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
