"""Tests for DrawCircleCommand's live indicative-radius readout (KNOWN_BUGS #4)."""
from __future__ import annotations

import pytest

from app.commands.draw_circle import DrawCircleCommand
from app.document import DocumentStore
from app.editor.editor import Editor
from app.entities import Vec2


@pytest.fixture
def editor():
    return Editor(document=DocumentStore())


def test_live_preview_radius_tracks_cursor_distance_from_center(editor):
    cmd = DrawCircleCommand(editor)
    cmd.start()
    cmd.center = Vec2(0, 0)

    value = cmd.live_preview_value("radius", Vec2(3, 4))

    assert value == pytest.approx(5.0)


def test_live_preview_radius_is_none_before_center_is_set(editor):
    cmd = DrawCircleCommand(editor)
    cmd.start()

    assert cmd.live_preview_value("radius", Vec2(3, 4)) is None


def test_live_preview_center_defaults_to_cursor(editor):
    cmd = DrawCircleCommand(editor)
    cmd.start()

    # "center" has no override, so the base-class default (raw cursor) applies.
    assert cmd.live_preview_value("center", Vec2(1, 2)) == Vec2(1, 2)
