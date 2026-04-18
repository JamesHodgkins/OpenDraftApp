"""
CAD Canvas widget — the main drawing surface with a viewport.

Provides basic pan/zoom, screen<->world transforms and a smooth adaptive grid
that fades between density levels as you zoom, giving a continuous sense of
scale rather than snapping between states.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF, QBrush, QPixmap
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, Signal, Slot


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
from app.entities.base import GripPoint, GripType
from app.editor.osnap_engine import OsnapEngine, SnapResult, SnapType
from app.editor.settings import EditorSettings
from app.editor.draftmate import (
    DraftmateEngine,
    DraftmateResult,
    DraftmateSettings,
    AlignmentLine,
    TrackedPoint,
)
from app.editor.hit_testing import (
    hit_test_point,
    entity_inside_rect,
    entity_crosses_rect,
)
from app.ui.dynamic_input_widget import DynamicInputWidget
from app.canvas_viewport import ViewportTransform
from app.canvas_grid import GridRenderer


class CADCanvas(QWidget):
    """Viewport-enabled CAD canvas with pan/zoom and grid drawing."""

    # emits world x,y when the mouse moves over the canvas
    mouseMoved = Signal(float, float)
    # emits the world-space point the user clicked (left button)
    pointSelected = Signal(float, float)
    # emits when the user presses Escape
    cancelRequested = Signal()
    # emitted when a drawing-mode toggle changes on the canvas (F8/F10 etc.)
    # so the status bar can stay in sync.
    orthoChanged = Signal(bool)
    draftmateChanged = Signal(bool)

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

        # ---- Viewport transform (pan/zoom/coordinate conversion) ----------
        self._vp = ViewportTransform()
        self._vp.update_offset_for_size(self.width(), self.height())

        # ---- Grid renderer ------------------------------------------------
        self._grid = GridRenderer(self._vp)

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

        # Resolve editor settings (or fall back to defaults if no editor provided).
        _s: EditorSettings = editor.settings if editor is not None else EditorSettings()

        # OSNAP engine — active whenever the editor is waiting for a point input.
        self._osnap: OsnapEngine = OsnapEngine(radius_px=_s.osnap_aperture_px)
        # Master OSNAP toggle — when False the snap engine is skipped entirely.
        self._osnap_master: bool = True
        # Last computed snap result (None when no snap is within aperture).
        self._snap_result: Optional[SnapResult] = None

        # ---- Ortho mode -----------------------------------------------------
        self._ortho: bool = False

        # ---- Selection state ------------------------------------------------
        # Pixel threshold for click-to-select hit testing.
        self._pick_tolerance_px: float = _s.pick_tolerance_px
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

        # ---- Grip editing state -------------------------------------------
        # Size (half-width) of grip squares in screen pixels.
        self._grip_half_size: int = _s.grip_half_size_px
        # Pixel tolerance for "is the mouse over a grip?" hit test.
        self._grip_pick_px: float = _s.grip_pick_px
        # The GripPoint currently under the cursor (None when no grip is hot).
        self._hot_grip: Optional[GripPoint] = None
        # The GripPoint currently being dragged (None when not dragging).
        self._active_grip: Optional[GripPoint] = None
        # The entity being grip-edited (a shallow copy so we can mutate it
        # live during the drag without corrupting the document until commit).
        self._grip_entity_snapshot = None
        # Mouse position in world coordinates during a grip drag.
        self._grip_drag_world: Optional[Vec2] = None

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

        # ---- Draftmate (Object Snap Tracking + Polar Tracking) -----------
        self._draftmate = DraftmateEngine()
        # Last frame's Draftmate result (None when disabled or no data).
        self._draftmate_result: Optional[DraftmateResult] = None

        # Connect to editor signals to update dynamic input state
        if self._editor is not None:
            self._editor.input_mode_changed.connect(self._on_editor_input_mode_changed)

    # ----------------------
    # Viewport proxy properties
    # ----------------------

    @property
    def scale(self) -> float:
        return self._vp.scale

    @scale.setter
    def scale(self, v: float) -> None:
        self._vp.scale = v

    @property
    def offset(self) -> QPointF:
        return self._vp.offset

    @offset.setter
    def offset(self, v: QPointF) -> None:
        self._vp.offset = v

    # ----------------------
    # Coordinate transforms
    # ----------------------

    def screen_to_world(self, pt: QPointF) -> QPointF:
        return self._vp.screen_to_world(pt)

    def world_to_screen(self, pt: QPointF) -> QPointF:
        return self._vp.world_to_screen(pt)

    def set_origin_anchor(
        self, anchor: str = "bottom-left",
        inset_x_px: float = 0.0, inset_y_px: float = 0.0,
        lock: bool = True,
    ) -> None:
        self._vp.set_origin_anchor(anchor, inset_x_px, inset_y_px, lock)
        self._vp.update_offset_for_size(self.width(), self.height())

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        if self._vp._origin_locked:
            self._vp.update_offset_for_size(self.width(), self.height())

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

            # ---- Grip: second click places the active grip ----
            if self._active_grip is not None:
                # Use snapped position when available.
                if self._snap_result is not None:
                    final_pos = self._snap_result.point
                elif self._grip_drag_world is not None:
                    final_pos = self._grip_drag_world
                else:
                    final_pos = Vec2(world_pt.x(), world_pt.y())
                if self._document is not None:
                    for e in self._document:
                        if e.id == self._active_grip.entity_id:
                            e.move_grip(self._active_grip.index, final_pos)
                            break
                # Reset grip state.
                self._active_grip = None
                self._grip_entity_snapshot = None
                self._grip_drag_world = None
                self._snap_result = None
                self.setCursor(Qt.CrossCursor)
                self.update()
                self.setFocus()
                return

            # ---- Grip activation: first click on a hot grip starts moving it ----
            if self._idle and self._hot_grip is not None:
                import copy
                grip = self._hot_grip
                self._active_grip = grip
                # Find the entity and snapshot it so we can mutate during move.
                if self._document is not None:
                    for e in self._document:
                        if e.id == grip.entity_id:
                            self._grip_entity_snapshot = copy.deepcopy(e)
                            break
                self._grip_drag_world = Vec2(world_pt.x(), world_pt.y())
                self.setFocus()
                return

            if self._idle:
                # ---- Selection mode ----
                self._sel_origin_screen = QPointF(posf)
                self._sel_current_screen = QPointF(posf)
                self._sel_origin_world = Vec2(world_pt.x(), world_pt.y())
                self._sel_dragging = False  # will become True after threshold
            else:
                # ---- Command mode — emit world point for the active command ----
                # Draftmate alignment snap takes priority over raw osnap.
                dm = self._draftmate_result
                if dm is not None and dm.snapped_point is not None:
                    pt = dm.snapped_point
                elif self._snap_result is not None:
                    pt = self._snap_result.point
                else:
                    pt = Vec2(world_pt.x(), world_pt.y())

                # Apply ortho constraint when no snap is active.
                from_point = getattr(self._editor, "snap_from_point", None)
                if (
                    self._ortho
                    and from_point is not None
                    and self._snap_result is None
                    and (dm is None or dm.snapped_point is None)
                ):
                    dx = pt.x - from_point.x
                    dy = pt.y - from_point.y
                    if abs(dx) >= abs(dy):
                        pt = Vec2(pt.x, from_point.y)
                    else:
                        pt = Vec2(from_point.x, pt.y)

                self.pointSelected.emit(pt.x, pt.y)
                # Clear tracked points after each click so the workspace
                # stays clean between drawing steps.
                self._draftmate.clear()
                self._draftmate_result = None
            self.setFocus()
            return

        # start panning with middle mouse button
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._vp._origin_locked = False
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        posf = event.position() if hasattr(event, "position") else event.posF()
        world_pt = self.screen_to_world(posf)
        raw = Vec2(world_pt.x(), world_pt.y())

        # ---- Active grip move (click-click mode) --------------------------
        if self._active_grip is not None:
            # Run OSNAP so the grip can snap to geometry while moving.
            if self._document is not None and self._osnap_master:
                # Exclude the entity being edited from snap candidates so
                # it doesn't snap to its own (original) geometry.
                snap_entities = [
                    ent for ent in self._document.entities
                    if ent.id != self._active_grip.entity_id
                ]
                self._snap_result = self._osnap.snap(
                    raw, snap_entities, self.scale,
                )
            else:
                self._snap_result = None

            # Use snapped position when available.
            if self._snap_result is not None:
                display_grip = self._snap_result.point
            else:
                display_grip = raw
            self._grip_drag_world = display_grip

            # Apply the grip movement live to the snapshot so the entity
            # redraws at the new position during the move.
            if self._grip_entity_snapshot is not None:
                import copy
                # Re-snapshot from the original document entity each frame
                # so cumulative floating-point drift doesn't accumulate.
                for e in (self._document or []):
                    if e.id == self._active_grip.entity_id:
                        self._grip_entity_snapshot = copy.deepcopy(e)
                        break
                self._grip_entity_snapshot.move_grip(
                    self._active_grip.index, display_grip)
            self.update()
            # Don't return — let the rest of mouseMoveEvent run so the
            # coordinate display, crosshair, etc. stay updated.
            try:
                self.mouseMoved.emit(display_grip.x, display_grip.y)
            except Exception:
                pass

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
        # Only run snap when the editor is expecting a point input and the
        # master snap toggle is on.  Skip when a grip is active — the
        # grip-move block above already ran snap.
        snap_active = (
            self._active_grip is None
            and self._editor is not None
            and getattr(self._editor, "_input_mode", "none") == "point"
            and self._document is not None
            and self._osnap_master
            and not getattr(self._editor, "suppress_osnap", False)
        )
        if snap_active:
            self._snap_result = self._osnap.snap(
                raw, self._document.entities, self.scale,
                from_point=getattr(self._editor, "snap_from_point", None),
            )
        elif self._active_grip is None:
            # Only clear snap when no grip is active — the grip-move block
            # above already set _snap_result for the current frame.
            self._snap_result = None

        # ---- Draftmate tracking + alignment --------------------------------
        from_point = getattr(self._editor, "snap_from_point", None) if self._editor else None
        if snap_active:
            self._draftmate_result = self._draftmate.update(
                raw, self._snap_result, from_point, self.scale,
            )
        else:
            self._draftmate_result = None

        # Decide final display point: Draftmate alignment > OSNAP > raw.
        dm = self._draftmate_result
        if dm is not None and dm.snapped_point is not None:
            display = dm.snapped_point
        elif self._snap_result is not None:
            display = self._snap_result.point
        else:
            display = raw

        # ---- Ortho constraint ---------------------------------------------
        # When ortho is active and we have a base point, constrain the
        # display position to the nearest cardinal axis (H or V) from the
        # base point.  OSNAP / Draftmate snaps take priority (already
        # resolved above) — ortho only constrains the "free" cursor.
        if (
            self._ortho
            and from_point is not None
            and self._snap_result is None
            and (dm is None or dm.snapped_point is None)
        ):
            dx = display.x - from_point.x
            dy = display.y - from_point.y
            if abs(dx) >= abs(dy):
                display = Vec2(display.x, from_point.y)
            else:
                display = Vec2(from_point.x, display.y)

        try:
            self.mouseMoved.emit(display.x, display.y)
        except Exception:
            pass

        # Update rubberband preview using the best available position.
        if self._editor is not None:
            self._preview_entities = self._editor.get_dynamic(display)

        # ---- Dynamic input widget update ------------------------------------
        # Update dynamic input position and cursor coordinates whenever mouse moves
        if snap_active or (self._editor is not None and getattr(self._editor, "_input_mode", "none") in ("integer", "float", "string", "choice", "angle", "length")):
            self._dynamic_input.update_cursor_position(display)
            self._dynamic_input.update_screen_position(event.pos() if hasattr(event, "pos") else posf.toPoint())

        # ---- Hover hit-test (idle mode only) --------------------------------
        # Skip hover/grip-hover while a grip is actively being moved.
        if self._active_grip is not None:
            pass  # grip move is in progress — no hover updates
        elif self._idle and self._document is not None and not self._sel_dragging:
            # ---- Grip hover detection (takes priority) --------------------
            sel_ids = self._editor.selection.ids if self._editor is not None else set()
            old_hot = self._hot_grip
            self._hot_grip = None
            if sel_ids:
                grip_tol = self._grip_pick_px / self.scale
                for e in self._document:
                    if e.id not in sel_ids:
                        continue
                    for gp in e.grip_points():
                        dx = raw.x - gp.position.x
                        dy = raw.y - gp.position.y
                        if (dx * dx + dy * dy) <= grip_tol * grip_tol:
                            self._hot_grip = gp
                            break
                    if self._hot_grip is not None:
                        break
            # Update cursor shape for grip hover feedback
            if self._hot_grip is not None and old_hot is None:
                self.setCursor(Qt.SizeAllCursor)
            elif self._hot_grip is None and old_hot is not None:
                self.setCursor(Qt.CrossCursor)

            # ---- Entity hover detection -----------------------------------
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
            self._vp.pan(dx, dy)
            self._last_mouse_pos = QPoint(pos)
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        # Grip placement is handled in mousePressEvent (click-click mode),
        # so left-button release during an active grip move is a no-op.
        if event.button() == Qt.LeftButton and self._active_grip is not None:
            return

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

    # ----------------------------------------------------------------
    # Mode helpers — single authoritative location for mutual exclusion
    # ----------------------------------------------------------------

    def _set_ortho(self, on: bool) -> None:
        self._ortho = on
        if on:
            self._draftmate.settings.enabled = False
            self._draftmate.clear()
            self._draftmate_result = None
            self.draftmateChanged.emit(False)
        self.orthoChanged.emit(on)
        self.update()

    def _set_draftmate(self, on: bool) -> None:
        self._draftmate.settings.enabled = on
        if on:
            self._ortho = False
            self.orthoChanged.emit(False)
        else:
            self._draftmate.clear()
            self._draftmate_result = None
        self.draftmateChanged.emit(on)
        self.update()

    def handle_escape(self) -> None:
        """Single authoritative Escape handler — called by keyPressEvent and MainWindow shortcut."""
        # Cancel an active grip drag first.
        if self._active_grip is not None:
            self._active_grip = None
            self._grip_entity_snapshot = None
            self._grip_drag_world = None
            self.update()
            return

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

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.handle_escape()
            return

        # --- F10: toggle Draftmate (Object Snap Tracking + Polar Tracking) -
        if event.key() == Qt.Key_F10:
            self._set_draftmate(not self._draftmate.settings.enabled)
            return

        # --- F8: toggle Ortho mode ----------------------------------------
        if event.key() == Qt.Key_F8:
            self._set_ortho(not self._ortho)
            return

        # --- Delete key: remove selected entities when idle --------------
        if event.key() == Qt.Key_Delete and self._idle:
            if self._editor is not None and self._editor.selection:
                self._editor.delete_selection()
                self._editor.document_changed.emit()
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
        delta = event.angleDelta().y()
        if delta == 0:
            return
        cursor_pos = event.position() if hasattr(event, "position") else event.posF()
        self._vp.zoom_on_point(cursor_pos, 1.25 if delta > 0 else 0.8)
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
            try:
                painter.drawPixmap(0, 0, self._scene_cache)
                if self._sel_origin_screen is not None and self._sel_current_screen is not None:
                    self._draw_selection_rect(painter)
            finally:
                painter.end()
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

                # If this entity is being grip-dragged, draw the snapshot
                # (with the grip applied) instead of the real entity.
                draw_e = e
                if (self._active_grip is not None
                        and self._grip_entity_snapshot is not None
                        and e.id == self._active_grip.entity_id):
                    draw_e = self._grip_entity_snapshot

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
                self._draw_entity(painter, draw_e)

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
                    self._draw_entity(painter, draw_e)

        # ---- Draw grip squares for selected entities ----------------------
        if sel_ids and self._document is not None and (self._idle or self._active_grip is not None):
            self._draw_grips(painter, sel_ids)

        # Draw dynamic / rubberband preview entities
        if self._preview_entities:
            preview_pen = QPen(QColor(0, 191, 255), 1)
            painter.setPen(preview_pen)
            for e in self._preview_entities:
                self._draw_entity(painter, e)

        # Draw Draftmate guides (tracked points + alignment lines)
        if self._draftmate_result is not None:
            self._draw_draftmate(painter, self._draftmate_result)

        # Draw OSNAP marker
        if self._snap_result is not None:
            self._draw_snap_marker(painter, self._snap_result)

        # Draw selection rectangle overlay (only reached on full redraws)
        if self._sel_dragging and self._sel_origin_screen is not None and self._sel_current_screen is not None:
            self._draw_selection_rect(painter)

        painter.end()

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

    # ------------------------------------------------------------------
    # Draftmate visual feedback
    # ------------------------------------------------------------------

    def _draw_draftmate(self, painter: QPainter, result: DraftmateResult) -> None:
        """Draw Draftmate guides: green crosses for tracked points and
        green dashed extension / polar lines."""
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        green = QColor(0x22, 0xC5, 0x5E)  # #22c55e — a bright "tracking green"
        w_px, h_px = self.width(), self.height()

        # ---- Tracked point crosses (+) ------------------------------------
        cross_half = 6  # half-size in screen pixels
        pen_cross = QPen(green, 1.5)
        pen_cross.setCosmetic(True)
        painter.setPen(pen_cross)
        painter.setBrush(Qt.NoBrush)
        for tp in result.tracked_points:
            sp = self.world_to_screen(QPointF(tp.point.x, tp.point.y))
            sx, sy = sp.x(), sp.y()
            painter.drawLine(
                QPointF(sx - cross_half, sy),
                QPointF(sx + cross_half, sy),
            )
            painter.drawLine(
                QPointF(sx, sy - cross_half),
                QPointF(sx, sy + cross_half),
            )

        # ---- Alignment / polar guide lines --------------------------------
        pen_guide = QPen(green, 1)
        pen_guide.setStyle(Qt.DashLine)
        pen_guide.setCosmetic(True)
        painter.setPen(pen_guide)

        for ln in result.alignment_lines:
            self._draw_infinite_line(painter, ln, w_px, h_px)

        # ---- Snapped point marker (small filled green circle) -------------
        if result.snapped_point is not None:
            sp = self.world_to_screen(
                QPointF(result.snapped_point.x, result.snapped_point.y)
            )
            painter.setPen(QPen(green, 1.5))
            painter.setBrush(QBrush(green))
            painter.drawEllipse(sp, 3.0, 3.0)

        painter.restore()

    def _draw_infinite_line(
        self,
        painter: QPainter,
        ln: AlignmentLine,
        w_px: int,
        h_px: int,
    ) -> None:
        """Clip an infinite line to the viewport and draw it."""
        # Convert origin + direction to two world-space points far off-screen
        # using a very large parameter range that guarantees the line extends
        # well beyond the viewport in both directions.
        T = 1e7  # large enough for any reasonable zoom level
        p1w = QPointF(
            ln.origin.x - T * ln.direction.x,
            ln.origin.y - T * ln.direction.y,
        )
        p2w = QPointF(
            ln.origin.x + T * ln.direction.x,
            ln.origin.y + T * ln.direction.y,
        )
        p1s = self.world_to_screen(p1w)
        p2s = self.world_to_screen(p2w)
        painter.drawLine(p1s, p2s)

    # ------------------------------------------------------------------
    # Grip rendering
    # ------------------------------------------------------------------

    def _draw_grips(self, painter: QPainter, sel_ids: set) -> None:
        """Draw CAD-style grip squares for all selected entities.

        Blue filled squares at each grip location; the currently hot
        (hovered) grip is drawn red; the actively dragged grip is also red.
        """
        S = self._grip_half_size  # half-size in pixels
        hot = self._hot_grip
        active = self._active_grip

        # Colours matching traditional CAD: blue = cold, red = hot/active
        cold_fill   = QColor(0, 100, 255)      # solid blue
        cold_border = QColor(0, 60, 180)        # darker blue outline
        hot_fill    = QColor(255, 40, 40)       # solid red
        hot_border  = QColor(180, 0, 0)         # darker red outline

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)

        for e in (self._document or []):
            if e.id not in sel_ids:
                continue
            # When an entity is being grip-dragged, use the snapshot so the
            # grip squares follow the live preview position.
            draw_e = e
            if (active is not None
                    and self._grip_entity_snapshot is not None
                    and e.id == active.entity_id):
                draw_e = self._grip_entity_snapshot

            for gp in draw_e.grip_points():
                sp = self.world_to_screen(
                    QPointF(gp.position.x, gp.position.y))
                sx, sy = sp.x(), sp.y()

                is_hot = (hot is not None
                          and hot.entity_id == gp.entity_id
                          and hot.index == gp.index)
                is_active = (active is not None
                             and active.entity_id == gp.entity_id
                             and active.index == gp.index)

                if is_hot or is_active:
                    painter.setPen(QPen(hot_border, 1))
                    painter.setBrush(QBrush(hot_fill))
                else:
                    painter.setPen(QPen(cold_border, 1))
                    painter.setBrush(QBrush(cold_fill))

                painter.drawRect(
                    int(sx - S), int(sy - S), S * 2, S * 2)

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
        """Delegate grid rendering to GridRenderer."""
        self._grid.draw(painter, self.width(), self.height())

    # ----------------------------------------------------------------
    # Dynamic input handling
    # ----------------------------------------------------------------

    @Slot(str)
    def _on_editor_input_mode_changed(self, mode: str) -> None:
        """Handle editor input mode changes to show/hide dynamic input widget."""
        if mode == "none":
            self._dynamic_input.clear()
        elif mode in ("point", "integer", "float", "string", "choice", "angle", "length"):
            # Skip dynamic input when the active command has suppressed it
            # (e.g. Trim — the user is picking segments, not entering coords).
            if getattr(self._editor, "suppress_dynamic_input", False):
                return
            base_point = None
            if mode == "point" and self._editor is not None:
                base_point = self._editor.snap_from_point
            choice_options = self._editor._choice_options if mode == "choice" else None
            angle_center = self._editor._angle_center if mode == "angle" else None
            length_base = self._editor._length_base if mode == "length" else None
            self._dynamic_input.set_input_mode(mode, Vec2(0, 0), base_point, choice_options, angle_center, length_base)
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
        elif mode == "angle":
            self._editor.provide_angle(float(value))
        elif mode == "length":
            self._editor.provide_length(float(value))
        elif mode == "string":
            self._editor.provide_string(str(value))
        elif mode == "choice":
            self._editor.provide_choice(str(value))

    @Slot()
    def _on_dynamic_input_cancelled(self) -> None:
        """Forward cancellation to editor."""
        if self._editor is not None:
            self.cancelRequested.emit()
