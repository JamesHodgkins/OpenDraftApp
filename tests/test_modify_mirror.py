"""Regression tests for the Mirror command (KNOWN_BUGS #6)."""
from __future__ import annotations

import math

import pytest

from app.commands.modify_mirror import MirrorCommand, _mirror_entity
from app.document import DocumentStore
from app.editor.editor import Editor
from app.entities import ArcEntity, LineEntity, Vec2


@pytest.fixture
def editor():
    return Editor(document=DocumentStore())


def _arc_span_deg(ent: ArcEntity) -> float:
    from app.entities.arc import _arc_span
    return math.degrees(_arc_span(ent.start_angle, ent.end_angle, ent.ccw))


def test_mirroring_arc_preserves_span_magnitude():
    """A 90° arc mirrored across an axis must stay a 90° arc, not 270°."""
    arc = ArcEntity(
        center=Vec2(2, 0), radius=1.0,
        start_angle=0.0, end_angle=math.pi / 2, ccw=True,
    )
    mirrored = _mirror_entity(arc, 0.0, 0.0, 1.0, 0.0)  # mirror across the x-axis

    assert isinstance(mirrored, ArcEntity)
    assert abs(_arc_span_deg(mirrored)) == pytest.approx(90.0)


def test_mirrored_arc_endpoints_match_reflected_points():
    """The reflected arc's endpoints must be the true mirror images of the originals."""
    arc = ArcEntity(
        center=Vec2(2, 0), radius=1.0,
        start_angle=math.radians(30), end_angle=math.radians(120), ccw=True,
    )
    mirrored = _mirror_entity(arc, 0.0, 0.0, 1.0, 0.0)

    def point_at(a: ArcEntity, angle: float) -> Vec2:
        return Vec2(a.center.x + a.radius * math.cos(angle), a.center.y + a.radius * math.sin(angle))

    orig_start = point_at(arc, arc.start_angle)
    orig_end = point_at(arc, arc.end_angle)
    new_start = point_at(mirrored, mirrored.start_angle)
    new_end = point_at(mirrored, mirrored.end_angle)

    # Mirroring across the x-axis negates y.
    assert new_start.x == pytest.approx(orig_start.x)
    assert new_start.y == pytest.approx(-orig_start.y)
    assert new_end.x == pytest.approx(orig_end.x)
    assert new_end.y == pytest.approx(-orig_end.y)


def test_mirror_command_completes_after_typed_keep_originals_choice(editor):
    """Full flow: pick axis, then set keep_originals via set_stateful_property
    (as the row's Enter/Space commit path does) — command must reach a
    committable state and commit() must actually run."""
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = MirrorCommand(editor)
    editor._active_command = cmd
    cmd.start()

    editor.set_stateful_property("axis_start", Vec2(0, 0))
    editor.set_stateful_property("axis_end", Vec2(0, 10))
    editor.set_stateful_property("keep_originals", "Y")

    assert cmd.all_exports_set()
    cmd.commit()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 2  # original kept + mirrored copy


def test_mirror_command_enter_defaults_to_keep_originals(editor):
    """Pressing Enter at the keep-originals prompt defaults to yes."""
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = MirrorCommand(editor)
    editor._active_command = cmd
    cmd.start()

    editor.set_stateful_property("axis_start", Vec2(0, 0))
    editor.set_stateful_property("axis_end", Vec2(0, 10))

    assert cmd.active_export == "keep_originals"
    assert cmd.keep_originals is None

    editor.commit_command()

    lines = [e for e in editor.document.entities if isinstance(e, LineEntity)]
    assert len(lines) == 2
    assert editor.active_command is None


def test_canvas_click_during_choice_prompt_gives_status_hint(editor):
    """A canvas click can't answer Y/N — it must not be silently swallowed."""
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    cmd = MirrorCommand(editor)
    editor._active_command = cmd
    cmd.start()
    editor.set_stateful_property("axis_start", Vec2(0, 0))
    editor.set_stateful_property("axis_end", Vec2(0, 10))
    assert cmd.active_export == "keep_originals"

    messages = []
    editor.status_message.connect(messages.append)
    editor.provide_point(Vec2(5, 5))

    assert messages  # user got told what to do instead of nothing happening
    assert cmd.keep_originals is None  # the click did not (mis)set anything
