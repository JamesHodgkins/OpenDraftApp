"""Tests for the entity auto-registry and entity_from_dict deserialisation."""
from __future__ import annotations

import pytest

from app.entities.base import _ENTITY_REGISTRY, Vec2
from app.entities import entity_from_dict
from app.entities.line import LineEntity
from app.entities.circle import CircleEntity
from app.entities.arc import ArcEntity
from app.entities.rectangle import RectangleEntity
from app.entities.polyline import PolylineEntity
from app.entities.text import TextEntity
from app.entities.dimension import DimensionEntity
from app.entities.hatch import HatchEntity


class TestRegistry:
    """Ensure all entity types are registered via __init_subclass__."""

    @pytest.mark.parametrize("kind,cls", [
        ("line", LineEntity),
        ("circle", CircleEntity),
        ("arc", ArcEntity),
        ("rect", RectangleEntity),
        ("polyline", PolylineEntity),
        ("text", TextEntity),
        ("dimension", DimensionEntity),
        ("hatch", HatchEntity),
    ])
    def test_registered(self, kind, cls):
        assert kind in _ENTITY_REGISTRY
        assert _ENTITY_REGISTRY[kind] is cls


class TestEntityFromDict:
    def test_line(self):
        d = {"type": "line", "id": "abc", "p1": {"x": 0, "y": 0}, "p2": {"x": 1, "y": 1}}
        e = entity_from_dict(d)
        assert isinstance(e, LineEntity)
        assert e.id == "abc"

    def test_circle(self):
        d = {"type": "circle", "id": "c1", "center": {"x": 5, "y": 5}, "radius": 3}
        e = entity_from_dict(d)
        assert isinstance(e, CircleEntity)
        assert e.radius == 3.0

    def test_unknown_type_fallback(self):
        d = {"type": "wormhole", "id": "z"}
        e = entity_from_dict(d)
        assert type(e).__name__ == "BaseEntity"
