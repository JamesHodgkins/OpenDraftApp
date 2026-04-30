"""Unit tests for dynamic-input vector parsing helpers."""
from __future__ import annotations

import pytest

from app.editor.dynamic_input_parser import DynamicInputParser
from app.entities import Vec2


def test_parse_vector_components_from_origin_base() -> None:
    value = DynamicInputParser.parse_vector(
        "3,-2",
        current_pos=Vec2(0, 0),
        base_point=Vec2(0, 0),
    )

    assert value == Vec2(3, -2)


def test_parse_vector_polar_magnitude_angle() -> None:
    value = DynamicInputParser.parse_vector(
        "10<30",
        current_pos=Vec2(0, 0),
        base_point=Vec2(0, 0),
    )

    assert value is not None
    assert value.x == pytest.approx(8.6602540378)
    assert value.y == pytest.approx(5.0)


def test_parse_vector_polar_supports_signed_values() -> None:
    value = DynamicInputParser.parse_vector(
        "5<-90",
        current_pos=Vec2(0, 0),
        base_point=Vec2(0, 0),
    )

    assert value is not None
    assert value.x == pytest.approx(0.0, abs=1e-9)
    assert value.y == pytest.approx(-5.0)
