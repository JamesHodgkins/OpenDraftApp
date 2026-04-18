"""ViewportTransform — pan/zoom state and screen↔world coordinate conversion.

Extracted from CADCanvas so the transform math can be tested independently
of the Qt widget layer.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF


class ViewportTransform:
    """Owns pan/zoom state and provides screen↔world coordinate transforms.

    Attributes
    ----------
    scale:
        Pixels per world unit.
    offset:
        World coordinates at screen pixel (0, 0).
    """

    def __init__(self) -> None:
        self.scale: float = 1.0
        self.offset: QPointF = QPointF(0.0, 0.0)
        self._origin_anchor: str = "bottom-left"
        self._origin_inset_px: QPointF = QPointF(10.0, 10.0)
        self._origin_locked: bool = True

    # ------------------------------------------------------------------
    # Transforms
    # ------------------------------------------------------------------

    def screen_to_world(self, pt: QPointF) -> QPointF:
        return QPointF(
            pt.x() / self.scale + self.offset.x(),
            self.offset.y() - (pt.y() / self.scale),
        )

    def world_to_screen(self, pt: QPointF) -> QPointF:
        return QPointF(
            (pt.x() - self.offset.x()) * self.scale,
            (self.offset.y() - pt.y()) * self.scale,
        )

    # ------------------------------------------------------------------
    # Origin anchor
    # ------------------------------------------------------------------

    def set_origin_anchor(
        self,
        anchor: str = "bottom-left",
        inset_x_px: float = 0.0,
        inset_y_px: float = 0.0,
        lock: bool = True,
    ) -> None:
        anchor = anchor.lower()
        if anchor not in ("top-left", "top-right", "bottom-left", "bottom-right"):
            raise ValueError("invalid anchor")
        self._origin_anchor = anchor
        self._origin_inset_px = QPointF(float(inset_x_px), float(inset_y_px))
        self._origin_locked = bool(lock)

    def update_offset_for_size(self, w_px: int, h_px: int) -> None:
        """Recompute offset so world (0,0) maps to the configured anchor/inset."""
        ix = self._origin_inset_px.x()
        iy = self._origin_inset_px.y()
        s = max(self.scale, 1e-12)
        ox = (-ix / s) if self._origin_anchor.endswith("-left") else (-(w_px - ix) / s)
        oy = (iy / s) if self._origin_anchor.startswith("top-") else ((h_px - iy) / s)
        self.offset = QPointF(ox, oy)

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def zoom_on_point(self, cursor_screen: QPointF, factor: float) -> None:
        """Zoom in/out centred on *cursor_screen*, keeping the world point fixed."""
        world_before = self.screen_to_world(cursor_screen)
        self._origin_locked = False
        self.scale = max(0.0001, min(self.scale * factor, 1e6))
        world_after = self.screen_to_world(cursor_screen)
        self.offset += world_before - world_after

    # ------------------------------------------------------------------
    # Pan
    # ------------------------------------------------------------------

    def pan(self, dx_px: float, dy_px: float) -> None:
        """Pan by *dx_px*, *dy_px* screen pixels."""
        self._origin_locked = False
        self.offset.setX(self.offset.x() - dx_px / self.scale)
        self.offset.setY(self.offset.y() + dy_px / self.scale)
