"""Tests for the keyboard-first command workflow.

Covers:

* ``StatefulCommandBase.all_exports_set`` and ``seed_from_previous`` hook.
* ``Editor.auto_complete_enabled`` triggers ``commit_command`` once every
  exported property has a non-``None`` value.
* ``Editor.repeat_command_enabled`` re-launches the same command after a
  commit, and the new instance receives the previous one via
  ``seed_from_previous``.
* Cancellation does *not* trigger an auto-repeat.
* ``DrawLineCommand.seed_from_previous`` chains Start = prev End and moves
  the active export to ``end_point``.
"""
from __future__ import annotations

import pytest

from app.document import DocumentStore
from app.editor.editor import Editor
from app.editor.stateful_command import PartialPoint
from app.entities import CircleEntity, LineEntity, PolylineEntity, SplineEntity, Vec2


# Importing the command module registers it under "lineCommand" via the
# ``@command`` decorator.  Tests use this registration.
from app.commands import draw_line as _draw_line_module  # noqa: F401
from app.commands import draw_circle as _draw_circle_module  # noqa: F401
from app.commands import draw_polyline as _draw_polyline_module  # noqa: F401
from app.commands import draw_spline as _draw_spline_module  # noqa: F401
from app.commands.draw_line import DrawLineCommand
from app.commands.draw_polyline import DrawPolylineCommand
from app.commands.draw_spline import DrawSplineCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_editor(qtbot) -> Editor:
    """Create a fresh editor with an empty document, attached to qtbot."""
    doc = DocumentStore()
    ed = Editor(document=doc)
    # qtbot needs *some* widget, but Editor is a QObject — we just need
    # an event loop, which the qtbot fixture sets up implicitly.
    return ed


def _wait_for(qtbot, predicate, timeout_ms: int = 500) -> None:
    """Wait until *predicate* returns truthy or timeout."""
    qtbot.waitUntil(predicate, timeout=timeout_ms)


# ---------------------------------------------------------------------------
# StatefulCommandBase additions
# ---------------------------------------------------------------------------

class TestStatefulCommandBaseHooks:
    def test_all_exports_set_initially_false(self, qtbot):
        ed = _make_editor(qtbot)
        cmd = DrawLineCommand(ed)
        assert cmd.all_exports_set() is False

    def test_all_exports_set_true_when_filled(self, qtbot):
        ed = _make_editor(qtbot)
        cmd = DrawLineCommand(ed)
        cmd.start_point = Vec2(0, 0)
        cmd.end_point = Vec2(1, 1)
        assert cmd.all_exports_set() is True

    def test_seed_from_previous_default_is_noop(self, qtbot):
        ed = _make_editor(qtbot)
        a = DrawLineCommand(ed)
        a.start_point = Vec2(2, 3)
        a.end_point = Vec2(4, 5)
        b = DrawLineCommand(ed)
        # Force the default base implementation, not the DrawLine override.
        from app.editor.stateful_command import StatefulCommandBase
        StatefulCommandBase.seed_from_previous(b, a)
        assert b.start_point is None
        assert b.end_point is None


class TestStatefulCommandHelperApi:
    def test_begin_resets_exports_and_sets_active(self, qtbot):
        ed = _make_editor(qtbot)
        cmd = DrawLineCommand(ed)

        cmd.start_point = Vec2(1, 2)
        cmd.end_point = Vec2(3, 4)
        cmd.begin(
            active_export="end_point",
            reset=("start_point", "end_point"),
            snap_from=Vec2(9, 9),
        )

        assert cmd.start_point is None
        assert cmd.end_point is None
        assert cmd.active_export == "end_point"
        assert ed.snap_from_point == Vec2(9, 9)

    def test_point_vector_preview_helpers_support_partial_values(self, qtbot):
        ed = _make_editor(qtbot)
        cmd = DrawLineCommand(ed)

        cmd.start_point = PartialPoint(x=5, y=None)
        assert cmd.point_value("start_point") is None
        assert cmd.point_preview("start_point", Vec2(2, 3)) == Vec2(5, 3)

        cmd.end_point = PartialPoint(x=None, y=2)
        assert cmd.vector_value("end_point") is None
        assert cmd.vector_preview(
            "end_point",
            Vec2(10, 12),
            base=Vec2(7, 7),
        ) == Vec2(3, 2)

    def test_set_snap_for_active_prefers_first_available_candidate(self, qtbot):
        ed = _make_editor(qtbot)
        cmd = DrawLineCommand(ed)

        cmd.active_export = "start_point"
        cmd.set_snap_for_active(
            {"start_point": (None, Vec2(1, 1), Vec2(2, 2))},
            default=(Vec2(9, 9),),
        )
        assert ed.snap_from_point == Vec2(1, 1)

        cmd.active_export = "end_point"
        cmd.set_snap_for_active(
            {"start_point": Vec2(3, 3)},
            default=(None, Vec2(4, 4)),
        )
        assert ed.snap_from_point == Vec2(4, 4)


# ---------------------------------------------------------------------------
# Auto-complete
# ---------------------------------------------------------------------------

class TestAutoComplete:
    def test_two_clicks_auto_commit_a_line(self, qtbot):
        ed = _make_editor(qtbot)
        ed.repeat_command_enabled = False  # isolate auto-complete from repeat
        ed.auto_complete_enabled = True

        ed.run_command("lineCommand")
        assert ed.is_running

        # First click locks the start point; second click would normally
        # require a manual Enter / Commit, but auto-complete fires on the
        # next event-loop tick once both exports have a value.
        ed.provide_point(Vec2(0, 0))
        ed.provide_point(Vec2(10, 5))

        _wait_for(qtbot, lambda: any(
            isinstance(e, LineEntity) for e in ed.document.entities
        ))

        line = next(e for e in ed.document.entities if isinstance(e, LineEntity))
        assert line.p1 == Vec2(0, 0)
        assert line.p2 == Vec2(10, 5)
        # The command finished (or was repeated, but we disabled repeat).
        assert not ed.is_running

    def test_auto_complete_disabled_does_not_auto_commit(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = False
        ed.repeat_command_enabled = False

        ed.run_command("lineCommand")
        ed.provide_point(Vec2(0, 0))
        ed.provide_point(Vec2(10, 5))

        # Give any pending QTimer.singleShot(0, ...) a chance to misfire.
        qtbot.wait(50)

        # No line should have been committed.
        assert not any(isinstance(e, LineEntity) for e in ed.document.entities)
        # The command is still running, awaiting a manual commit.
        assert ed.is_running

    def test_line_end_vector_is_relative_to_start(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = True
        ed.repeat_command_enabled = False

        ed.run_command("lineCommand")
        ed.provide_point(Vec2(2, 3))

        # End export is vector-kind: (5, -1) from start => endpoint (7, 2).
        ed.set_stateful_property("end_point", Vec2(5, -1))

        _wait_for(qtbot, lambda: any(
            isinstance(e, LineEntity) for e in ed.document.entities
        ))

        line = next(e for e in ed.document.entities if isinstance(e, LineEntity))
        assert line.p1 == Vec2(2, 3)
        assert line.p2 == Vec2(7, 2)

    def test_circle_radius_vector_property_commits_expected_radius(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = True
        ed.repeat_command_enabled = False

        ed.run_command("circleCommand")
        ed.provide_point(Vec2(10, 10))

        # Radius export is vector-kind and named "radius".
        ed.set_stateful_property("radius", Vec2(3, 4))

        _wait_for(qtbot, lambda: any(
            isinstance(e, CircleEntity) for e in ed.document.entities
        ))

        circle = next(e for e in ed.document.entities if isinstance(e, CircleEntity))
        assert circle.center == Vec2(10, 10)
        assert circle.radius == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Repeat command + chain seeding
# ---------------------------------------------------------------------------

class TestRepeatCommand:
    def test_repeat_restarts_same_command_after_commit(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = True
        ed.repeat_command_enabled = True

        ed.run_command("lineCommand")
        first_cmd = ed.active_command
        assert isinstance(first_cmd, DrawLineCommand)

        ed.provide_point(Vec2(0, 0))
        ed.provide_point(Vec2(5, 5))

        # Wait for auto-commit to add the line AND repeat to install a
        # *new* DrawLineCommand instance (distinct from the first one).
        _wait_for(qtbot, lambda: (
            any(isinstance(e, LineEntity) for e in ed.document.entities)
            and isinstance(ed.active_command, DrawLineCommand)
            and ed.active_command is not first_cmd
        ))

        assert ed.active_command is not first_cmd

    def test_repeat_chains_drawline_start_to_previous_end(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = True
        ed.repeat_command_enabled = True

        ed.run_command("lineCommand")
        first_cmd = ed.active_command
        assert isinstance(first_cmd, DrawLineCommand)

        ed.provide_point(Vec2(0, 0))
        ed.provide_point(Vec2(7, 0))

        _wait_for(qtbot, lambda: (
            isinstance(ed.active_command, DrawLineCommand)
            and ed.active_command is not first_cmd
        ))

        new_cmd = ed.active_command
        assert isinstance(new_cmd, DrawLineCommand)
        # seed_from_previous should have copied the previous end point as
        # the new start point and moved the active export to end_point.
        assert new_cmd.start_point == Vec2(7, 0)
        assert new_cmd.end_point is None
        assert new_cmd.active_export == "end_point"

    def test_repeat_disabled_does_not_relaunch(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = True
        ed.repeat_command_enabled = False

        ed.run_command("lineCommand")
        ed.provide_point(Vec2(0, 0))
        ed.provide_point(Vec2(1, 1))

        _wait_for(qtbot, lambda: any(
            isinstance(e, LineEntity) for e in ed.document.entities
        ))
        # Give the timer queue a chance to fire any stray re-launch.
        qtbot.wait(50)

        assert ed.active_command is None
        assert not ed.is_running

    def test_cancel_does_not_repeat(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = False  # avoid stray auto-commit
        ed.repeat_command_enabled = True

        ed.run_command("lineCommand")
        assert ed.is_running

        ed.cancel_command()
        qtbot.wait(50)

        # Repeat is only triggered by commit_command, never by cancel.
        assert ed.active_command is None
        assert not ed.is_running


class TestVariableLengthStatefulCommands:
    def test_polyline_collects_points_and_finishes_on_escape(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = True
        ed.repeat_command_enabled = True

        ed.run_command("polylineCommand")
        assert isinstance(ed.active_command, DrawPolylineCommand)

        ed.provide_point(Vec2(0, 0))
        _wait_for(
            qtbot,
            lambda: isinstance(ed.active_command, DrawPolylineCommand)
            and len(getattr(ed.active_command, "_points", [])) == 1,
        )
        assert not any(isinstance(e, PolylineEntity) for e in ed.document.entities)

        ed.provide_point(Vec2(5, 0))
        _wait_for(
            qtbot,
            lambda: isinstance(ed.active_command, DrawPolylineCommand)
            and len(getattr(ed.active_command, "_points", [])) == 2,
        )
        assert not any(isinstance(e, PolylineEntity) for e in ed.document.entities)

        ed.cancel_command()
        _wait_for(qtbot, lambda: not ed.is_running)

        polys = [e for e in ed.document.entities if isinstance(e, PolylineEntity)]
        assert len(polys) == 1
        assert polys[0].points == [Vec2(0, 0), Vec2(5, 0)]

    def test_spline_collects_control_points_and_finishes_on_escape(self, qtbot):
        ed = _make_editor(qtbot)
        ed.auto_complete_enabled = True
        ed.repeat_command_enabled = True

        ed.run_command("splineCommand")
        assert isinstance(ed.active_command, DrawSplineCommand)

        ed.provide_point(Vec2(0, 0))
        _wait_for(
            qtbot,
            lambda: isinstance(ed.active_command, DrawSplineCommand)
            and len(getattr(ed.active_command, "_points", [])) == 1,
        )
        ed.provide_point(Vec2(5, 0))
        _wait_for(
            qtbot,
            lambda: isinstance(ed.active_command, DrawSplineCommand)
            and len(getattr(ed.active_command, "_points", [])) == 2,
        )
        ed.provide_point(Vec2(10, 5))
        _wait_for(
            qtbot,
            lambda: isinstance(ed.active_command, DrawSplineCommand)
            and len(getattr(ed.active_command, "_points", [])) == 3,
        )

        assert not any(isinstance(e, SplineEntity) for e in ed.document.entities)

        ed.cancel_command()
        _wait_for(qtbot, lambda: not ed.is_running)

        splines = [e for e in ed.document.entities if isinstance(e, SplineEntity)]
        assert len(splines) == 1
        assert splines[0].points == [Vec2(0, 0), Vec2(5, 0), Vec2(10, 5)]
