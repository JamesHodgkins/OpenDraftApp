"""Tests extending KNOWN_BUGS #4's indicative-value readout beyond Circle.

Each command below overrides ``live_preview_value`` for an export that has
no committed value yet, so the controller panel can show what it *would*
become right now (dim placeholder text) instead of sitting blank.
"""
from __future__ import annotations

import math

import pytest

from app.commands.draw_arc import DrawArcStartEndRadiusCommand
from app.commands.draw_line import DrawLineCommand
from app.commands.modify_chamfer import ChamferCommand
from app.commands.modify_copy import CopyCommand
from app.commands.modify_move import MoveCommand
from app.commands.modify_rotate import RotateCommand
from app.commands.modify_scale import ScaleCommand
from app.document import DocumentStore
from app.editor.editor import Editor
from app.entities import LineEntity, Vec2


@pytest.fixture
def editor():
    return Editor(document=DocumentStore())


def _select(editor, *entities):
    doc = editor.document
    for ent in entities:
        doc.add_entity(ent)
        editor.selection.add(ent.id)


# ---- Arc (start/end/radius) ------------------------------------------------

def test_arc_radius_preview_uses_chord_half_as_floor(editor):
    cmd = DrawArcStartEndRadiusCommand(editor)
    cmd.start()
    cmd.start_point = Vec2(0, 0)
    cmd.end_point = Vec2(10, 0)

    # Cursor at the chord midpoint (distance from start == chord/2): stays at the floor.
    assert cmd.live_preview_value("radius", Vec2(5, 0)) == pytest.approx(5.0)


def test_arc_radius_preview_tracks_far_cursor(editor):
    cmd = DrawArcStartEndRadiusCommand(editor)
    cmd.start()
    cmd.start_point = Vec2(0, 0)
    cmd.end_point = Vec2(10, 0)

    assert cmd.live_preview_value("radius", Vec2(0, 20)) == pytest.approx(20.0)


def test_arc_radius_preview_none_before_both_points_set(editor):
    cmd = DrawArcStartEndRadiusCommand(editor)
    cmd.start()
    cmd.start_point = Vec2(0, 0)

    assert cmd.live_preview_value("radius", Vec2(5, 5)) is None


# ---- Line end vector preview ------------------------------------------------
# The command returns the raw displacement Vec2; the panel formats it per the
# user's cycled vector-input style (relative/absolute/polar) — see
# test_stateful_command_prompts.py for the style-aware formatting tests.

def test_line_end_vector_preview_is_cursor_minus_start(editor):
    cmd = DrawLineCommand(editor)
    cmd.start()
    cmd.start_point = Vec2(0, 0)

    value = cmd.live_preview_value("end_point", Vec2(3, 4))

    assert value == Vec2(3, 4)


def test_line_end_vector_preview_none_before_start_point(editor):
    cmd = DrawLineCommand(editor)
    cmd.start()

    assert cmd.live_preview_value("end_point", Vec2(3, 4)) is None


# ---- Move / Copy displacement ----------------------------------------------

def test_move_displacement_preview_is_cursor_minus_base(editor):
    _select(editor, LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    cmd = MoveCommand(editor)
    cmd.start()
    cmd.base_point = Vec2(1, 1)

    assert cmd.live_preview_value("displacement", Vec2(4, 5)) == Vec2(3, 4)


def test_copy_displacement_preview_is_cursor_minus_base(editor):
    _select(editor, LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    cmd = CopyCommand(editor)
    cmd.start()
    cmd.base_point = Vec2(2, 2)

    assert cmd.live_preview_value("displacement", Vec2(5, 2)) == Vec2(3, 0)


def test_move_displacement_preview_none_before_base_point(editor):
    _select(editor, LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    cmd = MoveCommand(editor)
    cmd.start()

    assert cmd.live_preview_value("displacement", Vec2(4, 5)) is None


# ---- Rotate angle -----------------------------------------------------------

def test_rotate_angle_preview_tracks_cursor_around_center(editor):
    _select(editor, LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    cmd = RotateCommand(editor)
    cmd.start()
    cmd.center = Vec2(0, 0)

    value = cmd.live_preview_value("rotation_vector", Vec2(0, 1))

    assert value == pytest.approx(90.0)


def test_rotate_angle_preview_none_before_center(editor):
    _select(editor, LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    cmd = RotateCommand(editor)
    cmd.start()

    assert cmd.live_preview_value("rotation_vector", Vec2(0, 1)) is None


# ---- Scale reference_vector / factor ----------------------------------------

def test_scale_reference_vector_preview_is_cursor_minus_base(editor):
    _select(editor, LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    cmd = ScaleCommand(editor)
    cmd.start()
    cmd.base_point = Vec2(1, 1)

    assert cmd.live_preview_value("reference_vector", Vec2(4, 5)) == Vec2(3, 4)


def test_scale_factor_preview_scales_distance_by_100(editor):
    _select(editor, LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    cmd = ScaleCommand(editor)
    cmd.start()
    cmd.base_point = Vec2(0, 0)

    assert cmd.live_preview_value("factor", Vec2(200, 0)) == pytest.approx(2.0)


def test_scale_factor_preview_none_before_base_point(editor):
    _select(editor, LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    cmd = ScaleCommand(editor)
    cmd.start()

    assert cmd.live_preview_value("factor", Vec2(200, 0)) is None


# ---- Chamfer distance_2 falls back to distance_1 ----------------------------

def test_chamfer_distance_2_preview_mirrors_distance_1(editor):
    cmd = ChamferCommand(editor)
    cmd.start()
    cmd.distance_1 = 2.5

    assert cmd.live_preview_value("distance_2", Vec2(0, 0)) == pytest.approx(2.5)


def test_chamfer_distance_2_preview_none_before_distance_1(editor):
    cmd = ChamferCommand(editor)
    cmd.start()

    assert cmd.live_preview_value("distance_2", Vec2(0, 0)) is None
