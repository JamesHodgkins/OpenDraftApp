"""
CAD Canvas widget — the main drawing surface with a viewport.

Provides basic pan/zoom, screen<->world transforms and a smooth adaptive grid
that fades between density levels as you zoom, giving a continuous sense of
scale rather than snapping between states.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap
from PySide6.QtCore import Qt, QPoint, QPointF, Signal, Slot


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
    "solid":      Qt.PenStyle.SolidLine,
    "dashed":     Qt.PenStyle.DashLine,
    "dotted":     Qt.PenStyle.DotLine,
    "dashdot":    Qt.PenStyle.DashDotLine,
    "dashdotdot": Qt.PenStyle.DashDotDotLine,
    "center":     Qt.PenStyle.DashLine,       # closest Qt equivalent
    "phantom":    Qt.PenStyle.DashDotDotLine,
    "hidden":     Qt.PenStyle.DashLine,
}


def _line_style_to_qt(style: str) -> Qt.PenStyle:
    return _LINE_STYLE_MAP.get(style.lower(), Qt.PenStyle.SolidLine)
from typing import List, Optional

from app.document import DocumentStore
from app.entities import Vec2
from app.entities.base import GripPoint
from app.editor.osnap_engine import OsnapEngine, SnapResult
from app.editor.settings import EditorSettings
from app.editor.draftmate import (
    DraftmateEngine,
    DraftmateResult,
)
from app.editor.hit_testing import (
    hit_test_point,
    entity_inside_rect,
    entity_crosses_rect,
)
from app.ui.dynamic_input_widget import DynamicInputWidget
from app.ui.command_palette import CommandPaletteWidget
from app.ui.canvas_context_menu import CanvasContextMenu
from app.canvas_viewport import ViewportTransform
from app.canvas_grid import GridRenderer
from app.canvas_painting import (
    build_entity_base_pen,
    build_overlay_pen,
    draw_draftmate,
    draw_grips,
    draw_hover_overlay,
    draw_selection_rect,
    draw_snap_marker,
    draw_vector_rubberband,
)
from app.canvas_interaction import (
    collect_rect_selection_ids,
    find_hit_entity_id,
    find_hot_grip,
    is_window_selection,
    normalized_selection_rect,
    resolve_display_point,
    selection_drag_exceeds_threshold,
)
from app.canvas_command_flow import (
    should_update_dynamic_input,
    update_snap_and_draftmate,
)
from app.canvas_grip_flow import (
    activate_hot_grip,
    cleared_active_grip_state,
    commit_active_grip_edit,
    resolve_grip_final_position,
    update_active_grip_drag,
)


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
    # emitted when the user wants to open the command palette; carries the
    # seed character (empty string when opened with no pre-typed text)
    paletteRequested = Signal(str)

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
        parent: Optional[QWidget] = None,
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
        self.setCursor(Qt.CursorShape.CrossCursor)

        # receive mouse move events even when no button is pressed
        self.setMouseTracking(True)

        # Accept keyboard focus so key-press events (Escape, etc.) are received
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Document and editor — injected via constructor (preferred) or set
        # via the public properties below.
        self._document: Optional[DocumentStore] = document
        self._editor = editor
        # Cached preview entities from the last mouse-move callback.
        self._preview_entities: List = []
        # Last resolved cursor world position for fallback vector
        # rubberband rendering.
        self._cursor_world: Optional[Vec2] = None

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
        # Linked grips (on selected entities) that coincide with the active grip.
        self._linked_grips: List[GripPoint] = []
        # Per-entity snapshots mutated live during grip drag preview.
        self._grip_entity_snapshots: dict[str, object] = {}
        # Deep copies of entities before the grip drag started (for undo).
        self._grip_before_snapshots: List[object] = []
        # Mouse position in world coordinates during a grip drag.
        self._grip_drag_world: Optional[Vec2] = None

        # ---- Render cache (rubber band optimisation) -------------------------
        # Captured scene pixmap (grid + entities, no rubber band) reused during
        # selection drags so we only redraw the selection rect each frame.
        self._scene_cache: Optional[QPixmap] = None

        # ---- Entity render cache (general optimisation) ----------------------
        # Cached pixmap of grid + all entities + selection overlays.  Reused
        # across mouse-move frames; only hover highlight, snap markers,
        # previews and grips are painted fresh each frame on top.
        self._entity_cache: Optional[QPixmap] = None
        self._cache_generation: int = -1
        self._cache_scale: float = -1.0
        self._cache_offset_x: float = 0.0
        self._cache_offset_y: float = 0.0
        self._cache_width: int = 0
        self._cache_height: int = 0
        self._cache_dpr: float = 1.0
        self._cache_sel_ids: frozenset = frozenset()

        # ---- Dynamic input widget --------------------------------------------
        # Custom-painted input fields following the cursor during point/value input
        self._dynamic_input = DynamicInputWidget(parent=self)
        self._dynamic_input.hide()
        self._dynamic_input.input_submitted.connect(self._on_dynamic_input_submitted)
        self._dynamic_input.input_cancelled.connect(self._on_dynamic_input_cancelled)

        # ---- Command palette -------------------------------------------------
        self._command_palette = CommandPaletteWidget(parent=self)
        self._command_palette.dismissed.connect(self._command_palette.hide)

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
        if event.button() == Qt.MouseButton.LeftButton:
            posf = event.position() if hasattr(event, "position") else event.posF()
            world_pt = self.screen_to_world(posf)

            # ---- Grip: second click places the active grip ----
            if self._active_grip is not None:
                final_pos = resolve_grip_final_position(
                    Vec2(world_pt.x(), world_pt.y()),
                    self._snap_result,
                    self._grip_drag_world,
                )
                commit_active_grip_edit(
                    document=self._document,
                    active_grip=self._active_grip,
                    linked_grips=self._linked_grips,
                    final_pos=final_pos,
                    before_snapshots=self._grip_before_snapshots,
                    editor=self._editor,
                )
                # Reset grip state.
                (
                    self._active_grip,
                    self._grip_entity_snapshots,
                    self._grip_before_snapshots,
                    self._grip_drag_world,
                    self._linked_grips,
                ) = cleared_active_grip_state()
                self._snap_result = None
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.update()
                self.setFocus()
                return

            # ---- Grip activation: first click on a hot grip starts moving it ----
            if self._idle and self._hot_grip is not None:
                sel_ids = self._editor.selection.ids if self._editor is not None else set()
                (
                    self._active_grip,
                    self._grip_entity_snapshots,
                    self._grip_before_snapshots,
                    self._grip_drag_world,
                    self._linked_grips,
                ) = activate_hot_grip(
                    self._document,
                    self._hot_grip,
                    Vec2(world_pt.x(), world_pt.y()),
                    selected_ids=set(sel_ids),
                )
                # While a grip is active we render live previews from snapshots;
                # suppress stale hover overlay that would otherwise remain at
                # the entity's pre-commit position.
                self._hovered_entity_id = None
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
                from_point = getattr(self._editor, "snap_from_point", None)
                pt = resolve_display_point(
                    Vec2(world_pt.x(), world_pt.y()),
                    self._snap_result,
                    self._draftmate_result,
                    ortho=self._ortho,
                    from_point=from_point,
                )

                self.pointSelected.emit(pt.x, pt.y)
                # Clear preview immediately so the stale rubberband highlight
                # doesn't persist while the command processes the click.
                self._preview_entities = []
                # Clear tracked points after each click so the workspace
                # stays clean between drawing steps.
                self._draftmate.clear()
                self._draftmate_result = None
            self.setFocus()
            return

        # start panning with middle mouse button
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._vp._origin_locked = False
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        posf = event.position() if hasattr(event, "position") else event.posF()
        world_pt = self.screen_to_world(posf)
        raw = Vec2(world_pt.x(), world_pt.y())

        # ---- Active grip move (click-click mode) --------------------------
        if self._active_grip is not None:
            self._snap_result, display_grip, self._grip_entity_snapshots = update_active_grip_drag(
                raw,
                document=self._document,
                active_grip=self._active_grip,
                linked_grips=self._linked_grips,
                osnap_engine=self._osnap,
                osnap_master=self._osnap_master,
                scale=self.scale,
                grip_entity_snapshots=self._grip_entity_snapshots,
            )
            self._grip_drag_world = display_grip
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
            if (
                not self._sel_dragging
                and selection_drag_exceeds_threshold(
                    self._sel_origin_screen,
                    self._sel_current_screen,
                    self._sel_drag_threshold,
                )
            ):
                self._sel_dragging = True
                # Snapshot the current scene (no rubber band yet) so paintEvent
                # can reuse it every frame instead of doing a full redraw.
                self._scene_cache = self.grab()
            if self._sel_dragging:
                self.update()

        # ---- OSNAP --------------------------------------------------------
        # Command-mode flow: derive snap + Draftmate state from editor input mode.
        snap_active, self._snap_result, self._draftmate_result, from_point = update_snap_and_draftmate(
            active_grip=self._active_grip,
            editor=self._editor,
            document=self._document,
            osnap_master=self._osnap_master,
            osnap_engine=self._osnap,
            draftmate_engine=self._draftmate,
            raw=raw,
            scale=self.scale,
            existing_snap_result=self._snap_result,
        )

        # Resolve display point (Draftmate > OSNAP > raw, then Ortho if free).
        display = resolve_display_point(
            raw,
            self._snap_result,
            self._draftmate_result,
            ortho=self._ortho,
            from_point=from_point,
        )

        self._cursor_world = display

        try:
            self.mouseMoved.emit(display.x, display.y)
        except Exception:
            pass

        # Update rubberband preview using the best available position.
        if self._editor is not None:
            self._preview_entities = self._editor.get_dynamic(display)

        # ---- Dynamic input widget update ------------------------------------
        # Update dynamic input position and cursor coordinates whenever mouse moves
        if should_update_dynamic_input(self._editor, snap_active):
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
                self._hot_grip = find_hot_grip(
                    self._document,
                    sel_ids,
                    raw,
                    grip_tol,
                )
            # Update cursor shape for grip hover feedback
            if self._hot_grip is not None and old_hot is None:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            elif self._hot_grip is None and old_hot is not None:
                self.setCursor(Qt.CursorShape.CrossCursor)

            # ---- Entity hover detection -----------------------------------
            tolerance = self._pick_tolerance_px / self.scale
            new_hover = find_hit_entity_id(
                self._document,
                get_layer=self._document.get_layer,
                point_world=raw,
                tolerance_world=tolerance,
                hit_test_point=hit_test_point,
                use_bbox_rejection=True,
            )
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
        if event.button() == Qt.MouseButton.LeftButton and self._active_grip is not None:
            return

        if event.button() == Qt.MouseButton.LeftButton and self._sel_origin_screen is not None:
            posf = event.position() if hasattr(event, "position") else event.posF()
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._finish_selection(posf, shift)
            # Reset selection drag state
            self._sel_origin_screen = None
            self._sel_current_screen = None
            self._sel_origin_world = None
            self._sel_dragging = False
            self._scene_cache = None
            self.update()

        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.CrossCursor)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """Right-click context menu for common editing actions.

        Behaviour:
        - If idle and the click hits an entity, that entity becomes selected
          before the menu opens (standard CAD behaviour).
        - Menu actions are enabled/disabled based on editor state.
        """
        if self._editor is None:
            return
        editor = self._editor
        is_idle = self._idle

        # ---- Update selection based on right-click hit test (idle only) ----
        if is_idle:
            clicked_id: Optional[str] = None
            if self._document is not None:
                try:
                    click_world_qpt = self.screen_to_world(QPointF(event.pos()))
                    click_world = Vec2(click_world_qpt.x(), click_world_qpt.y())
                    tolerance = self._pick_tolerance_px / self.scale
                    clicked_id = find_hit_entity_id(
                        self._document,
                        get_layer=self._document.get_layer,
                        point_world=click_world,
                        tolerance_world=tolerance,
                        hit_test_point=hit_test_point,
                        use_bbox_rejection=False,
                    )
                except Exception:
                    clicked_id = None

            if clicked_id is not None:
                # Replace selection with the clicked entity if it wasn't selected.
                if clicked_id not in editor.selection:
                    editor.selection.set({clicked_id})
                self._hovered_entity_id = clicked_id

        undo_stack = editor.undo_stack
        has_sel = bool(editor.selection)
        last_cmd = editor.last_command_name
        can_repeat = bool(last_cmd) and is_idle
        cmd_option_labels = editor.command_option_labels if editor.is_running else []

        def _do_delete() -> None:
            if not editor.is_running and editor.selection:
                editor.delete_selection()
                editor.document_changed.emit()
                self._hovered_entity_id = None
                self.update()

        def _do_repeat() -> None:
            if not can_repeat:
                return
            # Repeat should not cancel an active command (menu isn't shown then),
            # but guard anyway.
            if editor.is_running:
                return
            if last_cmd:
                editor.run_command(last_cmd)

        menu = CanvasContextMenu(
            parent=self,
            is_idle=is_idle,
            can_undo=undo_stack.can_undo,
            can_redo=undo_stack.can_redo,
            undo_text="Undo",
            redo_text="Redo",
            has_selection=has_sel,
            repeat_label=f"Repeat: {last_cmd}" if last_cmd else "Repeat",
            can_repeat=can_repeat,
            command_option_labels=cmd_option_labels,
            on_command_option=editor.provide_command_option if cmd_option_labels else None,
            on_cancel=editor.cancel,
            on_undo=editor.undo,
            on_redo=editor.redo,
            on_delete=_do_delete,
            on_repeat=_do_repeat,
            on_move=lambda: editor.run_command("moveCommand"),
            on_rotate=lambda: editor.run_command("rotateCommand"),
            on_scale=lambda: editor.run_command("scaleCommand"),
        )
        menu.exec(event.globalPos())

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
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and self._dynamic_input.isVisible():
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
            (
                self._active_grip,
                self._grip_entity_snapshots,
                self._grip_before_snapshots,
                self._grip_drag_world,
                self._linked_grips,
            ) = cleared_active_grip_state()
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
        # Palette gets priority — Escape closes it rather than cancelling a command
        if self._command_palette.isVisible():
            self._command_palette.keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Escape:
            self.handle_escape()
            return

        # --- F10: toggle Draftmate (Object Snap Tracking + Polar Tracking) -
        if event.key() == Qt.Key.Key_F10:
            self._set_draftmate(not self._draftmate.settings.enabled)
            return

        # --- F8: toggle Ortho mode ----------------------------------------
        if event.key() == Qt.Key.Key_F8:
            self._set_ortho(not self._ortho)
            return

        # --- Delete key: remove selected entities when idle --------------
        if event.key() == Qt.Key.Key_Delete and self._idle:
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
            return

        # Any alphanumeric key while idle → open palette with that char pre-typed
        if self._idle:
            text = event.text()
            if text and (text.isalpha() or text.isdigit()):
                self.paletteRequested.emit(text)
                return

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
            origin_screen = self._sel_origin_screen
            if origin_world is None or origin_screen is None:
                return
            end_world_qpt = self.screen_to_world(release_pos)
            end_world = Vec2(end_world_qpt.x(), end_world_qpt.y())

            # Normalise the rectangle
            rmin, rmax = normalized_selection_rect(origin_world, end_world)

            # Direction determines mode:
            # screen-space left→right  ⇒  window  (fully inside)
            # screen-space right→left  ⇒  crossing (intersects)
            is_window = is_window_selection(origin_screen, release_pos)
            matched_ids = collect_rect_selection_ids(
                self._document,
                get_layer=self._document.get_layer,
                rmin=rmin,
                rmax=rmax,
                is_window=is_window,
                entity_inside_rect=entity_inside_rect,
                entity_crosses_rect=entity_crosses_rect,
            )

            if shift:
                selection.subtract(matched_ids)
            else:
                selection.extend(matched_ids)
        else:
            # ---- Point (click) selection --------------------------------
            click_world_qpt = self.screen_to_world(release_pos)
            click_world = Vec2(click_world_qpt.x(), click_world_qpt.y())
            tolerance = self._pick_tolerance_px / self.scale

            hit_id = find_hit_entity_id(
                self._document,
                get_layer=self._document.get_layer,
                point_world=click_world,
                tolerance_world=tolerance,
                hit_test_point=hit_test_point,
                use_bbox_rejection=False,
            )

            if hit_id is not None:
                if shift:
                    selection.remove(hit_id)
                else:
                    selection.add(hit_id)
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

        sel_ids = self._editor.selection.ids if self._editor is not None else set()
        hover_id = self._hovered_entity_id

        # ---- Rebuild entity cache if stale --------------------------------
        if not self._is_entity_cache_valid(sel_ids):
            self._rebuild_entity_cache(sel_ids)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Blit cached scene (grid + entities + selection overlays)
        if self._entity_cache is not None:
            painter.drawPixmap(0, 0, self._entity_cache)

        # ---- Draw hover overlay (idle only) -------------------------------
        # During grip edits, entities are previewed via snapshots while the live
        # document stays unchanged until commit; drawing hover overlay would
        # therefore appear "left behind" at the pre-commit location.
        if self._active_grip is None and hover_id is not None and self._document is not None:
            self._draw_hover_overlay(painter, hover_id, sel_ids)

        # ---- Draw grip squares for selected entities ----------------------
        if sel_ids and self._document is not None and (self._idle or self._active_grip is not None):
            self._draw_grips(painter, sel_ids)

        # Draw highlighted cutting-edge / boundary entities (red)
        if self._editor is not None:
            highlight = self._editor.get_highlight()
            if highlight:
                hl_pen = QPen(QColor(220, 50, 50), 2)
                painter.setPen(hl_pen)
                for e in highlight:
                    self._draw_entity(painter, e)

        # Draw dynamic / rubberband preview entities
        if self._preview_entities:
            preview_pen = QPen(QColor(0, 191, 255), 1)
            painter.setPen(preview_pen)
            for e in self._preview_entities:
                self._draw_entity(painter, e)

        # Fallback vector rubberband for get_point calls that are interpreted
        # as base-to-destination vector input and don't provide custom preview.
        vector_rb = self._vector_rubberband_world_points()
        if vector_rb is not None:
            self._draw_vector_rubberband(painter, vector_rb[0], vector_rb[1])

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

    # ------------------------------------------------------------------
    # Entity render cache
    # ------------------------------------------------------------------

    def _is_entity_cache_valid(self, sel_ids: set) -> bool:
        """Return True if the cached entity pixmap is still usable."""
        if self._entity_cache is None:
            return False
        # During grip editing the snapshot is mutated every frame.
        if self._active_grip is not None:
            return False
        doc_gen = self._document._generation if self._document else -1
        if doc_gen != self._cache_generation:
            return False
        if self._vp.scale != self._cache_scale:
            return False
        if (self._vp.offset.x() != self._cache_offset_x
                or self._vp.offset.y() != self._cache_offset_y):
            return False
        if self.width() != self._cache_width or self.height() != self._cache_height:
            return False
        if self.devicePixelRatio() != self._cache_dpr:
            return False
        if frozenset(sel_ids) != self._cache_sel_ids:
            return False
        return True

    def _rebuild_entity_cache(self, sel_ids: set) -> None:
        """Render grid + all entities + selection overlays into a cached pixmap."""
        w, h = self.width(), self.height()
        dpr = self.devicePixelRatio()
        # Create the pixmap at physical pixel resolution so blitting is crisp
        # on HiDPI/scaled displays (e.g. Windows 125 % / 150 % scaling).
        pixmap = QPixmap(int(w * dpr), int(h * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(QColor("#1E1E1E"))

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Grid
        self._draw_grid(p)

        # Entities
        if self._document is not None:
            tl = self.screen_to_world(QPointF(0, 0))
            br = self.screen_to_world(QPointF(w, h))
            vp_min_x = min(tl.x(), br.x())
            vp_min_y = min(tl.y(), br.y())
            vp_max_x = max(tl.x(), br.x())
            vp_max_y = max(tl.y(), br.y())

            for e in self._document:
                layer = self._document.get_layer(e.layer)
                if layer is not None and not layer.visible:
                    continue
                bb = e.bounding_box()
                if bb is not None and not bb.intersects_viewport(
                    vp_min_x, vp_min_y, vp_max_x, vp_max_y
                ):
                    continue

                draw_e = e
                if self._active_grip is not None and self._grip_entity_snapshots:
                    snap = self._grip_entity_snapshots.get(e.id)
                    if snap is not None:
                        draw_e = snap

                pen = build_entity_base_pen(
                    e,
                    self._document,
                    resolve_color=_resolve_color_str,
                    line_style_to_qt=_line_style_to_qt,
                )
                p.setPen(pen)
                self._draw_entity(p, draw_e)

                # Selection overlay (cached; hover overlay is drawn live)
                overlay_pen = build_overlay_pen(
                    pen,
                    is_selected=e.id in sel_ids,
                    is_hovered=False,
                )
                if overlay_pen is not None:
                    p.setPen(overlay_pen)
                    self._draw_entity(p, draw_e)

        p.end()

        self._entity_cache = pixmap
        self._cache_generation = self._document._generation if self._document else -1
        self._cache_scale = self._vp.scale
        self._cache_offset_x = self._vp.offset.x()
        self._cache_offset_y = self._vp.offset.y()
        self._cache_width = w
        self._cache_height = h
        self._cache_dpr = dpr
        self._cache_sel_ids = frozenset(sel_ids)

    def _draw_hover_overlay(self, painter: QPainter, hover_id: str, sel_ids: set) -> None:
        """Draw the semi-transparent hover highlight for a single entity."""
        if self._document is None:
            return
        draw_hover_overlay(
            painter,
            document=self._document,
            hover_id=hover_id,
            selected_ids=sel_ids,
            draw_entity=self._draw_entity,
            line_style_to_qt=_line_style_to_qt,
        )

    def _draw_snap_marker(self, painter: QPainter, snap: SnapResult) -> None:
        """Draw the OSNAP marker at the snap point in screen coordinates."""
        draw_snap_marker(
            painter,
            world_to_screen=self.world_to_screen,
            snap=snap,
        )

    # ------------------------------------------------------------------
    # Draftmate visual feedback
    # ------------------------------------------------------------------

    def _draw_draftmate(self, painter: QPainter, result: DraftmateResult) -> None:
        """Draw Draftmate guides and snapped-point indicator."""
        draw_draftmate(
            painter,
            world_to_screen=self.world_to_screen,
            result=result,
        )

    # ------------------------------------------------------------------
    # Grip rendering
    # ------------------------------------------------------------------

    def _draw_grips(self, painter: QPainter, sel_ids: set) -> None:
        """Draw CAD-style grip squares for selected entities."""
        draw_grips(
            painter,
            document=self._document,
            selected_ids=sel_ids,
            world_to_screen=self.world_to_screen,
            grip_half_size=self._grip_half_size,
            hot_grip=self._hot_grip,
            active_grip=self._active_grip,
            active_entity_snapshots=self._grip_entity_snapshots,
        )

    def _draw_selection_rect(self, painter: QPainter) -> None:
        """Draw the selection rectangle overlay in screen coordinates."""
        if self._sel_origin_screen is None or self._sel_current_screen is None:
            return
        draw_selection_rect(
            painter,
            origin_screen=self._sel_origin_screen,
            current_screen=self._sel_current_screen,
        )

    def _draw_entity(self, painter: QPainter, e) -> None:
        """Draw a single entity using the painter's current pen."""
        try:
            e.draw(painter, self.world_to_screen, self.scale)
        except Exception:
            import traceback; traceback.print_exc()

    def _vector_rubberband_world_points(self) -> Optional[tuple[Vec2, Vec2]]:
        """Return base/tip world points for fallback vector rubberband."""
        if self._editor is None:
            return None
        if self._editor.input_mode != "point":
            return None
        base = self._editor.snap_from_point
        if base is None:
            return None
        if self._cursor_world is None:
            return None
        if self._sel_dragging:
            return None
        return base, self._cursor_world

    def _draw_vector_rubberband(self, painter: QPainter, base: Vec2, tip: Vec2) -> None:
        """Draw a subtle dashed guide line from vector base to cursor tip."""
        draw_vector_rubberband(
            painter,
            world_to_screen=self.world_to_screen,
            base=base,
            tip=tip,
        )

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
        del sel_ids, hover_id  # base pen is independent of overlay state
        return build_entity_base_pen(
            e,
            self._document,
            resolve_color=_resolve_color_str,
            line_style_to_qt=_line_style_to_qt,
        )

    def _overlay_pen_for_entity(self, e, sel_ids: set, hover_id: Optional[str]) -> Optional[QPen]:
        """Compute the semi-transparent overlay QPen for hover/selection.

        Returns ``None`` when the entity is neither selected nor hovered.
        """
        is_sel = e.id in sel_ids
        is_hover = e.id == hover_id
        base_pen = self._pen_for_entity(e, sel_ids, hover_id)
        return build_overlay_pen(base_pen, is_selected=is_sel, is_hovered=is_hover)

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
            self._cursor_world = None
            self._dynamic_input.clear()
        elif mode in ("point", "integer", "float", "string", "choice", "angle", "length"):
            editor = self._editor
            if editor is None:
                self._dynamic_input.clear()
                return
            # Skip dynamic input when the active command has suppressed it
            # (e.g. Trim — the user is picking segments, not entering coords).
            if getattr(editor, "suppress_dynamic_input", False):
                self._dynamic_input.clear()
                return
            base_point = None
            if mode == "point":
                base_point = editor.snap_from_point
            choice_options = editor._choice_options if mode == "choice" else None
            angle_center = editor._angle_center if mode == "angle" else None
            length_base = editor._length_base if mode == "length" else None
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
        editor = self._editor
        if editor is None:
            return

        mode = editor._input_mode
        if mode == "point":
            if isinstance(value, Vec2):
                editor.provide_point(value)
        elif mode == "integer":
            if isinstance(value, (int, float, str)):
                editor.provide_integer(int(value))
        elif mode == "float":
            if isinstance(value, (int, float, str)):
                editor.provide_float(float(value))
        elif mode == "angle":
            if isinstance(value, (int, float, str)):
                editor.provide_angle(float(value))
        elif mode == "length":
            if isinstance(value, (int, float, str)):
                editor.provide_length(float(value))
        elif mode == "string":
            editor.provide_string(str(value))
        elif mode == "choice":
            editor.provide_choice(str(value))

    @Slot()
    def _on_dynamic_input_cancelled(self) -> None:
        """Forward cancellation to editor."""
        if self._editor is not None:
            self.cancelRequested.emit()
