"""Tests for Ctrl-constrained grip editing (AutoCAD-style).

When a grip is dragged with Ctrl held, the entity should preserve its
existing geometric relationship and only change the one degree of freedom
implied by the grip: a line keeps its direction and only its length
changes, an arc keeps its radius and only its angle changes.
"""
from __future__ import annotations

import math

import pytest

from app.entities import Vec2
from app.entities.arc import ArcEntity
from app.entities.line import LineEntity


def test_line_endpoint_unconstrained_moves_freely():
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    line.move_grip(1, Vec2(10, 5))
    assert line.p2 == Vec2(10, 5)


def test_line_endpoint_constrained_slides_along_existing_direction():
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    # Drag p2 off-axis while constrained: should snap back onto the
    # original p1->p2 direction (the x-axis here), changing only length.
    line.move_grip(1, Vec2(7, 3), constrain=True)
    assert line.p1 == Vec2(0, 0)
    assert line.p2.y == pytest.approx(0.0)
    assert line.p2.x == pytest.approx(7.0)


def test_line_p1_constrained_slides_along_existing_direction():
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    line.move_grip(0, Vec2(-3, 4), constrain=True)
    assert line.p2 == Vec2(10, 0)
    assert line.p1.y == pytest.approx(0.0)
    assert line.p1.x == pytest.approx(-3.0)


def test_arc_endpoint_unconstrained_changes_radius():
    arc = ArcEntity(center=Vec2(0, 0), radius=5.0, start_angle=0.0, end_angle=math.pi / 2)
    arc.move_grip(2, Vec2(0, 10))
    assert arc.radius == pytest.approx(10.0)


def test_arc_endpoint_constrained_keeps_radius_changes_angle_only():
    arc = ArcEntity(center=Vec2(0, 0), radius=5.0, start_angle=0.0, end_angle=math.pi / 2)
    arc.move_grip(2, Vec2(0, 10), constrain=True)
    assert arc.radius == pytest.approx(5.0)
    assert arc.end_angle == pytest.approx(math.pi / 2)


def test_arc_start_endpoint_constrained_keeps_radius():
    arc = ArcEntity(center=Vec2(0, 0), radius=5.0, start_angle=0.0, end_angle=math.pi / 2)
    arc.move_grip(1, Vec2(-8, 0), constrain=True)
    assert arc.radius == pytest.approx(5.0)
    assert arc.start_angle == pytest.approx(math.pi)
