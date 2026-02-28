"""
Unified colour model for OpenDraft.

A :class:`Color` can represent either:
* An **ACI indexed** colour (``Color(aci=3)``), or
* A **true colour** / custom hex (``Color(hex="#ff8800")``).

The canvas and serialisation layers use :meth:`to_hex` to resolve to a
concrete ``#RRGGBB`` string for rendering.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.colors.aci import aci_to_hex, aci_to_rgb, hex_to_nearest_aci, ACI_COLORS


@dataclass(frozen=True, slots=True)
class Color:
    """Immutable colour value.

    Exactly one of *aci* or *hex* should be set.
    * ``Color(aci=1)``   → ACI Red
    * ``Color(hex="#ff8800")`` → arbitrary true colour
    """

    aci: Optional[int] = None
    hex: Optional[str] = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_aci(cls, index: int) -> "Color":
        return cls(aci=index)

    @classmethod
    def from_hex(cls, hex_str: str) -> "Color":
        return cls(hex=hex_str.lower())

    @classmethod
    def from_string(cls, value: str) -> "Color":
        """Parse a colour string.

        Accepts:
        * ``"aci:N"``  — an ACI index
        * ``"#RRGGBB"`` — a hex colour
        * A bare ``"#RRGGBB"`` string (legacy)
        """
        if value.startswith("aci:"):
            return cls(aci=int(value[4:]))
        if value.startswith("#"):
            return cls(hex=value.lower())
        # Fallback: try parsing as int (bare ACI number)
        try:
            return cls(aci=int(value))
        except ValueError:
            return cls(hex=value.lower())

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to_hex(self) -> str:
        """Resolve to a ``#rrggbb`` hex string for rendering."""
        if self.aci is not None:
            return aci_to_hex(self.aci)
        return self.hex or "#ffffff"

    def to_rgb(self) -> tuple[int, int, int]:
        """Resolve to an (R, G, B) tuple."""
        if self.aci is not None:
            return aci_to_rgb(self.aci)
        h = (self.hex or "#ffffff").lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    @property
    def is_aci(self) -> bool:
        return self.aci is not None

    @property
    def display_name(self) -> str:
        """Human-readable label for UI display."""
        if self.aci is not None:
            _ACI_NAMES = {
                1: "Red", 2: "Yellow", 3: "Green", 4: "Cyan",
                5: "Blue", 6: "Magenta", 7: "White", 8: "Dark Grey",
                9: "Light Grey",
            }
            name = _ACI_NAMES.get(self.aci, "")
            return f"ACI {self.aci}" + (f" ({name})" if name else "")
        return self.hex or "#ffffff"

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_string(self) -> str:
        """Encode to a serialisable string.

        ACI colours become ``"aci:N"``; hex colours stay as ``"#rrggbb"``.
        """
        if self.aci is not None:
            return f"aci:{self.aci}"
        return self.hex or "#ffffff"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-friendly dict."""
        if self.aci is not None:
            return {"aci": self.aci}
        return {"hex": self.hex or "#ffffff"}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Color":
        if "aci" in d:
            return cls(aci=int(d["aci"]))
        return cls(hex=str(d.get("hex", "#ffffff")))

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        if self.aci is not None:
            return f"Color(aci={self.aci})"
        return f"Color(hex={self.hex!r})"
