"""Tests for the hit_testing shim module."""
from __future__ import annotations

import pytest

from app.entities.base import BBox, Vec2
from app.entities.line import LineEntity
from app.entities.circle import CircleEntity
from app.entities.rectangle import RectangleEntity
from app.editor.hit_testing import (
    entity_bbox,
    entity_bounding_box,
    bbox_intersects_viewport,
    hit_test_point,
    entity_inside_rect,
    entity_crosses_rect,
)


class TestEntityBbox:
    def test_returns_bbox(self, line_h):
        bb = entity_bbox(line_h)
        assert isinstance(bb, BBox)
        assert bb.min_x == 0 and bb.max_x == 10

    def test_legacy_tuple(self, line_h):
        t = entity_bounding_box(line_h)
        assert isinstance(t, tuple) and len(t) == 4

    def test_none_for_base(self):
        from app.entities.base import BaseEntity
        assert entity_bbox(BaseEntity()) is None


class TestBboxIntersectsViewport:
    def test_overlapping(self):
        assert bbox_intersects_viewport((0, 0, 10, 10), 5, 5, 15, 15)

    def test_disjoint(self):
        assert not bbox_intersects_viewport((0, 0, 1, 1), 5, 5, 10, 10)


class TestHitTestPoint:
    def test_hit(self, line_h):
        assert hit_test_point(line_h, Vec2(5, 0), 0.5)

    def test_miss(self, line_h):
        assert not hit_test_point(line_h, Vec2(5, 10), 0.5)


class TestEntityInsideRect:
    def test_fully_inside(self, line_h):
        assert entity_inside_rect(line_h, Vec2(-1, -1), Vec2(11, 1))

    def test_partially_outside(self, line_h):
        assert not entity_inside_rect(line_h, Vec2(2, -1), Vec2(8, 1))


class TestEntityCrossesRect:
    def test_intersecting(self, line_h):
        assert entity_crosses_rect(line_h, Vec2(3, -1), Vec2(7, 1))

    def test_disjoint(self, line_h):
        assert not entity_crosses_rect(line_h, Vec2(20, 20), Vec2(30, 30))
