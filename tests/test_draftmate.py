"""
Tests for the Draftmate engine (Object Snap Tracking + Polar Tracking).
"""
from __future__ import annotations

import math
import time

import pytest

from app.editor.draftmate import (
    AlignmentLine,
    DraftmateEngine,
    DraftmateResult,
    DraftmateSettings,
    TrackedPoint,
    _dist,
    _line_line_intersect,
    _project_onto_line,
)
from app.entities.base import Vec2
from app.entities.snap_types import SnapResult, SnapType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snap(x: float, y: float, st: SnapType = SnapType.ENDPOINT) -> SnapResult:
    return SnapResult(point=Vec2(x, y), snap_type=st, entity_id="e1")


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------


class TestDraftmateSettings:
    def test_defaults(self):
        s = DraftmateSettings()
        assert s.enabled is False
        assert s.polar_angle_deg == 45.0
        assert s.max_tracked == 6
        assert s.acquire_ms == 400
        assert SnapType.ENDPOINT in s.trackable_types
        assert SnapType.MIDPOINT in s.trackable_types
        assert SnapType.CENTER in s.trackable_types


# ---------------------------------------------------------------------------
# Engine — basic lifecycle
# ---------------------------------------------------------------------------

class TestDraftmateEngine:
    def test_disabled_returns_none(self):
        eng = DraftmateEngine()
        assert eng.settings.enabled is False
        result = eng.update(Vec2(0, 0), None, None, scale=1.0)
        assert result is None

    def test_enabled_returns_result(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True))
        result = eng.update(Vec2(5, 5), None, None, scale=1.0)
        assert isinstance(result, DraftmateResult)
        assert result.tracked_points == []
        assert result.alignment_lines == []
        assert result.snapped_point is None

    def test_clear_resets_state(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True, acquire_ms=0))
        # Acquire a point (0 ms dwell) — two frames needed.
        snap = _make_snap(10, 20)
        eng.update(Vec2(10, 20), snap, None, scale=1.0)
        eng.update(Vec2(10, 20), snap, None, scale=1.0)
        assert len(eng.tracked_points) == 1

        eng.clear()
        assert eng.tracked_points == []


# ---------------------------------------------------------------------------
# Point acquisition
# ---------------------------------------------------------------------------

class TestAcquisition:
    def test_acquire_after_dwell(self):
        """Point is tracked only after the dwell time elapses."""
        eng = DraftmateEngine(DraftmateSettings(enabled=True, acquire_ms=50))
        snap = _make_snap(1, 2)

        # First frame — starts the timer.
        r1 = eng.update(Vec2(1, 2), snap, None, scale=1.0)
        assert r1.tracked_points == []

        # Wait for dwell.
        time.sleep(0.06)
        r2 = eng.update(Vec2(1, 2), snap, None, scale=1.0)
        assert len(r2.tracked_points) == 1
        assert r2.tracked_points[0].point == Vec2(1, 2)

    def test_no_acquire_on_non_trackable_type(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True, acquire_ms=0))
        snap = SnapResult(Vec2(5, 5), SnapType.NEAREST, "e1")
        eng.update(Vec2(5, 5), snap, None, scale=1.0)
        eng.update(Vec2(5, 5), snap, None, scale=1.0)
        assert eng.tracked_points == []

    def test_max_tracked_evicts_oldest(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True, acquire_ms=0, max_tracked=2))
        for i in range(4):
            snap = _make_snap(float(i), 0)
            # Two frames each to fully acquire.
            eng.update(Vec2(float(i), 0), snap, None, scale=1.0)
            eng.update(Vec2(float(i), 0), snap, None, scale=1.0)

        pts = eng.tracked_points
        assert len(pts) == 2
        # Oldest (0,0) and (1,0) are evicted; newest two remain.
        assert pts[0].point == Vec2(2.0, 0.0)
        assert pts[1].point == Vec2(3.0, 0.0)

    def test_duplicate_not_re_acquired(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True, acquire_ms=0))
        snap = _make_snap(1, 2)
        for _ in range(6):
            eng.update(Vec2(1, 2), snap, None, scale=1.0)
        assert len(eng.tracked_points) == 1


# ---------------------------------------------------------------------------
# Alignment lines
# ---------------------------------------------------------------------------

class TestAlignmentLines:
    def test_ortho_lines_for_tracked_points(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True, acquire_ms=0))
        snap = _make_snap(10, 20)
        eng.update(Vec2(10, 20), snap, None, scale=1.0)
        result = eng.update(Vec2(10, 20), snap, None, scale=1.0)

        # Should have at least 2 ortho lines (H + V) from the tracked point.
        ortho = [ln for ln in result.alignment_lines if ln.kind == "ortho"]
        assert len(ortho) == 2

    def test_polar_lines_from_base_point(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True, polar_angle_deg=90.0))
        # Cursor at (5, 0) sits right on the 0° polar line from the origin.
        result = eng.update(Vec2(5, 0), None, from_point=Vec2(0, 0), scale=1.0)

        polar = [ln for ln in result.alignment_lines if ln.kind == "polar"]
        # Only the nearest polar line is returned (at most 1).
        assert len(polar) == 1
        # It should be the 0° (or 180°) horizontal line.
        assert abs(polar[0].direction.y) < 1e-6

    def test_polar_45_default(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True))
        # Cursor at (5, 5) is exactly on the 45° polar line.
        result = eng.update(Vec2(5, 5), None, from_point=Vec2(0, 0), scale=1.0)

        polar = [ln for ln in result.alignment_lines if ln.kind == "polar"]
        # At most 1 polar line (the nearest) is returned.
        assert len(polar) == 1
        # Direction should lie on the 45° axis (may be 45° or 225°).
        import math
        assert abs(abs(polar[0].direction.x) - math.cos(math.radians(45))) < 1e-6
        assert abs(abs(polar[0].direction.y) - math.sin(math.radians(45))) < 1e-6


# ---------------------------------------------------------------------------
# Alignment snapping
# ---------------------------------------------------------------------------

class TestAlignmentSnapping:
    def test_snap_to_single_line(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True, acquire_ms=0, snap_tolerance_px=20.0))
        snap = _make_snap(10, 0)
        eng.update(Vec2(10, 0), snap, None, scale=1.0)
        eng.update(Vec2(10, 0), snap, None, scale=1.0)

        # Move cursor near the horizontal extension line (y≈0) but at x=50.
        result = eng.update(Vec2(50, 2), None, None, scale=1.0)
        assert result.snapped_point is not None
        # Should snap to (50, 0) — projection onto horizontal guide from (10,0).
        assert abs(result.snapped_point.y - 0.0) < 1e-6
        assert abs(result.snapped_point.x - 50.0) < 1e-6

    def test_snap_to_intersection(self):
        eng = DraftmateEngine(DraftmateSettings(enabled=True, acquire_ms=0, snap_tolerance_px=20.0))
        # Track two points: (10, 0) and (0, 20).
        s1 = _make_snap(10, 0)
        eng.update(Vec2(10, 0), s1, None, scale=1.0)
        eng.update(Vec2(10, 0), s1, None, scale=1.0)

        s2 = SnapResult(Vec2(0, 20), SnapType.MIDPOINT, "e2")
        eng.update(Vec2(0, 20), s2, None, scale=1.0)
        eng.update(Vec2(0, 20), s2, None, scale=1.0)

        # Cursor near (10, 20) should snap to intersection of the vertical
        # line from (10,0) and horizontal line from (0,20).
        result = eng.update(Vec2(11, 19), None, None, scale=1.0)
        assert result.snapped_point is not None
        assert abs(result.snapped_point.x - 10.0) < 1e-6
        assert abs(result.snapped_point.y - 20.0) < 1e-6


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

class TestGeometryHelpers:
    def test_project_onto_horizontal(self):
        ln = AlignmentLine(origin=Vec2(0, 5), direction=Vec2(1, 0))
        p = _project_onto_line(Vec2(10, 8), ln)
        assert abs(p.x - 10.0) < 1e-9
        assert abs(p.y - 5.0) < 1e-9

    def test_project_onto_vertical(self):
        ln = AlignmentLine(origin=Vec2(3, 0), direction=Vec2(0, 1))
        p = _project_onto_line(Vec2(7, 15), ln)
        assert abs(p.x - 3.0) < 1e-9
        assert abs(p.y - 15.0) < 1e-9

    def test_line_line_intersect_ortho(self):
        h = AlignmentLine(origin=Vec2(0, 5), direction=Vec2(1, 0))
        v = AlignmentLine(origin=Vec2(3, 0), direction=Vec2(0, 1))
        pt = _line_line_intersect(h, v)
        assert pt is not None
        assert abs(pt.x - 3.0) < 1e-9
        assert abs(pt.y - 5.0) < 1e-9

    def test_line_line_parallel_returns_none(self):
        a = AlignmentLine(origin=Vec2(0, 0), direction=Vec2(1, 0))
        b = AlignmentLine(origin=Vec2(0, 5), direction=Vec2(1, 0))
        assert _line_line_intersect(a, b) is None

    def test_dist(self):
        assert abs(_dist(Vec2(0, 0), Vec2(3, 4)) - 5.0) < 1e-9
