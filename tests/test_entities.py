"""Tests for entity protocol methods: bounding_box, hit_test, snap_candidates, etc."""
from __future__ import annotations

import math
import pytest

from app.entities.base import BBox, Vec2
from app.entities.line import LineEntity
from app.entities.circle import CircleEntity
from app.entities.arc import ArcEntity
from app.entities.rectangle import RectangleEntity
from app.entities.polyline import PolylineEntity
from app.entities.text import TextEntity
from app.entities.base import BaseEntity as _BaseEntity
from app.entities.snap_types import SnapType

from tests.conftest import ALL_SNAP_TYPES


# ===================================================================
# LineEntity
# ===================================================================

class TestLineEntity:
    # ---- bounding_box ----
    def test_bbox(self, line_h):
        bb = line_h.bounding_box()
        assert bb == BBox(0, 0, 10, 0)

    def test_bbox_diagonal(self, line_diag):
        bb = line_diag.bounding_box()
        assert bb == BBox(0, 0, 3, 4)

    # ---- hit_test ----
    def test_hit_on_line(self, line_h):
        assert line_h.hit_test(Vec2(5, 0), tolerance=0.5)

    def test_hit_near_line(self, line_h):
        assert line_h.hit_test(Vec2(5, 0.3), tolerance=0.5)

    def test_miss(self, line_h):
        assert not line_h.hit_test(Vec2(5, 5), tolerance=0.5)

    def test_hit_endpoint(self, line_h):
        assert line_h.hit_test(Vec2(0, 0), tolerance=0.1)

    # ---- snap_candidates ----
    def test_snap_endpoints(self, line_h):
        snaps = line_h.snap_candidates(ALL_SNAP_TYPES)
        endpoints = [s for s in snaps if s.snap_type == SnapType.ENDPOINT]
        assert len(endpoints) == 2
        pts = {s.point for s in endpoints}
        assert Vec2(0, 0) in pts and Vec2(10, 0) in pts

    def test_snap_midpoint(self, line_h):
        snaps = line_h.snap_candidates(ALL_SNAP_TYPES)
        mids = [s for s in snaps if s.snap_type == SnapType.MIDPOINT]
        assert len(mids) == 1
        assert mids[0].point == Vec2(5, 0)

    def test_snap_filtered(self, line_h):
        """When only ENDPOINT is enabled, no midpoint is returned."""
        snaps = line_h.snap_candidates(frozenset({SnapType.ENDPOINT}))
        assert all(s.snap_type == SnapType.ENDPOINT for s in snaps)

    # ---- nearest_snap ----
    def test_nearest_on_line(self, line_h):
        snap = line_h.nearest_snap(Vec2(5, 3))
        assert snap is not None
        assert snap.point.x == pytest.approx(5.0)
        assert snap.point.y == pytest.approx(0.0)

    def test_nearest_clamped_to_endpoint(self, line_h):
        snap = line_h.nearest_snap(Vec2(20, 0))
        assert snap is not None
        assert snap.point.x == pytest.approx(10.0)

    # ---- perp_snaps ----
    def test_perp_from_above(self, line_h):
        perps = line_h.perp_snaps(Vec2(5, 10))
        assert len(perps) == 1
        assert perps[0].point.x == pytest.approx(5.0)
        assert perps[0].point.y == pytest.approx(0.0)

    def test_perp_infinite_extension(self, line_h):
        """Perp foot outside segment range (t<0 or t>1) is still returned
        because LineEntity uses the infinite line for perp snaps."""
        perps = line_h.perp_snaps(Vec2(-5, 10))
        assert len(perps) == 1

    # ---- crosses_rect ----
    def test_crosses_rect_intersecting(self, line_h):
        assert line_h.crosses_rect(Vec2(3, -1), Vec2(7, 1))

    def test_crosses_rect_miss(self, line_h):
        assert not line_h.crosses_rect(Vec2(20, 20), Vec2(30, 30))

    # ---- serialisation round-trip ----
    def test_dict_roundtrip(self, line_h):
        d = line_h.to_dict()
        restored = LineEntity.from_dict(d)
        assert restored.p1 == line_h.p1
        assert restored.p2 == line_h.p2
        assert restored.type == "line"


# ===================================================================
# CircleEntity
# ===================================================================

class TestCircleEntity:
    def test_bbox(self, circle_origin):
        bb = circle_origin.bounding_box()
        assert bb == BBox(-1, -1, 1, 1)

    def test_hit_on_circumference(self, circle_origin):
        assert circle_origin.hit_test(Vec2(1, 0), tolerance=0.1)

    def test_hit_centre_misses(self, circle_origin):
        """Centre of the circle is NOT on the circle itself."""
        assert not circle_origin.hit_test(Vec2(0, 0), tolerance=0.1)

    def test_snap_center(self, circle_origin):
        snaps = circle_origin.snap_candidates(frozenset({SnapType.CENTER}))
        assert len(snaps) == 1
        assert snaps[0].point == Vec2(0, 0)
        assert snaps[0].snap_type == SnapType.CENTER

    def test_snap_quadrants(self, circle_origin):
        snaps = circle_origin.snap_candidates(frozenset({SnapType.QUADRANT}))
        assert len(snaps) == 4
        pts = {s.point for s in snaps}
        assert Vec2(1, 0) in pts
        assert Vec2(-1, 0) in pts
        assert Vec2(0, 1) in pts
        assert Vec2(0, -1) in pts

    def test_nearest(self, circle_origin):
        snap = circle_origin.nearest_snap(Vec2(3, 0))
        assert snap is not None
        assert snap.point.x == pytest.approx(1.0)
        assert snap.point.y == pytest.approx(0.0)

    def test_nearest_from_center(self, circle_origin):
        """Cursor exactly at center — ambiguous, returns None."""
        snap = circle_origin.nearest_snap(Vec2(0, 0))
        assert snap is None

    def test_perp(self, circle_origin):
        perps = circle_origin.perp_snaps(Vec2(5, 0))
        assert len(perps) == 1
        assert perps[0].point.x == pytest.approx(1.0)
        assert perps[0].point.y == pytest.approx(0.0)

    def test_crosses_rect(self, circle_origin):
        assert circle_origin.crosses_rect(Vec2(-0.5, -0.5), Vec2(0.5, 0.5))

    def test_crosses_rect_miss(self, circle_origin):
        assert not circle_origin.crosses_rect(Vec2(5, 5), Vec2(6, 6))

    def test_dict_roundtrip(self, circle_origin):
        d = circle_origin.to_dict()
        restored = CircleEntity.from_dict(d)
        assert restored.center == circle_origin.center
        assert restored.radius == circle_origin.radius


# ===================================================================
# RectangleEntity
# ===================================================================

class TestRectangleEntity:
    def test_bbox(self, rect_unit):
        bb = rect_unit.bounding_box()
        assert bb == BBox(1, 1, 3, 4)

    def test_hit_on_edge(self, rect_unit):
        assert rect_unit.hit_test(Vec2(1, 2.5), tolerance=0.1)

    def test_hit_inside_misses(self, rect_unit):
        """Interior of rect is not on any edge."""
        assert not rect_unit.hit_test(Vec2(2, 2.5), tolerance=0.01)

    def test_snap_corners(self, rect_unit):
        snaps = rect_unit.snap_candidates(frozenset({SnapType.ENDPOINT}))
        assert len(snaps) == 4

    def test_snap_midpoints(self, rect_unit):
        snaps = rect_unit.snap_candidates(frozenset({SnapType.MIDPOINT}))
        assert len(snaps) == 4

    def test_nearest(self, rect_unit):
        snap = rect_unit.nearest_snap(Vec2(0, 2.5))
        assert snap is not None
        # Nearest point should be on the left edge, x ≈ 1
        assert snap.point.x == pytest.approx(1.0)

    def test_perp_on_horizontal_edge(self, rect_unit):
        # From a point directly above the bottom edge
        perps = rect_unit.perp_snaps(Vec2(2, -5))
        pts_y = [p.point.y for p in perps]
        # Should have a perp foot on the bottom edge (y=1) and top edge (y=4)
        assert pytest.approx(1.0) in pts_y or pytest.approx(4.0) in pts_y

    def test_dict_roundtrip(self, rect_unit):
        d = rect_unit.to_dict()
        restored = RectangleEntity.from_dict(d)
        assert restored.p1 == rect_unit.p1
        assert restored.p2 == rect_unit.p2


# ===================================================================
# PolylineEntity
# ===================================================================

class TestPolylineEntity:
    def test_bbox_open(self, polyline_open):
        bb = polyline_open.bounding_box()
        assert bb == BBox(0, 0, 5, 5)

    def test_hit_on_segment(self, polyline_open):
        assert polyline_open.hit_test(Vec2(2.5, 0), tolerance=0.1)

    def test_hit_miss(self, polyline_open):
        assert not polyline_open.hit_test(Vec2(2.5, 2.5), tolerance=0.1)

    def test_snap_endpoints(self, polyline_open):
        snaps = polyline_open.snap_candidates(frozenset({SnapType.ENDPOINT}))
        # Open polyline endpoints: first and last vertex
        pts = {s.point for s in snaps}
        assert Vec2(0, 0) in pts
        assert Vec2(5, 5) in pts

    def test_snap_midpoints(self, polyline_open):
        snaps = polyline_open.snap_candidates(frozenset({SnapType.MIDPOINT}))
        assert len(snaps) == 2  # one per segment

    def test_closed_extra_segment(self, polyline_closed):
        segs = polyline_closed._segments()
        assert len(segs) == 3  # 3 edges for a closed triangle

    def test_nearest(self, polyline_open):
        snap = polyline_open.nearest_snap(Vec2(2.5, -1))
        assert snap is not None
        assert snap.point.y == pytest.approx(0.0)

    def test_dict_roundtrip(self, polyline_open):
        d = polyline_open.to_dict()
        restored = PolylineEntity.from_dict(d)
        assert restored.points == polyline_open.points
        assert restored.closed == polyline_open.closed

    def test_empty_polyline_bbox_is_none(self):
        p = PolylineEntity(points=[], closed=False)
        assert p.bounding_box() is None


# ===================================================================
# ArcEntity
# ===================================================================

class TestArcEntity:
    def test_bbox(self, arc_quarter):
        bb = arc_quarter.bounding_box()
        assert bb is not None
        # Conservative bbox is the full circle
        assert bb.min_x <= -5.0
        assert bb.max_x >= 5.0

    def test_hit_on_arc(self, arc_quarter):
        # Point on the arc at 45°
        pt = Vec2(5 * math.cos(math.pi / 4), 5 * math.sin(math.pi / 4))
        assert arc_quarter.hit_test(pt, tolerance=0.5)

    def test_hit_off_arc(self, arc_quarter):
        # Point at 180° — on the circle but outside arc sweep
        assert not arc_quarter.hit_test(Vec2(-5, 0), tolerance=0.3)

    def test_snap_center(self, arc_quarter):
        snaps = arc_quarter.snap_candidates(frozenset({SnapType.CENTER}))
        assert len(snaps) == 1
        assert snaps[0].point == Vec2(0, 0)

    def test_snap_endpoints(self, arc_quarter):
        snaps = arc_quarter.snap_candidates(frozenset({SnapType.ENDPOINT}))
        pts = {s.point for s in snaps}
        # Start at 0° → (5,0), end at π/2 → (0,5)
        assert any(abs(p.x - 5) < 0.01 and abs(p.y) < 0.01 for p in pts)
        assert any(abs(p.x) < 0.01 and abs(p.y - 5) < 0.01 for p in pts)

    def test_dict_roundtrip(self, arc_quarter):
        d = arc_quarter.to_dict()
        restored = ArcEntity.from_dict(d)
        assert restored.center == arc_quarter.center
        assert restored.radius == arc_quarter.radius
        assert restored.start_angle == pytest.approx(arc_quarter.start_angle)
        assert restored.end_angle == pytest.approx(arc_quarter.end_angle)


# ===================================================================
# TextEntity
# ===================================================================

class TestTextEntity:
    def test_bbox(self, text_hello):
        bb = text_hello.bounding_box()
        assert bb is not None
        # Approximate width = len("Hello") * 0.6 * height
        assert bb.min_x == pytest.approx(1.0)
        assert bb.min_y == pytest.approx(2.0)

    def test_hit_inside(self, text_hello):
        # Should hit inside the approximate text bbox
        bb = text_hello.bounding_box()
        mid = Vec2((bb.min_x + bb.max_x) / 2, (bb.min_y + bb.max_y) / 2)
        assert text_hello.hit_test(mid, tolerance=0.1)

    def test_hit_outside(self, text_hello):
        assert not text_hello.hit_test(Vec2(100, 100), tolerance=0.1)

    def test_dict_roundtrip(self, text_hello):
        d = text_hello.to_dict()
        restored = TextEntity.from_dict(d)
        assert restored.text == "Hello"
        assert restored.position == text_hello.position


# ===================================================================
# BaseEntity (default no-ops)
# ===================================================================

class TestBaseEntityDefaults:
    def test_defaults_return_none_or_empty(self):
        e = _BaseEntity()
        assert e.bounding_box() is None
        assert e.hit_test(Vec2(0, 0), 1.0) is False
        assert e.snap_candidates(frozenset()) == []
        assert e.nearest_snap(Vec2(0, 0)) is None
        assert e.perp_snaps(Vec2(0, 0)) == []
        assert e.crosses_rect(Vec2(0, 0), Vec2(1, 1)) is False
