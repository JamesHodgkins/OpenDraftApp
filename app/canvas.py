"""
CAD Canvas widget — the main drawing surface with a viewport.

Provides basic pan/zoom, screen<->world transforms and a smooth adaptive grid
that fades between density levels as you zoom, giving a continuous sense of
scale rather than snapping between states.
"""
from math import log10, floor, ceil, pi

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, Signal, Slot
from typing import List, Optional

from app.document import DocumentStore
from app.entities import Vec2
from app.editor.osnap_engine import OsnapEngine, SnapResult, SnapType


class CADCanvas(QWidget):
    """Viewport-enabled CAD canvas with pan/zoom and grid drawing."""

    # emits world x,y when the mouse moves over the canvas
    mouseMoved = Signal(float, float)
    # emits the world-space point the user clicked (left button)
    pointSelected = Signal(float, float)
    # emits when the user presses Escape
    cancelRequested = Signal()

    @Slot()
    def refresh(self) -> None:
        """Schedule a repaint.  Safe to call from any thread via QueuedConnection."""
        # If the editor no longer has a dynamic callback, clear stale preview.
        if self._editor is not None and self._editor._dynamic_callback is None:
            self._preview_entities = []
        self.update()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)

        # View transform state
        self.scale = 1.0  # pixels per world unit
        self.offset = QPointF(0.0, 0.0)  # world coordinates at screen (0,0)

        # Interaction state
        self._panning = False
        self._last_mouse_pos = QPoint()

        # UI niceties
        self.setCursor(Qt.CrossCursor)

        # receive mouse move events even when no button is pressed
        self.setMouseTracking(True)

        # Accept keyboard focus so key-press events (Escape, etc.) are received
        self.setFocusPolicy(Qt.StrongFocus)

        # Document reference (set by MainWindow)
        self._document: Optional[DocumentStore] = None

        # Editor reference — used to query rubberband preview on mouse move.
        # Set by MainWindow after constructing the editor.
        self._editor = None
        # Cached preview entities from the last mouse-move callback.
        self._preview_entities: List = []

        # OSNAP engine — active whenever the editor is waiting for a point input.
        self._osnap: OsnapEngine = OsnapEngine()
        # Last computed snap result (None when no snap is within aperture).
        self._snap_result: Optional[SnapResult] = None

    # ----------------------
    # Coordinate transforms
    # ----------------------
    def screen_to_world(self, pt: QPointF) -> QPointF:
        # Inverted Y: screen y grows downwards, world y grows upwards
        return QPointF(pt.x() / self.scale + self.offset.x(), self.offset.y() - (pt.y() / self.scale))

    def world_to_screen(self, pt: QPointF) -> QPointF:
        # Inverted Y: convert world y to screen y by subtracting from offset
        return QPointF((pt.x() - self.offset.x()) * self.scale, (self.offset.y() - pt.y()) * self.scale)

    # ----------------------
    # Event handling
    # ----------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        # Left click — emit a world-space point for the active command.
        if event.button() == Qt.LeftButton:
            posf = event.position() if hasattr(event, "position") else event.posF()
            world_pt = self.screen_to_world(posf)
            # If a snap candidate is active, use it instead of the raw cursor.
            if self._snap_result is not None:
                pt = self._snap_result.point
                self.pointSelected.emit(pt.x, pt.y)
            else:
                self.pointSelected.emit(world_pt.x(), world_pt.y())
            # Give the canvas focus so subsequent key events (Escape) are routed here.
            self.setFocus()
            return

        # start panning with middle mouse button
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        posf = event.position() if hasattr(event, "position") else event.posF()
        world_pt = self.screen_to_world(posf)
        raw = Vec2(world_pt.x(), world_pt.y())

        # ---- OSNAP --------------------------------------------------------
        # Only run snap when the editor is expecting a point input.
        snap_active = (
            self._editor is not None
            and getattr(self._editor, "_input_mode", "none") == "point"
            and self._document is not None
        )
        if snap_active:
            self._snap_result = self._osnap.snap(
                raw, self._document, self.scale,
                from_point=getattr(self._editor, "snap_from_point", None),
            )
        else:
            self._snap_result = None

        # Coordinate display follows the snapped position when snap is active.
        display = self._snap_result.point if self._snap_result else raw
        try:
            self.mouseMoved.emit(display.x, display.y)
        except Exception:
            pass

        # Update rubberband preview using snapped position when available.
        if self._editor is not None:
            preview_pt = self._snap_result.point if self._snap_result else raw
            self._preview_entities = self._editor.get_dynamic(preview_pt)

        self.update()

        if self._panning:
            pos = event.pos()
            dx = pos.x() - self._last_mouse_pos.x()
            dy = pos.y() - self._last_mouse_pos.y()
            # update offset so that content moves with the drag
            # x behaves as before; y sign is inverted for world coordinates
            self.offset.setX(self.offset.x() - dx / self.scale)
            self.offset.setY(self.offset.y() + dy / self.scale)
            self._last_mouse_pos = QPoint(pos)
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CrossCursor)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.cancelRequested.emit()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        # Zoom centered on mouse cursor
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.25 if delta > 0 else 0.8

        # cursor in widget coordinates -> world coordinates before zoom
        cursor_pos = event.position() if hasattr(event, "position") else event.posF()
        world_before = self.screen_to_world(cursor_pos)

        # apply zoom
        self.scale *= factor
        # clamp scale to reasonable range
        self.scale = max(0.0001, min(self.scale, 1e6))

        # adjust offset so the world point under cursor stays fixed
        world_after = self.screen_to_world(cursor_pos)
        self.offset += (world_before - world_after)
        self.update()

    # ----------------------
    # Drawing
    # ----------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1E1E1E"))
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Draw grid
        self._draw_grid(painter)

        # Draw document entities
        if self._document is not None:
            pen = QPen(QColor(220, 220, 220), 1)
            painter.setPen(pen)
            for e in self._document:
                self._draw_entity(painter, e)

        # Draw dynamic / rubberband preview entities
        if self._preview_entities:
            preview_pen = QPen(QColor(0, 191, 255), 1)
            painter.setPen(preview_pen)
            for e in self._preview_entities:
                self._draw_entity(painter, e)

        # Draw OSNAP marker
        if self._snap_result is not None:
            self._draw_snap_marker(painter, self._snap_result)

    def _draw_snap_marker(self, painter: QPainter, snap: SnapResult) -> None:
        """Draw the OSNAP marker at the snap point in screen coordinates.

        Matches the web version: orange stroke-only shapes, 2 px line width,
        fixed 6 px half-size aperture, no fill, no label.
        """
        sp = self.world_to_screen(QPointF(snap.point.x, snap.point.y))
        sx, sy = sp.x(), sp.y()
        S = 6  # half-size in pixels (matches web's  6 / zoom  at zoom=1)

        orange = QColor(0xF9, 0x73, 0x16)  # #f97316

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(orange, 2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        t = snap.snap_type

        if t == SnapType.ENDPOINT:
            # Stroke-only square
            painter.drawRect(int(sx - S), int(sy - S), S * 2, S * 2)

        elif t == SnapType.MIDPOINT:
            # Upward-pointing triangle: apex top, base bottom
            triangle = QPolygonF([
                QPointF(sx,      sy - S),   # apex
                QPointF(sx - S,  sy + S),   # bottom-left
                QPointF(sx + S,  sy + S),   # bottom-right
            ])
            painter.drawPolygon(triangle)

        elif t == SnapType.CENTER:
            # Stroke-only circle
            painter.drawEllipse(QPointF(sx, sy), S, S)

        elif t == SnapType.QUADRANT:
            # Diamond (not in web version; keep as a sensible extra)
            diamond = QPolygonF([
                QPointF(sx,      sy - S),
                QPointF(sx + S,  sy),
                QPointF(sx,      sy + S),
                QPointF(sx - S,  sy),
            ])
            painter.drawPolygon(diamond)

        elif t == SnapType.INTERSECTION:
            # X with a bounding square cap (nearest style from web)
            painter.drawLine(QPointF(sx - S, sy - S), QPointF(sx + S, sy + S))
            painter.drawLine(QPointF(sx + S, sy - S), QPointF(sx - S, sy + S))
            painter.drawLine(QPointF(sx - S, sy - S), QPointF(sx + S, sy - S))
            painter.drawLine(QPointF(sx - S, sy + S), QPointF(sx + S, sy + S))

        elif t == SnapType.PERPENDICULAR:
            # Two L-shapes (matches web version exactly): top-right + bottom-left corners
            # top-right L
            painter.drawLine(QPointF(sx,       sy + S), QPointF(sx + S, sy + S))
            painter.drawLine(QPointF(sx + S,   sy + S), QPointF(sx + S, sy))
            # bottom-left L
            painter.drawLine(QPointF(sx,       sy - S), QPointF(sx - S, sy - S))
            painter.drawLine(QPointF(sx - S,   sy - S), QPointF(sx - S, sy))

        elif t == SnapType.NEAREST:
            # X with top and bottom horizontal bars (matches web nearest)
            painter.drawLine(QPointF(sx - S, sy - S), QPointF(sx + S, sy + S))
            painter.drawLine(QPointF(sx + S, sy - S), QPointF(sx - S, sy + S))
            painter.drawLine(QPointF(sx - S, sy - S), QPointF(sx + S, sy - S))
            painter.drawLine(QPointF(sx - S, sy + S), QPointF(sx + S, sy + S))

        painter.restore()

    def _draw_entity(self, painter: QPainter, e) -> None:
        """Draw a single entity using the painter's current pen."""
        try:
            t = getattr(e, "type", "")
            if t == "line":
                p1 = QPointF(e.p1.x, e.p1.y)
                p2 = QPointF(e.p2.x, e.p2.y)
                s1 = self.world_to_screen(p1)
                s2 = self.world_to_screen(p2)
                painter.drawLine(s1.x(), s1.y(), s2.x(), s2.y())

            elif t == "circle":
                c = QPointF(e.center.x, e.center.y)
                sc = self.world_to_screen(c)
                r_px = e.radius * self.scale
                rect = QRectF(sc.x() - r_px, sc.y() - r_px, 2 * r_px, 2 * r_px)
                painter.drawEllipse(rect)

            elif t == "rect":
                p1 = QPointF(e.p1.x, e.p1.y)
                p2 = QPointF(e.p2.x, e.p2.y)
                s1 = self.world_to_screen(p1)
                s2 = self.world_to_screen(p2)
                left = min(s1.x(), s2.x())
                top = min(s1.y(), s2.y())
                w = abs(s2.x() - s1.x())
                h = abs(s2.y() - s1.y())
                painter.drawRect(int(left), int(top), int(w), int(h))

            elif t == "polyline":
                pts = [self.world_to_screen(QPointF(p.x, p.y)) for p in e.points]
                if len(pts) >= 2:
                    for i in range(len(pts) - 1):
                        a = pts[i]
                        b = pts[i + 1]
                        painter.drawLine(a.x(), a.y(), b.x(), b.y())
                    if getattr(e, "closed", False):
                        a = pts[-1]
                        b = pts[0]
                        painter.drawLine(a.x(), a.y(), b.x(), b.y())

            elif t == "text":
                pos = QPointF(e.position.x, e.position.y)
                sp = self.world_to_screen(pos)
                painter.drawText(sp.x(), sp.y(), e.text)

            elif t == "arc":
                sc = self.world_to_screen(QPointF(e.center.x, e.center.y))
                r_px = e.radius * self.scale
                rect = QRectF(sc.x() - r_px, sc.y() - r_px, 2 * r_px, 2 * r_px)
                start_deg = e.start_angle * 180.0 / pi
                end_deg   = e.end_angle   * 180.0 / pi
                span = (end_deg - start_deg) % 360.0 if e.ccw else -((start_deg - end_deg) % 360.0)
                painter.drawArc(rect, int(start_deg * 16), int(span * 16))
        except Exception:
            import traceback; traceback.print_exc()

    def _draw_grid(self, painter: QPainter) -> None:
        """
        Draw a smooth multi-level adaptive grid.

        Every nice-number spacing (1, 2, 5, 10, 20, 50, …) is drawn
        simultaneously.  Each level's opacity is driven by its current pixel
        spacing: lines fade in from transparent as you zoom in and fade back
        out as they compress together, giving a continuous visual sense of
        scale instead of a jarring snap.

        Visual hierarchy is preserved: coarser levels are drawn brighter so
        the eye always has a dominant reference scale.
        """
        w, h = self.width(), self.height()

        # World extents of the viewport
        tl = self.screen_to_world(QPointF(0, 0))
        br = self.screen_to_world(QPointF(w, h))
        wx_min, wx_max = min(tl.x(), br.x()), max(tl.x(), br.x())
        wy_min, wy_max = min(tl.y(), br.y()), max(tl.y(), br.y())

        # ── Fade thresholds (pixels) ──────────────────────────────────────
        # A grid level is invisible when its lines are < FADE_IN px apart
        # and fully opaque when they are >= FADE_FULL px apart.
        FADE_IN   = 14.0
        FADE_FULL = 70.0

        def alpha_for_spacing(world_spacing: float) -> float:
            px = world_spacing * self.scale
            if px <= FADE_IN:
                return 0.0
            if px >= FADE_FULL:
                return 1.0
            # Smooth S-curve (smoothstep) for a more natural transition
            t = (px - FADE_IN) / (FADE_FULL - FADE_IN)
            return t * t * (3.0 - 2.0 * t)

        # ── Build the list of nice spacings to consider ───────────────────
        # Include all levels whose pixel spacing is above FADE_IN (invisible
        # ones are cheaply skipped).  Cap the upper end so we don't iterate
        # billions of world-units for trivial off-screen lines.
        min_world = max(FADE_IN / self.scale, 1e-9)
        max_world = max(w, h) * 4.0 / self.scale   # generous, ~4× viewport

        if min_world <= 0:
            low_exp = -6
        else:
            low_exp = int(floor(log10(min_world))) - 1
        high_exp = int(floor(log10(max(max_world, 1e-9)))) + 2

        # Only mantissas 1 and 5 so every transition ratio is either ×5 or ×2.
        # This ensures every coarser grid line falls exactly ON a finer grid
        # line (clean subdivision) — no misalignment at any transition.
        # The 1,2,5 sequence has ×2.5 gaps (2→5) where lines fall *between*
        # each other, causing the "every other transition misaligns" problem.
        nice_spacings: list[float] = []
        for exp in range(low_exp, high_exp + 1):
            for mant in (1, 5):
                s = mant * (10.0 ** exp)
                if min_world * 0.5 <= s <= max_world * 2.0:
                    nice_spacings.append(s)
        nice_spacings.sort()

        # ── Draw each level, finest first (coarser paints on top) ─────────
        # Brightness: coarser (larger px_size) should be visibly brighter.
        # Map log(px_size) linearly from FADE_FULL (dim) to 10×FADE_FULL (bright).
        log_fade_full = log10(FADE_FULL)
        log_bright    = log10(FADE_FULL * 10.0)   # 1 decade above fully-opaque threshold

        for spacing in nice_spacings:
            a = alpha_for_spacing(spacing)
            if a <= 0.0:
                continue

            a_int = max(0, min(255, int(a * 255)))

            px_size = spacing * self.scale
            brightness_t = min(1.0, max(0.0,
                (log10(max(px_size, 1e-9)) - log_fade_full) / (log_bright - log_fade_full)
            ))
            brightness = int(28 + brightness_t * 42)

            pen = QPen(QColor(brightness, brightness, brightness, a_int), 1)
            painter.setPen(pen)

            # Vertical lines
            start_x = floor(wx_min / spacing) * spacing
            x = start_x
            guard = int((wx_max - wx_min) / spacing) + 4
            i = 0
            while x <= wx_max + spacing and i < guard:
                idx = int(round(x / spacing))
                if idx != 0:   # axis is drawn separately
                    sx = (x - self.offset.x()) * self.scale
                    painter.drawLine(int(sx), 0, int(sx), h)
                x += spacing
                i += 1

            # Horizontal lines
            start_y = floor(wy_min / spacing) * spacing
            y = start_y
            guard = int((wy_max - wy_min) / spacing) + 4
            i = 0
            while y <= wy_max + spacing and i < guard:
                idx = int(round(y / spacing))
                if idx != 0:
                    sy = (self.offset.y() - y) * self.scale
                    painter.drawLine(0, int(sy), w, int(sy))
                y += spacing
                i += 1

        # ── World-origin axes (always on top) ─────────────────────────────
        ox = (0.0 - self.offset.x()) * self.scale
        oy = (self.offset.y() - 0.0) * self.scale
        axis_pen = QPen(QColor(180, 80, 80, 200), 1)
        painter.setPen(axis_pen)
        painter.drawLine(int(ox), 0, int(ox), h)
        painter.drawLine(0, int(oy), w, int(oy))

