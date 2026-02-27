"""Text entity — a single-line text annotation at a 2-D position."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

from app.entities.base import BaseEntity, Vec2

HAlign = Literal["left", "center", "right"]
VAlign = Literal["top", "middle", "bottom", "baseline"]


@dataclass
class TextEntity(BaseEntity):
    """A single-line text label placed at a world-space position.

    Attributes
    ----------
    text:           The string content to display.
    position:       Anchor point in world coordinates.
    height:         Cap height of the text in world units.
    align:          Horizontal alignment of the anchor within the text box.
    vertical_align: Vertical alignment of the anchor within the text box.
    justify:        Text justification (left / center / right).
    font_family:    Font family name (e.g. ``"Arial"``).
    font_style:     CSS-style modifier string (e.g. ``"Bold Italic"``).
    letter_spacing: Extra letter-spacing in world units.
    rotation:       Counter-clockwise rotation in degrees.
    """

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
            id=d.get("id", str(uuid.uuid4())),
            layer=d.get("layer", "default"),
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
