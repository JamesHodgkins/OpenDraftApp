"""Regression tests for the Offset command (KNOWN_BUGS #3).

``OffsetCommand`` built new entities with ``copy.deepcopy``/``uuid.uuid4()``
but the module never imported ``copy`` or ``uuid``, so every call to
``commit()`` raised ``NameError`` and Offset silently did nothing.
"""
from __future__ import annotations

import pytest

from app.commands.modify_offset import _MODE_PICK_SIDE, OffsetCommand
from app.document import DocumentStore
from app.editor.editor import Editor
from app.entities import CircleEntity, LineEntity, PolylineEntity, Vec2


@pytest.fixture
def editor():
    doc = DocumentStore()
    return Editor(document=doc)


def test_offset_line_both_sides_adds_two_lines(editor):
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    assert cmd.start() is None

    cmd.distance = 2.0
    cmd.mode = "both"
    cmd.commit()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    # original + two offset copies
    assert len(lines) == 3
    ys = sorted(round(e.p1.y, 6) for e in lines)
    assert ys == [-2.0, 0.0, 2.0]


def test_offset_line_pick_side_adds_one_line(editor):
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    cmd.start()
    cmd.distance = 3.0
    cmd.mode = "pick side"
    cmd.side_point = Vec2(5, 5)  # above the line
    cmd.commit()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 2
    new_line = next(e for e in lines if e.id != line.id)
    assert new_line.p1.y == pytest.approx(3.0)


def test_offset_line_pick_side_accepts_keyboard_shortcut(editor):
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    cmd.start()
    cmd.distance = 3.0
    cmd.mode = "P"
    cmd.side_point = Vec2(5, 5)
    cmd.commit()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 2
    new_line = next(e for e in lines if e.id != line.id)
    assert new_line.p1.y == pytest.approx(3.0)


def test_offset_editor_commit_command_adds_entities_after_shortcut_mode(editor):
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    editor._active_command = cmd
    editor._last_command_name = "offsetCommand"
    cmd.start()

    editor.set_stateful_property("distance", 2.0)
    editor.set_stateful_property("mode", "B")
    assert cmd.all_exports_set()

    editor.commit_command()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 3
    assert editor.active_command is None


def test_offset_viewport_distance_click_measures_from_selected_geometry(editor):
    line = LineEntity(p1=Vec2(100, 100), p2=Vec2(110, 100))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    editor._active_command = cmd
    editor._last_command_name = "offsetCommand"
    cmd.start()

    editor.provide_point(Vec2(105, 103))
    assert cmd.distance == pytest.approx(3.0)
    assert cmd.active_export == "mode"

    editor.provide_choice("P")
    editor.provide_point(Vec2(105, 110))
    editor.commit_command()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 2
    new_line = next(e for e in lines if e.id != line.id)
    assert new_line.p1.y == pytest.approx(103.0)


def test_offset_pick_side_shortcut_does_not_suppress_viewport_side_click(editor):
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    editor._active_command = cmd
    editor._last_command_name = "offsetCommand"
    cmd.start()

    editor.set_stateful_property("distance", 3.0)
    editor.set_stateful_property("mode", "P")

    assert not editor.consume_click_point_suppressed()

    editor.provide_point(Vec2(5, 5))
    assert cmd.all_exports_set()
    editor.commit_command()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 2
    new_line = next(e for e in lines if e.id != line.id)
    assert new_line.p1.y == pytest.approx(3.0)


def test_offset_editor_choice_provider_clears_stale_typed_distance_suppression(editor):
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    editor._active_command = cmd
    editor._last_command_name = "offsetCommand"
    cmd.start()

    editor.set_stateful_property("distance", 3.0)
    assert editor._suppress_next_click_point is True
    editor.provide_choice("P")
    assert cmd.active_export == "side_point"
    assert not editor.consume_click_point_suppressed()

    editor.provide_point(Vec2(5, 5))
    editor.commit_command()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 2


def test_offset_two_viewport_clicks_complete_without_typing_mode(editor):
    """Clicking distance then clicking a side must finish Offset (KNOWN_BUGS).

    Previously the second click (answering "which side") was silently
    swallowed because the command was still waiting on the "both/pick side"
    choice export, which a canvas click can never answer. The user could only
    get unstuck by typing "B"/"P" manually. A click on that step should now
    be treated as "pick side" + this point in one gesture.
    """
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    editor._active_command = cmd
    editor._last_command_name = "offsetCommand"
    cmd.start()

    editor.provide_point(Vec2(5, 3))  # sets distance = 3.0 from the line
    assert cmd.active_export == "mode"

    editor.provide_point(Vec2(5, 5))  # click a side — should finish the command
    assert cmd.mode == _MODE_PICK_SIDE
    assert cmd.all_exports_set()

    editor.commit_command()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 2
    new_line = next(e for e in lines if e.id != line.id)
    assert new_line.p1.y == pytest.approx(3.0)


def test_offset_commit_failure_keeps_command_alive_instead_of_quitting(editor):
    """A failed commit() must return False, not silently tear the command down.

    ``Editor.commit_command()`` treats any non-``False`` return from
    ``commit()`` as "finished" and tears the command down (`_finish_stateful`)
    — even ``None``. Every one of Offset's own early-return guards used to
    return ``None`` on failure (invalid distance/mode/side, or no valid
    offset results), so hitting any of them from an auto-commit or a manual
    Enter silently killed the whole command instead of leaving it running for
    the user to correct — this is what "click completes on one side but the
    other side just quits the command" looks like from the outside.
    """
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    editor._active_command = cmd
    editor._last_command_name = "offsetCommand"
    cmd.start()

    # Force an invalid state commit() must reject (mode never chosen) without
    # going through the normal export-setting path, so we can drive
    # commit_command() directly regardless of auto-commit gating.
    cmd.distance = 5.0
    editor.commit_command()

    # The bug: this used to be None because _finish_stateful had already run.
    assert editor.active_command is cmd
    assert not cmd._is_committed


def test_offset_distance_click_on_the_geometry_itself_is_rejected(editor):
    """A click that measures ~0 distance must not silently stall the command.

    Clicking close enough to the selected geometry that the measured
    distance is ~0 used to still advance to the "mode" step (0.0 is not
    None), but `all_exports_set()` requires `distance > 0` — so auto-commit
    could never fire no matter which side was picked afterwards, and no
    status message ever explained why. The click should instead be rejected
    outright, leaving `distance` unset so the user can click again.
    """
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = OffsetCommand(editor)
    editor._active_command = cmd
    editor._last_command_name = "offsetCommand"
    cmd.start()

    editor.provide_point(Vec2(5, 0))  # exactly on the line: distance == 0

    assert cmd.distance is None
    assert cmd.active_export == "distance"


def test_offset_circle_grows_radius(editor):
    circle = CircleEntity(center=Vec2(0, 0), radius=5.0)
    editor.document.add_entity(circle)
    editor.selection.add(circle.id)

    cmd = OffsetCommand(editor)
    cmd.start()
    cmd.distance = 1.5
    cmd.mode = "both"
    cmd.commit()

    circles = [e for e in editor.document.entities if isinstance(e, CircleEntity)]
    radii = sorted(round(e.radius, 6) for e in circles)
    # both-sides on a circle only keeps the valid (positive-radius) result
    assert radii == [3.5, 5.0, 6.5]


def test_offset_closed_polyline_uses_closing_segment_for_corners(editor):
    poly = PolylineEntity(
        points=[
            Vec2(0, 0),
            Vec2(10, 0),
            Vec2(10, 10),
            Vec2(0, 10),
        ],
        closed=True,
    )
    editor.document.add_entity(poly)
    editor.selection.add(poly.id)

    cmd = OffsetCommand(editor)
    cmd.start()
    cmd.distance = 1.0
    cmd.mode = "P"
    cmd.side_point = Vec2(5, -5)
    cmd.commit()

    polylines = [e for e in editor.document.entities if isinstance(e, PolylineEntity)]
    assert len(polylines) == 2
    offset = next(e for e in polylines if e.id != poly.id)

    assert offset.closed is True
    assert offset.points[0].x == pytest.approx(-1.0)
    assert offset.points[0].y == pytest.approx(-1.0)
