"""Tests for CADCanvas coordinate transforms and origin anchoring.

These tests use pytest-qt to create a real QApplication, which is required
by PySide6 widget constructors.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent

from app.canvas import CADCanvas, _line_style_to_qt
from app.document import DocumentStore

from app.entities import Vec2, LineEntity


# helper for synthesising key events in tests
from PySide6.QtGui import QKeyEvent

def key(event, key_code, text=""):
    return QKeyEvent(QKeyEvent.KeyPress, key_code, Qt.NoModifier, text)


@pytest.fixture
def canvas(qtbot):
    """Create a canvas widget backed by an empty document and editor."""
    doc = DocumentStore()
    from app.editor.editor import Editor

    editor = Editor(document=doc)
    c = CADCanvas(document=doc, editor=editor)
    c.resize(800, 600)
    qtbot.addWidget(c)
    return c


class TestCoordinateTransforms:
    """Verify screen↔world round-trip at default settings."""

    def test_world_to_screen_roundtrip(self, canvas):
        world = QPointF(50, 30)
        screen = canvas.world_to_screen(world)
        back = canvas.screen_to_world(screen)
        assert back.x() == pytest.approx(world.x(), abs=1e-6)
        assert back.y() == pytest.approx(world.y(), abs=1e-6)

    def test_screen_to_world_roundtrip(self, canvas):
        screen = QPointF(200, 150)
        world = canvas.screen_to_world(screen)
        back = canvas.world_to_screen(world)
        assert back.x() == pytest.approx(screen.x(), abs=1e-6)
        assert back.y() == pytest.approx(screen.y(), abs=1e-6)

    def test_origin_maps_to_offset(self, canvas):
        """World origin should map to the inset position, not (0,0)."""
        sp = canvas.world_to_screen(QPointF(0, 0))
        # With bottom-left anchor and 10px inset, origin screen pos should be
        # near (10, height - 10)
        assert sp.x() == pytest.approx(10.0, abs=1.0)
        assert sp.y() == pytest.approx(canvas.height() - 10.0, abs=1.0)


class TestOriginAnchoring:
    def test_set_origin_bottom_left(self, canvas):
        canvas.set_origin_anchor("bottom-left", inset_x_px=20, inset_y_px=30)
        sp = canvas.world_to_screen(QPointF(0, 0))
        assert sp.x() == pytest.approx(20.0, abs=1.0)
        assert sp.y() == pytest.approx(canvas.height() - 30.0, abs=1.0)

    def test_set_origin_top_left(self, canvas):
        canvas.set_origin_anchor("top-left", inset_x_px=15, inset_y_px=15)
        sp = canvas.world_to_screen(QPointF(0, 0))
        assert sp.x() == pytest.approx(15.0, abs=1.0)
        assert sp.y() == pytest.approx(15.0, abs=1.0)

    def test_invalid_anchor_raises(self, canvas):
        with pytest.raises(ValueError):
            canvas.set_origin_anchor("center")

    def test_resize_preserves_anchor(self, canvas):
        canvas.set_origin_anchor("bottom-left", inset_x_px=10, inset_y_px=10)
        canvas.setFixedSize(1024, 768)
        # update_offset_for_size is called by resizeEvent, but setFixedSize
        # may not fire events in test; call it manually.
        canvas._vp.update_offset_for_size(canvas.width(), canvas.height())
        sp = canvas.world_to_screen(QPointF(0, 0))
        assert sp.x() == pytest.approx(10.0, abs=1.0)
        assert sp.y() == pytest.approx(canvas.height() - 10.0, abs=1.0)

    def test_positive_y_goes_up(self, canvas):
        """World +Y should map to a lower screen Y (upward on screen)."""
        canvas.set_origin_anchor("bottom-left", inset_x_px=0, inset_y_px=0)
        s0 = canvas.world_to_screen(QPointF(0, 0))
        s1 = canvas.world_to_screen(QPointF(0, 10))
        assert s1.y() < s0.y()

    def test_positive_x_goes_right(self, canvas):
        """World +X should map to higher screen X."""
        canvas.set_origin_anchor("bottom-left", inset_x_px=0, inset_y_px=0)
        s0 = canvas.world_to_screen(QPointF(0, 0))
        s1 = canvas.world_to_screen(QPointF(10, 0))
        assert s1.x() > s0.x()


class TestScaling:
    def test_zoom_in(self, canvas):
        """Doubling scale should double screen distances."""
        canvas.scale = 1.0
        canvas._vp.update_offset_for_size(canvas.width(), canvas.height())
        s0 = canvas.world_to_screen(QPointF(0, 0))
        s10 = canvas.world_to_screen(QPointF(10, 0))
        delta1 = s10.x() - s0.x()

        canvas.scale = 2.0
        canvas._vp.update_offset_for_size(canvas.width(), canvas.height())
        s0 = canvas.world_to_screen(QPointF(0, 0))
        s10 = canvas.world_to_screen(QPointF(10, 0))
        delta2 = s10.x() - s0.x()

        assert delta2 == pytest.approx(delta1 * 2, abs=1.0)


def test_entity_override_pen(canvas):
    """Verify the pen computed for entities respects overrides and selection.

    The rendering model uses two passes:
      1. Base pen — always reflects the true entity properties (overrides).
      2. Overlay pen — semi-transparent highlight for hover/selection.
    ``_pen_for_entity`` returns the base pen; ``_overlay_pen_for_entity``
    returns the overlay pen (or None when neither hovered nor selected).
    """
    from app.entities import LineEntity

    # prepare document and editor-like stub
    doc = canvas._document
    # add an entity on default layer
    e = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    doc.add_entity(e)

    # no overrides, not selected — base pen matches layer defaults
    pen = canvas._pen_for_entity(e, sel_ids=set(), hover_id=None)
    assert pen.widthF() == pytest.approx(doc.layers[0].thickness)
    assert pen.style() == _line_style_to_qt(doc.layers[0].line_style)
    # no overlay when not hovered/selected
    assert canvas._overlay_pen_for_entity(e, sel_ids=set(), hover_id=None) is None

    # apply explicit weight override
    e.line_weight = 3.0
    pen = canvas._pen_for_entity(e, sel_ids=set(), hover_id=None)
    assert pen.widthF() == pytest.approx(3.0)

    # style override
    e.line_style = "dotted"
    pen = canvas._pen_for_entity(e, sel_ids=set(), hover_id=None)
    assert pen.style() == Qt.DotLine

    # now select the entity — base pen still has true overrides
    pen = canvas._pen_for_entity(e, sel_ids={e.id}, hover_id=None)
    assert pen.widthF() == pytest.approx(3.0)
    assert pen.style() == Qt.DotLine
    # overlay pen exists with selection colour (semi-transparent blue)
    overlay = canvas._overlay_pen_for_entity(e, sel_ids={e.id}, hover_id=None)
    assert overlay is not None
    assert overlay.color().alpha() < 255  # semi-transparent
    assert overlay.color().red() == 0 and overlay.color().green() == 150 and overlay.color().blue() == 255
    assert overlay.style() == Qt.DotLine  # overlay preserves style

    # hover on top of selection — base pen still reflects overrides
    pen = canvas._pen_for_entity(e, sel_ids={e.id}, hover_id=e.id)
    assert pen.widthF() == pytest.approx(3.0)
    assert pen.style() == Qt.DotLine
    # overlay uses hover+sel colour
    overlay = canvas._overlay_pen_for_entity(e, sel_ids={e.id}, hover_id=e.id)
    assert overlay is not None
    assert overlay.color().red() == 80 and overlay.color().green() == 180 and overlay.color().blue() == 255
    assert overlay.style() == Qt.DotLine

    # colour override always takes effect on the base pen
    e.color = "#123456"
    pen = canvas._pen_for_entity(e, sel_ids=set(), hover_id=None)
    assert pen.color() == QColor("#123456")

    # colour override visible even when hovered — base pen shows true colour
    pen = canvas._pen_for_entity(e, sel_ids=set(), hover_id=e.id)
    assert pen.color() == QColor("#123456")
    # overlay is present with hover colour
    overlay = canvas._overlay_pen_for_entity(e, sel_ids=set(), hover_id=e.id)
    assert overlay is not None
    assert overlay.color().red() == 255 and overlay.color().green() == 200 and overlay.color().blue() == 0


def test_delete_selected_entities(canvas):
    """Pressing Delete with a non-empty selection should remove those items."""
    doc = canvas._document
    # add a couple of lines and select them
    e1 = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    e2 = LineEntity(p1=Vec2(2, 2), p2=Vec2(3, 3))
    doc.add_entity(e1)
    doc.add_entity(e2)
    canvas._editor.selection.add(e1.id)
    canvas._editor.selection.add(e2.id)

    # pretend the user was hovering one of them when they hit Delete
    canvas._hovered_entity_id = e1.id

    canvas.keyPressEvent(key(None, Qt.Key_Delete))
    # both should be removed
    assert doc.get_entity(e1.id) is None
    assert doc.get_entity(e2.id) is None
    assert not canvas._editor.selection
    # hover state should have been reset
    assert canvas._hovered_entity_id is None


def test_delete_without_selection_does_nothing(canvas):
    """Hitting Delete with nothing selected should be a no-op."""
    doc = canvas._document
    e = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1))
    doc.add_entity(e)
    # ensure selection empty
    canvas._editor.selection.clear()
    canvas.keyPressEvent(key(None, Qt.Key_Delete))
    # entity still present
    assert doc.get_entity(e.id) is e


def test_vector_rubberband_points_require_point_mode_base_and_cursor(canvas):
    base = Vec2(1, 2)
    tip = Vec2(6, 7)

    canvas._editor._input_mode = "point"
    canvas._editor.snap_from_point = base
    canvas._cursor_world = tip
    canvas._preview_entities = []

    assert canvas._vector_rubberband_world_points() == (base, tip)


def test_vector_rubberband_points_visible_with_preview_entities(canvas):
    base = Vec2(1, 2)
    tip = Vec2(6, 7)

    canvas._editor._input_mode = "point"
    canvas._editor.snap_from_point = base
    canvas._cursor_world = tip

    # Command preview entities should not suppress the vector guide.
    canvas._preview_entities = [LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1))]
    assert canvas._vector_rubberband_world_points() == (base, tip)


def test_vector_rubberband_points_hidden_for_missing_context(canvas):
    tip = Vec2(6, 7)

    canvas._editor._input_mode = "point"
    canvas._editor.snap_from_point = None
    canvas._cursor_world = tip
    assert canvas._vector_rubberband_world_points() is None

    canvas._editor._input_mode = "integer"
    assert canvas._vector_rubberband_world_points() is None


def test_input_mode_none_clears_cursor_world_state(canvas):
    canvas._cursor_world = Vec2(3, 4)
    canvas._on_editor_input_mode_changed("none")
    assert canvas._cursor_world is None


def test_refresh_recomputes_dynamic_preview_without_mouse_move(canvas):
    tip = Vec2(12, 8)
    canvas._cursor_world = tip
    canvas._preview_entities = []

    canvas._editor.set_dynamic(lambda m: [LineEntity(p1=Vec2(0, 0), p2=m)])
    canvas.refresh()

    assert len(canvas._preview_entities) == 1
    ent = canvas._preview_entities[0]
    assert isinstance(ent, LineEntity)
    assert ent.p2 == tip


def test_click_honours_snap_even_when_stale_move_cleared_it(canvas, qtbot):
    """Regression test for KNOWN_BUGS #1.

    A mouseMoveEvent firing a hair before the click (cursor jitter during the
    button press) can move the cursor off the snap aperture and clear
    `_snap_result`, even though the snap marker was visually active a moment
    earlier. The click handler must recompute the snap at the actual click
    position rather than trusting a possibly-stale `_snap_result`.
    """
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent

    doc = canvas._document
    endpoint = Vec2(10, 10)
    doc.add_entity(LineEntity(p1=endpoint, p2=Vec2(20, 0)))

    canvas._editor._input_mode = "point"
    canvas._editor.snap_from_point = None
    canvas._editor._active_command = object()  # force is_running -> command mode

    received = []
    canvas.pointSelected.connect(lambda x, y: received.append(Vec2(x, y)))

    screen_pt = canvas.world_to_screen(QPointF(endpoint.x, endpoint.y))

    # Simulate the stale-clear: a move event just before the click already
    # wiped out the cached snap result.
    canvas._snap_result = None

    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        screen_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(event)

    assert len(received) == 1
    assert received[0].x == pytest.approx(endpoint.x, abs=1e-6)
    assert received[0].y == pytest.approx(endpoint.y, abs=1e-6)


def test_escape_during_grip_drag_invalidates_stale_render_cache(canvas):
    """Regression test for KNOWN_BUGS #5.

    Dragging a grip forces the entity render cache to rebuild every frame
    from the *live drag preview* (snapshot) positions. Cancelling the drag
    with Escape resets the grip state but never touched the document, so
    nothing in `_is_entity_cache_valid` noticed the switch back to "draw the
    real document" — the last drag-frame pixmap kept being reused until some
    unrelated change (pan/zoom/selection) invalidated it. The entity looked
    like it stayed at the dragged position even though the underlying data
    was already back to normal.
    """
    doc = canvas._document
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    doc.add_entity(line)
    canvas._editor.selection.add(line.id)

    grip = line.grip_points()[0]  # endpoint grip at p1
    canvas._hot_grip = grip
    canvas.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            canvas.world_to_screen(QPointF(grip.position.x, grip.position.y)),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert canvas._active_grip is not None

    # Drag it somewhere else and render — this rebuilds the cache from the
    # dragged snapshot, exactly like a real drag would.
    canvas._osnap_master = False  # avoid incidental snapping in the test
    canvas.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            canvas.world_to_screen(QPointF(5, 5)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    canvas.show()
    canvas.repaint()
    assert canvas._entity_cache is not None  # sanity: cache was populated

    canvas.handle_escape()

    assert canvas._active_grip is None
    assert canvas._entity_cache is None  # forced to rebuild on next paint
    # The document itself was never mutated by the cancelled drag.
    assert line.p1 == Vec2(0, 0)


def test_ctrl_press_toggles_sticky_grip_lock(canvas):
    """Ctrl is a sticky toggle for the active grip drag, not a held modifier.

    Pressing Ctrl once locks the grip to the entity's existing path (line
    direction / arc radius); pressing it again unlocks it. The lock does
    not require Ctrl to stay held down, and resets when the drag ends.
    """
    doc = canvas._document
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    doc.add_entity(line)
    canvas._editor.selection.add(line.id)
    canvas._osnap_master = False  # avoid incidental snapping in the test

    grip = line.grip_points()[1]  # endpoint grip at p2
    canvas._hot_grip = grip
    canvas.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            canvas.world_to_screen(QPointF(grip.position.x, grip.position.y)),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert canvas._active_grip is not None
    assert canvas._grip_constrain_locked is False

    ctrl_press = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.NoModifier
    )
    canvas.keyPressEvent(ctrl_press)
    assert canvas._grip_constrain_locked is True

    canvas.keyPressEvent(ctrl_press)
    assert canvas._grip_constrain_locked is False

    # Lock it, then drag off-axis and commit — the committed endpoint must
    # land on the line's original direction (y stays 0), proving the lock
    # (not a held modifier) drove the constrained move_grip call.
    canvas.keyPressEvent(ctrl_press)
    assert canvas._grip_constrain_locked is True

    canvas.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            canvas.world_to_screen(QPointF(7, 3)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    canvas.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            canvas.world_to_screen(QPointF(7, 3)),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert canvas._active_grip is None
    assert line.p2.y == pytest.approx(0.0)
    assert line.p2.x == pytest.approx(7.0)
    # The toggle resets once the drag is committed.
    assert canvas._grip_constrain_locked is False


def test_export_thumbnail_png_returns_png_signature(canvas):
    doc = canvas._document
    doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(25, 15)))

    png = canvas.export_thumbnail_png(width=128, height=96)

    assert png is not None
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_command_mode_click_does_not_steal_focus_from_input_row(qtbot):
    """Regression test — command inputs lost focus right after entering a point.

    A canvas click delivers a point to the active command via
    ``pointSelected`` — synchronously, inside that same call, the editor
    advances ``active_export`` and the controller panel moves keyboard focus
    to the next row. ``mousePressEvent`` used to unconditionally call
    ``self.setFocus()`` right after, silently undoing that and stranding
    focus (and the next keystrokes) on the canvas. It must only claim focus
    for itself in selection mode (no command running); a command-mode click
    leaves focus wherever the point-delivery handler already put it.

    Canvas and the stand-in "input row" are parented under one shared
    top-level widget — like the real app, where canvas and the controller
    panel both live inside ``MainWindow`` — since ``setFocus()`` only
    steals focus *within* the same top-level window; two independent
    top-levels don't fight over OS-level focus at all, which would make
    this test pass even without the fix.
    """
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget
    from app.editor.editor import Editor

    doc = DocumentStore()
    editor = Editor(document=doc)

    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    canvas = CADCanvas(document=doc, editor=editor)
    other = QLineEdit()
    layout.addWidget(canvas)
    layout.addWidget(other)
    host.show()
    host.activateWindow()
    qtbot.waitExposed(host)
    canvas.setFocus()
    qtbot.waitUntil(canvas.hasFocus)

    editor._input_mode = "point"
    editor.snap_from_point = None
    editor._active_command = object()  # force is_running -> command mode

    def _simulate_panel_focus_move(_x, _y):
        # Mirrors what really happens: provide_point() synchronously advances
        # the command and the panel focuses the next row's input widget —
        # all before mousePressEvent finishes running.
        other.setFocus()

    canvas.pointSelected.connect(_simulate_panel_focus_move)

    screen_pt = canvas.world_to_screen(QPointF(5, 5))
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        screen_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(event)

    assert other.hasFocus()
    assert not canvas.hasFocus()


def test_click_does_not_override_manually_typed_value(canvas):
    """Regression test — a manually-typed value must beat a click that follows it.

    Typing "100<45" into the End vector row and then clicking the viewport
    (without pressing Enter first) used to silently discard the typed value:
    the click's own focus-out commits the pending text via
    ``QLineEdit.editingFinished`` -> ``PropertiesPanel.property_changed`` ->
    ``Editor.set_stateful_property`` *before* ``mousePressEvent`` runs its own
    point-delivery — but that same click then also emitted ``pointSelected``,
    which clobbered the just-set value with the raw mouse position. Manual
    entry must take precedence.
    """
    import math
    from app.commands.draw_line import DrawLineCommand

    editor = canvas._editor

    cmd = DrawLineCommand(editor)
    editor._active_command = cmd
    cmd.start()
    cmd.start_point = Vec2(0, 0)
    cmd.active_export = "end_point"

    # Simulate the panel row's editingFinished -> set_stateful_property path
    # (the exact call PropertiesPanel._on_edit_finished triggers), which the
    # real UI fires synchronously when a click carries focus away from a row
    # that still has valid, uncommitted typed text ("100<45" parsed as a
    # length<angle vector).
    typed_vector = Vec2(100 * math.cos(math.radians(45)), 100 * math.sin(math.radians(45)))
    editor.set_stateful_property("end_point", typed_vector)
    assert cmd.end_point == typed_vector

    # The click that triggered the above focus-out now reaches mousePressEvent.
    screen_pt = canvas.world_to_screen(QPointF(5, 5))  # nowhere near the typed vector
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        screen_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(event)

    # The typed value must survive — not be overwritten by the click position.
    assert cmd.end_point == typed_vector


def test_normal_click_still_delivers_point_after_suppression_consumed(canvas):
    """The suppression is one-shot — a later, unrelated click still works."""
    editor = canvas._editor
    editor._input_mode = "point"
    editor._active_command = object()  # force is_running -> command mode

    received = []
    canvas.pointSelected.connect(lambda x, y: received.append(Vec2(x, y)))

    screen_pt = canvas.world_to_screen(QPointF(5, 5))
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        screen_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(event)

    assert len(received) == 1


def test_stale_click_suppression_does_not_eat_a_later_unrelated_click(canvas, qtbot):
    """A row commit via Enter/Space (no click involved) must not eat the next click.

    ``set_stateful_property``'s click-suppression flag (KNOWN_BUGS #11) has to
    arm speculatively, because a genuine click-away focus-out and a deliberate
    Enter/Space commit both reach it the same way — there's no way to tell
    them apart at that point. But #11's fix left the flag armed until
    *whatever* click happened to consume it next, with no expiry — so typing
    a value and pressing Enter (no click involved at all) would silently
    swallow an entirely separate, later click (KNOWN_BUGS #13: e.g. Offset's
    side-pick click after typing its distance, which read as "the command
    just resets" once some other action finally hit ``commit()``). The flag
    must not survive past the event-loop tick it was armed in — a real
    same-gesture click's own point delivery happens synchronously within the
    same call stack, before that tick ever runs.
    """
    from app.commands.modify_offset import OffsetCommand
    from app.entities import LineEntity

    editor = canvas._editor
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    editor._active_command = cmd
    editor._last_command_name = "offsetCommand"
    cmd.start()

    # Enter/Space commit — no click involved, unlike test_click_does_not_override_manually_typed_value.
    # Distance alone doesn't finish the command (mode/side_point are still
    # unset), so no auto-commit races the suppression-flag expiry below.
    editor.set_stateful_property("distance", 3.0)
    assert editor._suppress_next_click_point is True

    # Let the event loop reach the next tick, as real usage would between a
    # keypress and a later, separate mouse click.
    qtbot.wait(10)
    assert editor._suppress_next_click_point is False

    received = []
    canvas.pointSelected.connect(lambda x, y: received.append(Vec2(x, y)))
    screen_pt = canvas.world_to_screen(QPointF(7, 7))
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        screen_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(event)

    assert len(received) == 1


def test_idle_click_still_focuses_canvas_for_selection(qtbot):
    """Selection-mode clicks (no command running) still claim canvas focus."""
    from app.editor.editor import Editor

    doc = DocumentStore()
    editor = Editor(document=doc)
    canvas = CADCanvas(document=doc, editor=editor)
    canvas.resize(800, 600)
    qtbot.addWidget(canvas)

    editor._active_command = None  # idle -> selection mode
    canvas.show()
    canvas.activateWindow()
    qtbot.waitExposed(canvas)

    screen_pt = canvas.world_to_screen(QPointF(5, 5))
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        screen_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(event)

    qtbot.waitUntil(canvas.hasFocus)
