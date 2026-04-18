"""GridRenderer — adaptive multi-level grid painting.

Extracted from CADCanvas so the grid algorithm can be read and modified
without navigating the full 1 400-line canvas file.
"""
from __future__ import annotations

from math import floor, log10

from PySide6.QtCore import QLine, QPointF
from PySide6.QtGui import QColor, QPainter, QPen

from app.canvas_viewport import ViewportTransform


class GridRenderer:
    """Draws the smooth multi-level adaptive grid onto a QPainter."""

    # Fade thresholds in screen pixels
    _FADE_IN   = 2.0
    _FADE_FULL = 50.0
    _MAX_LINES_PER_LEVEL = 400

    def __init__(self, viewport: ViewportTransform) -> None:
        self._vp = viewport

    def draw(self, painter: QPainter, w: int, h: int) -> None:
        """Paint the grid and world-origin axes onto *painter*."""
        vp = self._vp
        tl = vp.screen_to_world(QPointF(0, 0))
        br = vp.screen_to_world(QPointF(w, h))
        wx_min = min(tl.x(), br.x())
        wx_max = max(tl.x(), br.x())
        wy_min = min(tl.y(), br.y())
        wy_max = max(tl.y(), br.y())

        nice_spacings = self._build_spacings(vp.scale, w, h, wx_min, wx_max, wy_min, wy_max)
        self._draw_levels(painter, vp, nice_spacings, w, h, wx_min, wx_max, wy_min, wy_max)
        self._draw_axes(painter, vp, w, h)

    # ------------------------------------------------------------------

    def _alpha_for_spacing(self, world_spacing: float, scale: float) -> float:
        px = world_spacing * scale
        if px <= self._FADE_IN:
            return 0.02
        if px >= self._FADE_FULL:
            return 1.0
        t = (px - self._FADE_IN) / (self._FADE_FULL - self._FADE_IN)
        return max(0.0, min(1.0, t ** 0.6))

    def _build_spacings(
        self, scale: float, w: int, h: int,
        wx_min: float, wx_max: float, wy_min: float, wy_max: float,
    ) -> list[float]:
        min_world = max(self._FADE_IN / scale, 1e-9)
        max_world = max(w, h) * 4.0 / scale
        low_exp  = int(floor(log10(min_world))) - 1
        high_exp = int(floor(log10(max(max_world, 1e-9)))) + 2

        spacings: list[float] = []
        for exp in range(low_exp, high_exp + 1):
            for mant in (1, 5):
                s = mant * (10.0 ** exp)
                if min_world * 0.5 <= s <= max_world * 2.0:
                    spacings.append(s)
        spacings.sort()

        if len(spacings) > 4:
            spacings = sorted(spacings, key=lambda s: self._alpha_for_spacing(s, scale), reverse=True)[:4]
            spacings.sort()
        return spacings

    def _draw_levels(
        self, painter: QPainter, vp: ViewportTransform,
        spacings: list[float], w: int, h: int,
        wx_min: float, wx_max: float, wy_min: float, wy_max: float,
    ) -> None:
        log_fade_full = log10(self._FADE_FULL)
        log_bright    = log10(self._FADE_FULL * 10.0)

        for spacing in spacings:
            a = self._alpha_for_spacing(spacing, vp.scale)
            if a <= 0.0:
                continue

            a_int   = max(0, min(160, int(a * 160)))
            px_size = spacing * vp.scale
            brightness_t = min(1.0, max(0.0,
                (log10(max(px_size, 1e-9)) - log_fade_full) / (log_bright - log_fade_full)
            ))
            brightness = int(38 + brightness_t * 22)

            pen = QPen(QColor(brightness, brightness, brightness, a_int), 1)
            painter.setPen(pen)

            start_x   = floor(wx_min / spacing) * spacing
            num_vert  = int((wx_max - wx_min) / spacing) + 4
            start_y   = floor(wy_min / spacing) * spacing
            num_horiz = int((wy_max - wy_min) / spacing) + 4
            total     = num_vert + num_horiz
            stride    = max(1, int(total / self._MAX_LINES_PER_LEVEL))

            vert_lines: list[QLine] = []
            horiz_lines: list[QLine] = []

            for iv in range(0, num_vert, stride):
                x = start_x + iv * spacing
                if x > wx_max + spacing:
                    break
                if int(round(x / spacing)) == 0:
                    continue
                sx = int((x - vp.offset.x()) * vp.scale)
                vert_lines.append(QLine(sx, 0, sx, h))

            for ih in range(0, num_horiz, stride):
                y = start_y + ih * spacing
                if y > wy_max + spacing:
                    break
                if int(round(y / spacing)) == 0:
                    continue
                sy = int((vp.offset.y() - y) * vp.scale)
                horiz_lines.append(QLine(0, sy, w, sy))

            if vert_lines:
                painter.drawLines(vert_lines)
            if horiz_lines:
                painter.drawLines(horiz_lines)

    def _draw_axes(self, painter: QPainter, vp: ViewportTransform, w: int, h: int) -> None:
        ox = (0.0 - vp.offset.x()) * vp.scale
        oy = (vp.offset.y() - 0.0) * vp.scale
        painter.setPen(QPen(QColor(80, 80, 80, 200), 1))
        painter.drawLine(int(ox), 0, int(ox), h)
        painter.drawLine(0, int(oy), w, int(oy))
