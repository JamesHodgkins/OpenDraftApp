"""
Shared test fixtures for the OpenDraft test suite.

Provides pre-built entity instances, a populated DocumentStore, and a
helper that exposes all SnapTypes as a frozenset for protocol tests.
"""
from __future__ import annotations

import math
import pytest

from app.entities.base import BaseEntity, BBox, Vec2
from app.entities.line import LineEntity
from app.entities.circle import CircleEntity
from app.entities.arc import ArcEntity
from app.entities.rectangle import RectangleEntity
from app.entities.polyline import PolylineEntity
from app.entities.text import TextEntity
from app.entities.snap_types import SnapType, SnapResult
from app.document import DocumentStore, Layer


# ---------------------------------------------------------------------------
# Snap helpers
# ---------------------------------------------------------------------------

ALL_SNAP_TYPES: frozenset = frozenset(SnapType)


# ---------------------------------------------------------------------------
# Entity fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def line_h():
    """Horizontal line from (0,0) to (10,0)."""
    return LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))


@pytest.fixture
def line_diag():
    """Diagonal line from (0,0) to (3,4)."""
    return LineEntity(p1=Vec2(0, 0), p2=Vec2(3, 4))


@pytest.fixture
def circle_origin():
    """Unit circle centred at the origin."""
    return CircleEntity(center=Vec2(0, 0), radius=1.0)


@pytest.fixture
def circle_offset():
    """Circle of radius 5 centred at (10,10)."""
    return CircleEntity(center=Vec2(10, 10), radius=5.0)


@pytest.fixture
def rect_unit():
    """2×3 rectangle, p1=(1,1) p2=(3,4)."""
    return RectangleEntity(p1=Vec2(1, 1), p2=Vec2(3, 4))


@pytest.fixture
def arc_quarter():
    """Quarter-circle arc: centre (0,0), r=5, 0→π/2, CCW."""
    return ArcEntity(
        center=Vec2(0, 0),
        radius=5.0,
        start_angle=0.0,
        end_angle=math.pi / 2,
        ccw=True,
    )


@pytest.fixture
def polyline_open():
    """Open polyline: (0,0)→(5,0)→(5,5)."""
    return PolylineEntity(points=[Vec2(0, 0), Vec2(5, 0), Vec2(5, 5)], closed=False)


@pytest.fixture
def polyline_closed():
    """Closed triangle: (0,0)→(4,0)→(2,3)."""
    return PolylineEntity(
        points=[Vec2(0, 0), Vec2(4, 0), Vec2(2, 3)],
        closed=True,
    )


@pytest.fixture
def text_hello():
    """Text entity at (1,2) with content 'Hello'."""
    return TextEntity(position=Vec2(1, 2), text="Hello", height=10.0)


# ---------------------------------------------------------------------------
# Document fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def doc_with_entities(line_h, circle_origin, rect_unit):
    """A DocumentStore pre-loaded with a line, circle and rectangle."""
    doc = DocumentStore()
    doc.add_entity(line_h)
    doc.add_entity(circle_origin)
    doc.add_entity(rect_unit)
    return doc
