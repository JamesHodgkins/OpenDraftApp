"""Text entity — a single-line text annotation at a 2-D position."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Literal, Optional

from app.entities.base import BaseEntity, BBox, Vec2

HAlign = Literal["left", "center", "right"]
VAlign = Literal["top", "middle", "bottom", "baseline"]


@dataclass
class TextEntity(BaseEntity):
    """A single-line text label placed at a world-space position."""

    _entity_kind: ClassVar[str] = "text"
    type: str = field(default="text", init=False, repr=False)
    text: str = ""
    position: Vec2 = field(default_factory=Vec2)
    height: float = 2.5
    align: HAlign = "left"
    vertical_align: VAlign = "bottom"
    justify: HAlign = "left"
    font_family: str = "Arial"
    font_style: str = ""
    letter_spacing: float = 0.0
    rotation: float = 0.0

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        # Approximate: width ≈ character-count × 0.6 × height
        w = len(self.text) * 0.6 * self.height
        h = self.height
        px, py = self.position.x, self.position.y
        return BBox(px, py, px + w, py + h)

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        bb = self.bounding_box()
        if bb is None:
            return False
        return (bb.min_x - tolerance <= pt.x <= bb.max_x + tolerance and
                bb.min_y - tolerance <= pt.y <= bb.max_y + tolerance)

    def snap_candidates(self, enabled: AbstractSet) -> List:
        return []   # text has no geometric snap points

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        return None

    def perp_snaps(self, from_pt: Vec2) -> List:
        return []

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF
        sp = world_to_screen(QPointF(self.position.x, self.position.y))
        painter.drawText(sp.x(), sp.y(), self.text)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["text"] = self.text
        d["position"] = self.position.to_dict()
        d["height"] = self.height
        d["align"] = self.align
        d["verticalAlign"] = self.vertical_align
        d["justify"] = self.justify
        d["fontFamily"] = self.font_family
        d["fontStyle"] = self.font_style
        d["letterSpacing"] = self.letter_spacing
        d["rotation"] = self.rotation
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TextEntity":
        return cls(
            **cls._base_kwargs(d),
            text=d.get("text", ""),
            position=Vec2.from_dict(d["position"]),
            height=float(d.get("height", 2.5)),
            align=d.get("align", "left"),
            vertical_align=d.get("verticalAlign", "bottom"),
            justify=d.get("justify", "left"),
            font_family=d.get("fontFamily", "Arial"),
            font_style=d.get("fontStyle", ""),
            letter_spacing=float(d.get("letterSpacing", 0.0)),
            rotation=float(d.get("rotation", 0.0)),
        )
