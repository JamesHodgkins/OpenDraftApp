"""Tests for base.py geometry helpers and the BBox dataclass."""
from __future__ import annotations

import math
import pytest

from app.entities.base import (
    BBox, Vec2,
    _geo_dist, _geo_pt_seg_dist,
    _geo_angle_on_arc,
    _geo_point_in_rect, _geo_seg_intersects_rect,
)


# ===================================================================
# Vec2
# ===================================================================

class TestVec2:
    def test_defaults(self):
        v = Vec2()
        assert v.x == 0.0 and v.y == 0.0

    def test_immutable(self):
        v = Vec2(1, 2)
        with pytest.raises(AttributeError):
            v.x = 5  # type: ignore[misc]

    def test_roundtrip_dict(self):
        v = Vec2(3.5, -7.1)
        assert Vec2.from_dict(v.to_dict()) == v

    def test_iter(self):
        x, y = Vec2(1, 2)
        assert (x, y) == (1, 2)

    def test_hash_and_equality(self):
        a = Vec2(1, 2)
        b = Vec2(1, 2)
        assert a == b
        assert hash(a) == hash(b)
        assert a is not b


# ===================================================================
# BBox
# ===================================================================

class TestBBox:
    def test_contains_true(self):
        outer = BBox(0, 0, 10, 10)
        inner = BBox(2, 2, 8, 8)
        assert outer.contains(inner)

    def test_contains_false_partial(self):
        outer = BBox(0, 0, 10, 10)
        partial = BBox(5, 5, 15, 15)
        assert not outer.contains(partial)

    def test_intersects_overlap(self):
        a = BBox(0, 0, 5, 5)
        b = BBox(3, 3, 8, 8)
        assert a.intersects(b)
        assert b.intersects(a)

    def test_intersects_disjoint(self):
        a = BBox(0, 0, 1, 1)
        b = BBox(5, 5, 6, 6)
        assert not a.intersects(b)

    def test_intersects_touching_edge(self):
        a = BBox(0, 0, 5, 5)
        b = BBox(5, 0, 10, 5)
        assert a.intersects(b)

    def test_intersects_viewport_inside(self):
        bb = BBox(2, 2, 4, 4)
        assert bb.intersects_viewport(0, 0, 10, 10)

    def test_intersects_viewport_outside(self):
        bb = BBox(20, 20, 30, 30)
        assert not bb.intersects_viewport(0, 0, 10, 10)


# ===================================================================
# _geo_dist
# ===================================================================

class TestGeoDist:
    def test_same_point(self):
        assert _geo_dist(Vec2(0, 0), Vec2(0, 0)) == 0.0

    def test_3_4_5(self):
        assert _geo_dist(Vec2(0, 0), Vec2(3, 4)) == pytest.approx(5.0)

    def test_negative_coords(self):
        d = _geo_dist(Vec2(-1, -1), Vec2(2, 3))
        assert d == pytest.approx(5.0)


# ===================================================================
# _geo_pt_seg_dist
# ===================================================================

class TestGeoPtSegDist:
    def test_perpendicular_foot(self):
        """Point directly above the midpoint of a horizontal segment."""
        d = _geo_pt_seg_dist(Vec2(5, 3), Vec2(0, 0), Vec2(10, 0))
        assert d == pytest.approx(3.0)

    def test_foot_beyond_endpoint(self):
        """Closest point is the endpoint when foot falls outside."""
        d = _geo_pt_seg_dist(Vec2(15, 0), Vec2(0, 0), Vec2(10, 0))
        assert d == pytest.approx(5.0)

    def test_zero_length_seg(self):
        d = _geo_pt_seg_dist(Vec2(3, 4), Vec2(0, 0), Vec2(0, 0))
        assert d == pytest.approx(5.0)

    def test_on_segment(self):
        d = _geo_pt_seg_dist(Vec2(5, 0), Vec2(0, 0), Vec2(10, 0))
        assert d == pytest.approx(0.0)


# ===================================================================
# _geo_angle_on_arc
# ===================================================================

class TestGeoAngleOnArc:
    """Angles in radians, CCW=counter-clockwise."""

    def test_ccw_simple(self):
        # Arc from 0 to π/2 CCW: π/4 is inside
        assert _geo_angle_on_arc(math.pi / 4, 0, math.pi / 2, ccw=True)

    def test_ccw_outside(self):
        assert not _geo_angle_on_arc(math.pi, 0, math.pi / 2, ccw=True)

    def test_ccw_wrapping(self):
        # Arc from 3π/2 to π/2 wrapping through 0
        assert _geo_angle_on_arc(0.0, 3 * math.pi / 2, math.pi / 2, ccw=True)

    def test_cw_simple(self):
        # CW from π/2 to 0: π/4 is inside
        assert _geo_angle_on_arc(math.pi / 4, math.pi / 2, 0.0, ccw=False)

    def test_cw_outside(self):
        assert not _geo_angle_on_arc(math.pi, math.pi / 2, 0, ccw=False)


# ===================================================================
# _geo_point_in_rect
# ===================================================================

class TestGeoPointInRect:
    def test_inside(self):
        assert _geo_point_in_rect(Vec2(5, 5), Vec2(0, 0), Vec2(10, 10))

    def test_on_edge(self):
        assert _geo_point_in_rect(Vec2(0, 5), Vec2(0, 0), Vec2(10, 10))

    def test_outside(self):
        assert not _geo_point_in_rect(Vec2(11, 5), Vec2(0, 0), Vec2(10, 10))


# ===================================================================
# _geo_seg_intersects_rect
# ===================================================================

class TestGeoSegIntersectsRect:
    def test_segment_inside(self):
        assert _geo_seg_intersects_rect(
            Vec2(2, 2), Vec2(8, 8), Vec2(0, 0), Vec2(10, 10))

    def test_segment_crossing(self):
        assert _geo_seg_intersects_rect(
            Vec2(-5, 5), Vec2(15, 5), Vec2(0, 0), Vec2(10, 10))

    def test_segment_outside(self):
        assert not _geo_seg_intersects_rect(
            Vec2(20, 20), Vec2(30, 30), Vec2(0, 0), Vec2(10, 10))

    def test_segment_tangent_to_corner(self):
        """Segment passing exactly through a corner."""
        assert _geo_seg_intersects_rect(
            Vec2(-1, -1), Vec2(1, 1), Vec2(0, 0), Vec2(10, 10))
