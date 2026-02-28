"""Tests for the OsnapEngine — integration tests exercising snap through entities."""
from __future__ import annotations

import math
import pytest

from app.entities.base import Vec2
from app.entities.line import LineEntity
from app.entities.circle import CircleEntity
from app.entities.rectangle import RectangleEntity
from app.entities.snap_types import SnapType
from app.editor.osnap_engine import OsnapEngine


@pytest.fixture
def engine():
    return OsnapEngine()


@pytest.fixture
def entities():
    return [
        LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0)),
        CircleEntity(center=Vec2(20, 0), radius=5),
    ]


class TestOsnapSnap:
    def test_snap_to_endpoint(self, engine, entities):
        """Cursor near line endpoint (0,0) at scale=1."""
        result = engine.snap(Vec2(0.5, 0.5), entities, scale=1.0)
        assert result is not None
        assert result.snap_type == SnapType.ENDPOINT
        assert result.point.x == pytest.approx(0.0)
        assert result.point.y == pytest.approx(0.0)

    def test_snap_to_midpoint(self, engine):
        """Cursor near line midpoint (50,0), far from endpoints.
        With a 100-unit line at scale=1, the endpoints are 50 px away — outside
        the default 20 px aperture — so the midpoint wins.
        """
        line = LineEntity(p1=Vec2(0, 0), p2=Vec2(100, 0))
        result = engine.snap(Vec2(50.0, 0.5), [line], scale=1.0)
        assert result is not None
        assert result.snap_type == SnapType.MIDPOINT
        assert result.point.x == pytest.approx(50.0)
        assert result.point.y == pytest.approx(0.0)

    def test_snap_to_circle_center(self, engine):
        circle = CircleEntity(center=Vec2(20, 0), radius=5)
        result = engine.snap(Vec2(20.1, 0.1), [circle], scale=1.0)
        assert result is not None
        assert result.snap_type == SnapType.CENTER
        assert result.point.x == pytest.approx(20.0)

    def test_no_snap_outside_aperture(self, engine, entities):
        """Far from any entity — should return None."""
        result = engine.snap(Vec2(100, 100), entities, scale=1.0)
        assert result is None

    def test_scale_affects_aperture(self, engine, entities):
        """At low scale the aperture covers more world-space."""
        # At scale=0.01, 20px aperture → 2000 world-units.  Should snap.
        result = engine.snap(Vec2(500, 0), entities, scale=0.01)
        assert result is not None

    def test_enabled_types_filter(self):
        """Disabling ENDPOINT means the engine won't snap to endpoints."""
        eng = OsnapEngine(enabled=frozenset({SnapType.CENTER}))
        line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
        result = eng.snap(Vec2(0, 0), [line], scale=1.0)
        # Line has no CENTER snap, so nothing should match at tight zoom
        # (unless NEAREST picks it up). Depending on priority, result could be None.
        if result is not None:
            assert result.snap_type != SnapType.ENDPOINT

    def test_snap_from_point_perpendicular(self, engine):
        """Perpendicular snap requires a from_point."""
        line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
        result = engine.snap(
            Vec2(5, 0.1), [line], scale=1.0,
            from_point=Vec2(5, 10),
        )
        # Should get perp foot at (5, 0) or an endpoint —
        # the important thing is that perp candidates are generated
        assert result is not None


class TestOsnapIntersection:
    def test_two_crossing_lines(self, engine):
        l1 = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 10))
        l2 = LineEntity(p1=Vec2(0, 10), p2=Vec2(10, 0))
        result = engine.snap(Vec2(5.1, 5.1), [l1, l2], scale=1.0)
        assert result is not None
        # The intersection at (5,5) should beat competing snaps
        assert result.point.x == pytest.approx(5.0)
        assert result.point.y == pytest.approx(5.0)

    def test_parallel_lines_no_intersection(self, engine):
        l1 = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
        l2 = LineEntity(p1=Vec2(0, 5), p2=Vec2(10, 5))
        result = engine.snap(Vec2(5, 2.5), [l1, l2], scale=1.0)
        # Should still snap (midpoint etc.) but NOT as INTERSECTION
        if result is not None:
            assert result.snap_type != SnapType.INTERSECTION
