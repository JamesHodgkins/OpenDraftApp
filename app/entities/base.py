"""
Base types shared by all drawing entities.

Provides Vec2 (a simple 2-D point/vector) and BaseEntity, the abstract
root from which every concrete entity inherits.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


# ---------------------------------------------------------------------------
# 2-D coordinate helper
# ---------------------------------------------------------------------------

@dataclass
class Vec2:
    """An immutable-friendly 2-D point or vector."""
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
# Entity base
# ---------------------------------------------------------------------------

@dataclass
class BaseEntity:
    """Root class for all drawing entities.

    Subclasses must set ``type`` as a class-level default and implement
    ``to_dict`` / ``from_dict``.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    layer: str = "default"

    # ------------------------------------------------------------------
    # Serialisation helpers (overridden by subclasses for their fields)
    # ------------------------------------------------------------------

    def _base_dict(self) -> Dict[str, Any]:
        """Return the base fields shared by every entity."""
        return {"id": self.id, "type": self.type, "layer": self.layer}

    def to_dict(self) -> Dict[str, Any]:
        return self._base_dict()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BaseEntity":
        return cls(id=d.get("id", str(uuid.uuid4())), layer=d.get("layer", "default"))

    def __repr__(self) -> str:          # noqa: D105
        return f"<{self.__class__.__name__} id={self.id!r}>"
