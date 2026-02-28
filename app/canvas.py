"""
CAD Canvas widget — the main drawing surface with a viewport.

Provides basic pan/zoom, screen<->world transforms and a smooth adaptive grid
that fades between density levels as you zoom, giving a continuous sense of
scale rather than snapping between states.
"""
from math import log10, floor, ceil

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF, QBrush, QPixmap
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, Signal, Slot, QLine


# ---------------------------------------------------------------------------
# Colour resolution helper
# ---------------------------------------------------------------------------
def _resolve_color_str(color_str: str) -> QColor:
    """Resolve a colour string to a QColor.

    Accepts ``"aci:N"`` (ACI indexed) and plain ``"#rrggbb"`` hex strings.
    """
    try:
        from app.colors.color import Color
        return QColor(Color.from_string(color_str).to_hex())
    except Exception:
        return QColor(color_str)

# ---------------------------------------------------------------------------
# Line-style helper
# ---------------------------------------------------------------------------
_LINE_STYLE_MAP = {
    "solid":      Qt.SolidLine,
    "dashed":     Qt.DashLine,
    "dotted":     Qt.DotLine,
    "dashdot":    Qt.DashDotLine,
    "dashdotdot": Qt.DashDotDotLine,
    "center":     Qt.DashLine,       # closest Qt equivalent
    "phantom":    Qt.DashDotDotLine,
    "hidden":     Qt.DashLine,
}


def _line_style_to_qt(style: str) -> Qt.PenStyle:
    return _LINE_STYLE_MAP.get(style.lower(), Qt.SolidLine)
from typing import List, Optional

from app.document import DocumentStore
from app.entities import Vec2
from app.editor.osnap_engine import OsnapEngine, SnapResult, SnapType
from app.editor.hit_testing import (
    hit_test_point,
    entity_inside_rect,
    entity_crosses_rect,
)
from app.ui.dynamic_input_widget import DynamicInputWidget


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

    def __init__(
        self,
        document: Optional[DocumentStore] = None,
        editor=None,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.setMinimumSize(800, 600)

        # View transform state
        self.scale = 1.0  # pixels per world unit
        self.offset = QPointF(0.0, 0.0)  # world coordinates at screen (0,0)
        # Origin anchoring: keep world (0,0) mapped to a screen corner
        # by default place origin at bottom-left with a small inset.
        self._origin_anchor: str = "bottom-left"  # one of: top-left, top-right, bottom-left, bottom-right
        self._origin_inset_px: QPointF = QPointF(10.0, 10.0)  # (x inset, y inset) in screen pixels
        self._origin_locked: bool = True  # when True, resize keeps the anchor
        # Initialise offset so world (0,0) appears at the chosen corner/inset
        self._update_offset_for_origin()

        # Interaction state
        self._panning = False
        self._last_mouse_pos = QPoint()

        # UI niceties
        self.setCursor(Qt.CrossCursor)

        # receive mouse move events even when no button is pressed
        self.setMouseTracking(True)

        # Accept keyboard focus so key-press events (Escape, etc.) are received
        self.setFocusPolicy(Qt.StrongFocus)

        # Document and editor — injected via constructor (preferred) or set
        # via the public properties below.
        self._document: Optional[DocumentStore] = document
        self._editor = editor
        # Cached preview entities from the last mouse-move callback.
        self._preview_entities: List = []

        # OSNAP engine — active whenever the editor is waiting for a point input.
        self._osnap: OsnapEngine = OsnapEngine()
        # Last computed snap result (None when no snap is within aperture).
        self._snap_result: Optional[SnapResult] = None

        # ---- Selection state ------------------------------------------------
        # Pixel threshold for click-to-select hit testing.
        self._pick_tolerance_px: float = 7.0
        # True while the user is dragging a selection rectangle.
        self._sel_dragging: bool = False
        # Screen-space anchor for selection rectangle (where left-button was pressed).
        self._sel_origin_screen: Optional[QPointF] = None
        # Current screen-space mouse position during a selection drag.
        self._sel_current_screen: Optional[QPointF] = None
        # World-space origin of the selection rectangle.
        self._sel_origin_world: Optional[Vec2] = None
        # Minimum pixel drag distance before starting a rectangle selection.
        self._sel_drag_threshold: float = 4.0

        # ---- Hover state ---------------------------------------------------
        # Entity id currently under the cursor (None when nothing is hovered).
        self._hovered_entity_id: Optional[str] = None

        # ---- Render cache (rubber band optimisation) -------------------------
        # Captured scene pixmap (grid + entities, no rubber band) reused during
        # selection drags so we only redraw the selection rect each frame.
        self._scene_cache: Optional[QPixmap] = None

        # ---- Dynamic input widget --------------------------------------------
        # Custom-painted input fields following the cursor during point/value input
        self._dynamic_input = DynamicInputWidget(parent=self)
        self._dynamic_input.hide()
        self._dynamic_input.input_submitted.connect(self._on_dynamic_input_submitted)
        self._dynamic_input.input_cancelled.connect(self._on_dynamic_input_cancelled)

        # Connect to editor signals to update dynamic input state
        if self._editor is not None:
            self._editor.input_mode_changed.connect(self._on_editor_input_mode_changed)

    # ----------------------
    # Coordinate transforms
    # ----------------------
    def screen_to_world(self, pt: QPointF) -> QPointF:
        # Inverted Y: screen y grows downwards, world y grows upwards
        return QPointF(pt.x() / self.scale + self.offset.x(), self.offset.y() - (pt.y() / self.scale))

    def world_to_screen(self, pt: QPointF) -> QPointF:
        # Inverted Y: convert world y to screen y by subtracting from offset
        return QPointF((pt.x() - self.offset.x()) * self.scale, (self.offset.y() - pt.y()) * self.scale)

    def set_origin_anchor(self, anchor: str = "bottom-left", inset_x_px: float = 0.0, inset_y_px: float = 0.0, lock: bool = True) -> None:
        """Set where the world-origin (0,0) is mapped on the widget.

        anchor: one of 'top-left', 'top-right', 'bottom-left', 'bottom-right'
        inset_x_px / inset_y_px: pixel inset from the chosen edges
        lock: when True, the anchor is preserved across widget resizes
        """
        anchor = anchor.lower()
        if anchor not in ("top-left", "top-right", "bottom-left", "bottom-right"):
            raise ValueError("invalid anchor")
        self._origin_anchor = anchor
        self._origin_inset_px = QPointF(float(inset_x_px), float(inset_y_px))
        self._origin_locked = bool(lock)
        self._update_offset_for_origin()

    def _update_offset_for_origin(self) -> None:
        """Recompute `self.offset` (world coords at screen (0,0)) from the
        current anchor/inset, widget size and scale.
        """
        w_px, h_px = self.width(), self.height()
        ix = self._origin_inset_px.x()
        iy = self._origin_inset_px.y()
        # X offset (world coordinate that maps to screen x==0).
        # We choose offset so world x==0 maps to the requested screen x inset:
        #   world_to_screen.x(0) == inset_x_px  =>  (0 - offset.x) * scale == inset_x_px
        # hence offset.x = -inset_x_px / scale for left anchor. For right anchor
        # world x==0 should map to (widget_width - inset_x_px).
        if self._origin_anchor.endswith("-left"):
            ox = -ix / max(self.scale, 1e-12)
        else:
            ox = -(w_px - ix) / max(self.scale, 1e-12)
        # Y offset (world coordinate that maps to screen y==0)
        if self._origin_anchor.startswith("top-"):
            oy = iy / max(self.scale, 1e-12)
        else:
            # anchor on bottom: world y that maps to screen y==0 is (widget_height - inset)/scale
            oy = (h_px - iy) / max(self.scale, 1e-12)
        self.offset = QPointF(ox, oy)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        if getattr(self, "_origin_locked", False):
            self._update_offset_for_origin()

    # ----------------------
    # Event handling
    # ----------------------
    @property
    def _idle(self) -> bool:
        """True when no command is running and the editor is not waiting for input."""
        return self._editor is None or not self._editor.is_running

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            posf = event.position() if hasattr(event, "position") else event.posF()
            world_pt = self.screen_to_world(posf)

            if self._idle:
                # ---- Selection mode ----
                self._sel_origin_screen = QPointF(posf)
                self._sel_current_screen = QPointF(posf)
                self._sel_origin_world = Vec2(world_pt.x(), world_pt.y())
                self._sel_dragging = False  # will become True after threshold
            else:
                # ---- Command mode — emit world point for the active command ----
                if self._snap_result is not None:
                    pt = self._snap_result.point
                    self.pointSelected.emit(pt.x, pt.y)
                else:
                    self.pointSelected.emit(world_pt.x(), world_pt.y())
            self.setFocus()
            return

        # start panning with middle mouse button
        if event.button() == Qt.MiddleButton:
            self._panning = True
            # User-initiated pan should break origin anchoring so subsequent
            # resizes preserve the current camera offset.
            self._origin_locked = False
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        posf = event.position() if hasattr(event, "position") else event.posF()
        world_pt = self.screen_to_world(posf)
        raw = Vec2(world_pt.x(), world_pt.y())

        # ---- Selection rectangle drag tracking ----------------------------
        if self._sel_origin_screen is not None and not self._panning:
            self._sel_current_screen = QPointF(posf)
            dx = posf.x() - self._sel_origin_screen.x()
            dy = posf.y() - self._sel_origin_screen.y()
            if not self._sel_dragging and (dx * dx + dy * dy) > self._sel_drag_threshold ** 2:
                self._sel_dragging = True
                # Snapshot the current scene (no rubber band yet) so paintEvent
                # can reuse it every frame instead of doing a full redraw.
                self._scene_cache = self.grab()
            if self._sel_dragging:
                self.update()

        # ---- OSNAP --------------------------------------------------------
        # Only run snap when the editor is expecting a point input.
        snap_active = (
            self._editor is not None
            and getattr(self._editor, "_input_mode", "none") == "point"
            and self._document is not None
        )
        if snap_active:
            self._snap_result = self._osnap.snap(
                raw, self._document.entities, self.scale,
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

        # ---- Dynamic input widget update ------------------------------------
        # Update dynamic input position and cursor coordinates whenever mouse moves
        if snap_active or (self._editor is not None and getattr(self._editor, "_input_mode", "none") in ("integer", "float", "string")):
            self._dynamic_input.update_cursor_position(display)
            self._dynamic_input.update_screen_position(event.pos() if hasattr(event, "pos") else posf.toPoint())

        # ---- Hover hit-test (idle mode only) --------------------------------
        if self._idle and self._document is not None and not self._sel_dragging:
            tolerance = self._pick_tolerance_px / self.scale
            new_hover: Optional[str] = None
            for e in self._document:
                lyr = self._document.get_layer(e.layer)
                if lyr is not None and not lyr.visible:
                    continue
                if hit_test_point(e, raw, tolerance):
                    new_hover = e.id
                    break
            if new_hover != self._hovered_entity_id:
                self._hovered_entity_id = new_hover
        elif not self._idle:
            # Clear hover while a command is running
            if self._hovered_entity_id is not None:
                self._hovered_entity_id = None

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
        if event.button() == Qt.LeftButton and self._sel_origin_screen is not None:
            posf = event.position() if hasattr(event, "position") else event.posF()
            shift = bool(event.modifiers() & Qt.ShiftModifier)
            self._finish_selection(posf, shift)
            # Reset selection drag state
            self._sel_origin_screen = None
            self._sel_current_screen = None
            self._sel_origin_world = None
            self._sel_dragging = False
            self._scene_cache = None
            self.update()

        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CrossCursor)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """Clear hover highlight when the cursor leaves the canvas."""
        if self._hovered_entity_id is not None:
            self._hovered_entity_id = None
            self.update()

    def event(self, event) -> bool:  # noqa: N802
        """Intercept Tab/Shift-Tab before Qt's focus-chain handles them.

        Qt processes Tab at the QWidget.event() level, before keyPressEvent
        is called.  When the dynamic input widget is visible we must consume
        Tab/Backtab here so they never reach the focus machinery.
        """
        if event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key_Tab, Qt.Key_Backtab) and self._dynamic_input.isVisible():
                self._dynamic_input.keyPressEvent(event)
                return True  # consumed
        return super().event(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            if self._idle:
                # No command running: clear selection (and hover)
                changed = False
                if self._editor is not None and self._editor.selection:
                    self._editor.selection.clear()
                    changed = True
                if self._hovered_entity_id is not None:
                    self._hovered_entity_id = None
                    changed = True
                if changed:
                    self.update()
                # Always emit so any other idle-mode handlers can react
                self.cancelRequested.emit()
            else:
                # Command is active: cancel the command but leave selection intact
                self._dynamic_input.clear()
                self.cancelRequested.emit()
            return

        # --- Delete key: remove selected entities when idle --------------
        if event.key() == Qt.Key_Delete and self._idle:
            if self._editor is not None and self._editor.selection:
                # Editor provides a convenience helper that takes care of
                # iterating, emitting signals and clearing the set.
                self._editor.delete_selection()
                # If the deleted objects included the one currently hovered,
                # clear the hover so we don't try to render an overlay for a
                # non-existent entity.
                self._hovered_entity_id = None
                self.update()
            return

        if self._dynamic_input.isVisible():
            # Forward all non-Escape keys to the dynamic input widget while it
            # is active so the user can type values without clicking.
            self._dynamic_input.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    # ----------------------------------------------------------------
    # Selection logic
    # ----------------------------------------------------------------

    def _finish_selection(self, release_pos: QPointF, shift: bool) -> None:
        """Process a completed left-button click or drag for selection.

        Called from ``mouseReleaseEvent`` when in idle (no command) mode.
        """
        if self._editor is None or self._document is None:
            return

        selection = self._editor.selection

        if self._sel_dragging:
            # ---- Rectangle selection ----------------------------------
            origin_world = self._sel_origin_world
            end_world_qpt = self.screen_to_world(release_pos)
            end_world = Vec2(end_world_qpt.x(), end_world_qpt.y())

            # Normalise the rectangle
            rmin = Vec2(min(origin_world.x, end_world.x),
                        min(origin_world.y, end_world.y))
            rmax = Vec2(max(origin_world.x, end_world.x),
                        max(origin_world.y, end_world.y))

            # Direction determines mode:
            # screen-space left→right  ⇒  window  (fully inside)
            # screen-space right→left  ⇒  crossing (intersects)
            is_window = release_pos.x() >= self._sel_origin_screen.x()

            matched_ids = set()
            for e in self._document:
                layer = self._document.get_layer(e.layer)
                if layer is not None and not layer.visible:
                    continue
                if is_window:
                    if entity_inside_rect(e, rmin, rmax):
                        matched_ids.add(e.id)
                else:
                    if entity_crosses_rect(e, rmin, rmax):
                        matched_ids.add(e.id)

            if shift:
                selection.subtract(matched_ids)
            else:
                selection.extend(matched_ids)
        else:
            # ---- Point (click) selection --------------------------------
            click_world_qpt = self.screen_to_world(release_pos)
            click_world = Vec2(click_world_qpt.x(), click_world_qpt.y())
            tolerance = self._pick_tolerance_px / self.scale

            hit = None
            for e in self._document:
                layer = self._document.get_layer(e.layer)
                if layer is not None and not layer.visible:
                    continue
                if hit_test_point(e, click_world, tolerance):
                    hit = e
                    break  # first hit wins (topmost in draw order)

            if hit is not None:
                if shift:
                    selection.remove(hit.id)
                else:
                    selection.add(hit.id)
            # Clicking in empty space does nothing (per requirements).

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
        # Zoom is an interactive camera change — disable origin anchoring so
        # the view stays where the user zoomed/panned when the widget is
        # later resized.
        self._origin_locked = False
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
        # Fast path: during a rubber band selection drag the view transform
        # does not change, so we can reuse the cached scene and only repaint
        # the selection rectangle on top.  This avoids re-rendering the grid
        # and all entities on every mouse-move event during the drag.
        if self._sel_dragging and self._scene_cache is not None:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self._scene_cache)
            if self._sel_origin_screen is not None and self._sel_current_screen is not None:
                self._draw_selection_rect(painter)
            return

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1E1E1E"))
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Draw grid
        self._draw_grid(painter)

        # Draw document entities — layer-aware pen per entity
        sel_ids   = self._editor.selection.ids if self._editor is not None else set()
        hover_id  = self._hovered_entity_id
        if self._document is not None:
            # Compute viewport world bounds once for frustum culling.
            w_px, h_px = self.width(), self.height()
            tl = self.screen_to_world(QPointF(0, 0))
            br = self.screen_to_world(QPointF(w_px, h_px))
            vp_min_x = min(tl.x(), br.x())
            vp_min_y = min(tl.y(), br.y())
            vp_max_x = max(tl.x(), br.x())
            vp_max_y = max(tl.y(), br.y())

            for e in self._document:
                layer = self._document.get_layer(e.layer)
                # Skip entities whose layer is hidden
                if layer is not None and not layer.visible:
                    continue
                # Frustum cull: skip entities whose bounding box is entirely
                # outside the viewport.  Entities with no bounding box (unknown
                # types) are always drawn as a safe fallback.
                bb = e.bounding_box()
                if bb is not None and not bb.intersects_viewport(
                    vp_min_x, vp_min_y, vp_max_x, vp_max_y
                ):
                    continue
                # Resolve pen defaults from layer
                is_sel   = e.id in sel_ids
                is_hover = e.id == hover_id
                if layer is not None:
                    color     = _resolve_color_str(layer.color)
                    thickness = layer.thickness
                    style     = _line_style_to_qt(layer.line_style)
                else:
                    color     = QColor(220, 220, 220)
                    thickness = 1.0
                    style     = Qt.SolidLine

                # Apply ALL per-entity overrides unconditionally so the true
                # appearance is always visible (even under hover/selection).
                ew = getattr(e, "line_weight", None)
                if ew is not None:
                    thickness = ew
                ec = getattr(e, "color", None)
                if ec is not None:
                    color = _resolve_color_str(ec)
                es = getattr(e, "line_style", None)
                if es is not None:
                    style = _line_style_to_qt(es)

                # ---- Base pass: draw entity with its true pen ----
                pen = QPen(color, thickness)
                pen.setStyle(style)
                painter.setPen(pen)
                self._draw_entity(painter, e)

                # ---- Overlay pass: semi-transparent highlight for hover/selection ----
                if is_hover or is_sel:
                    if is_hover and is_sel:
                        overlay_color = QColor(80, 180, 255, 90)
                    elif is_hover:
                        overlay_color = QColor(255, 200, 0, 90)
                    else:
                        overlay_color = QColor(0, 150, 255, 90)
                    overlay_thickness = max(thickness + 4.0, 6.0)
                    overlay_pen = QPen(overlay_color, overlay_thickness)
                    overlay_pen.setStyle(style)
                    painter.setPen(overlay_pen)
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

        # Draw selection rectangle overlay (only reached on full redraws)
        if self._sel_dragging and self._sel_origin_screen is not None and self._sel_current_screen is not None:
            self._draw_selection_rect(painter)

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
            # X symbol: two diagonal crossing lines (classic CAD intersection marker)
            painter.drawLine(QPointF(sx - S, sy - S), QPointF(sx + S, sy + S))
            painter.drawLine(QPointF(sx + S, sy - S), QPointF(sx - S, sy + S))

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

    def _draw_selection_rect(self, painter: QPainter) -> None:
        """Draw the selection rectangle overlay in screen coordinates.

        **Window** (left→right): solid blue border, semi-transparent blue fill.
        **Crossing** (right→left): dashed green border, semi-transparent green fill.
        Matches the standard AutoCAD colour convention.
        """
        ox, oy = self._sel_origin_screen.x(), self._sel_origin_screen.y()
        cx, cy = self._sel_current_screen.x(), self._sel_current_screen.y()

        is_window = cx >= ox  # left-to-right ⇒ window

        left   = min(ox, cx)
        top    = min(oy, cy)
        width  = abs(cx - ox)
        height = abs(cy - oy)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)

        if is_window:
            # Window: solid blue border + translucent blue fill
            border_color = QColor(0, 120, 215)
            fill_color   = QColor(0, 120, 215, 40)
            pen = QPen(border_color, 1, Qt.SolidLine)
        else:
            # Crossing: dashed green border + translucent green fill
            border_color = QColor(0, 200, 80)
            fill_color   = QColor(0, 200, 80, 40)
            pen = QPen(border_color, 1, Qt.DashLine)

        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill_color))
        painter.drawRect(QRectF(left, top, width, height))
        painter.restore()

    def _draw_entity(self, painter: QPainter, e) -> None:
        """Draw a single entity using the painter's current pen."""
        try:
            e.draw(painter, self.world_to_screen, self.scale)
        except Exception:
            import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # Testing helpers
    # ------------------------------------------------------------------
    def _pen_for_entity(self, e, sel_ids: set, hover_id: Optional[str]):
        """Compute the *base* QPen that *paintEvent* would use for *e*.

        Returns the true resolved pen (with all property overrides applied).
        Hover/selection is rendered as a separate semi-transparent overlay
        pass in ``paintEvent``, so this method returns only the base pen.

        For test convenience the overlay pen is available via
        ``_overlay_pen_for_entity``.
        """
        # resolve layer
        layer = self._document.get_layer(e.layer) if self._document else None
        if layer is not None:
            color = QColor(layer.color)
            thickness = layer.thickness
            style = _line_style_to_qt(layer.line_style)
        else:
            color = QColor(220, 220, 220)
            thickness = 1.0
            style = Qt.SolidLine

        # Apply ALL per-entity overrides unconditionally.
        ew = getattr(e, "line_weight", None)
        if ew is not None:
            thickness = ew
        ec = getattr(e, "color", None)
        if ec is not None:
            color = QColor(ec)
        es = getattr(e, "line_style", None)
        if es is not None:
            style = _line_style_to_qt(es)

        pen = QPen(color, thickness)
        pen.setStyle(style)
        return pen

    def _overlay_pen_for_entity(self, e, sel_ids: set, hover_id: Optional[str]) -> Optional[QPen]:
        """Compute the semi-transparent overlay QPen for hover/selection.

        Returns ``None`` when the entity is neither selected nor hovered.
        """
        is_sel = e.id in sel_ids
        is_hover = e.id == hover_id
        if not (is_sel or is_hover):
            return None

        # Resolve thickness from base pen computation.
        base_pen = self._pen_for_entity(e, sel_ids, hover_id)
        thickness = base_pen.widthF()
        style = base_pen.style()

        if is_hover and is_sel:
            overlay_color = QColor(80, 180, 255, 90)
        elif is_hover:
            overlay_color = QColor(255, 200, 0, 90)
        else:
            overlay_color = QColor(0, 150, 255, 90)

        overlay_thickness = max(thickness + 4.0, 6.0)
        overlay_pen = QPen(overlay_color, overlay_thickness)
        overlay_pen.setStyle(style)
        return overlay_pen

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
        # A grid level is invisible when its lines are <= FADE_IN px apart
        # and fully opaque when they are >= FADE_FULL px apart.
        # Lower FADE_IN makes finer (closer) grid lines become visible
        # sooner (i.e. at smaller pixel spacings).  Lowering FADE_FULL
        # brings levels to full opacity earlier to preserve readability.
        FADE_IN   = 2.0   # was 14.0 — show finer grids earlier
        FADE_FULL = 50.0  # was 70.0 — reach full opacity sooner

        def alpha_for_spacing(world_spacing: float) -> float:
            px = world_spacing * self.scale
            # Always give extremely compressed grids a faint visibility so
            # very fine structure remains hinted even when spacing < FADE_IN.
            if px <= FADE_IN:
                return 0.02
            if px >= FADE_FULL:
                return 1.0
            # Gentler power curve to keep small-spacing levels more visible
            # across the transition.  Using an exponent < 1 biases the curve
            # upwards so t values produce higher alpha than a linear ramp.
            t = (px - FADE_IN) / (FADE_FULL - FADE_IN)
            return max(0.0, min(1.0, t ** 0.6))

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

        # Use mantissas 1 and 5 to guarantee coarser levels fall exactly on
        # finer levels (clean subdivision).  This preserves alignment when
        # switching between grid levels while the alpha curve below keeps
        # finer grids visible for longer.
        nice_spacings: list[float] = []
        for exp in range(low_exp, high_exp + 1):
            for mant in (1, 5):
                s = mant * (10.0 ** exp)
                if min_world * 0.5 <= s <= max_world * 2.0:
                    nice_spacings.append(s)
        nice_spacings.sort()

        # ── Cap to the 4 most visible levels ──────────────────────────────
        # Computing and drawing 20+ levels on every frame is expensive.
        # Sort by alpha (descending) and keep only the top 4 so the dominant
        # levels with the most visual weight are always rendered, while nearly
        # invisible micro-levels are elided.
        if len(nice_spacings) > 4:
            nice_spacings = sorted(
                nice_spacings,
                key=lambda s: alpha_for_spacing(s),
                reverse=True,
            )[:4]
            nice_spacings.sort()  # restore spatial order (finest first)

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

            # Vertical / Horizontal lines
            # Compute rough counts and apply a cap so extremely dense views
            # don't issue thousands of draw calls per frame. If the total
            # lines would exceed MAX_LINES_PER_LEVEL we sample every Nth
            # line (stride) to keep a visual hint while bounding work.
            MAX_LINES_PER_LEVEL = 400

            start_x = floor(wx_min / spacing) * spacing
            num_vert = int((wx_max - wx_min) / spacing) + 4

            start_y = floor(wy_min / spacing) * spacing
            num_horiz = int((wy_max - wy_min) / spacing) + 4

            total_lines = num_vert + num_horiz
            stride = max(1, int(total_lines / MAX_LINES_PER_LEVEL))

            # Build batched line lists and draw them once to reduce overhead
            vert_lines = []
            horiz_lines = []

            for iv in range(0, num_vert, stride):
                x = start_x + iv * spacing
                if x > wx_max + spacing:
                    break
                idx = int(round(x / spacing))
                if idx == 0:
                    continue
                sx = int((x - self.offset.x()) * self.scale)
                vert_lines.append(QLine(sx, 0, sx, h))

            for ih in range(0, num_horiz, stride):
                y = start_y + ih * spacing
                if y > wy_max + spacing:
                    break
                idx = int(round(y / spacing))
                if idx == 0:
                    continue
                sy = int((self.offset.y() - y) * self.scale)
                horiz_lines.append(QLine(0, sy, w, sy))

            if vert_lines:
                painter.drawLines(vert_lines)
            if horiz_lines:
                painter.drawLines(horiz_lines)

        # ── World-origin axes (always on top) ─────────────────────────────
        ox = (0.0 - self.offset.x()) * self.scale
        oy = (self.offset.y() - 0.0) * self.scale
        axis_pen = QPen(QColor(180, 80, 80, 200), 1)
        painter.setPen(axis_pen)
        painter.drawLine(int(ox), 0, int(ox), h)
        painter.drawLine(0, int(oy), w, int(oy))

    # ----------------------------------------------------------------
    # Dynamic input handling
    # ----------------------------------------------------------------

    @Slot(str)
    def _on_editor_input_mode_changed(self, mode: str) -> None:
        """Handle editor input mode changes to show/hide dynamic input widget."""
        if mode == "none":
            self._dynamic_input.clear()
        elif mode in ("point", "integer", "float", "string"):
            base_point = None
            if mode == "point" and self._editor is not None:
                base_point = self._editor.snap_from_point
            self._dynamic_input.set_input_mode(mode, Vec2(0, 0), base_point)
            # Show the widget on the screen
            self._dynamic_input.show()
            self._dynamic_input.raise_()
            # Ensure the canvas has keyboard focus so keyPressEvent fires
            # and forwards typed characters to the dynamic input widget.
            self.setFocus()

    @Slot(object)
    def _on_dynamic_input_submitted(self, value: object) -> None:
        """Forward accepted dynamic input to the editor."""
        if self._editor is None:
            return

        mode = self._editor._input_mode
        if mode == "point":
            self._editor.provide_point(value)
        elif mode == "integer":
            self._editor.provide_integer(int(value))
        elif mode == "float":
            self._editor.provide_float(float(value))
        elif mode == "string":
            self._editor.provide_string(str(value))

    @Slot()
    def _on_dynamic_input_cancelled(self) -> None:
        """Forward cancellation to editor."""
        if self._editor is not None:
            self.cancelRequested.emit()
