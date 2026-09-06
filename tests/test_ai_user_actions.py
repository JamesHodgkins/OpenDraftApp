"""Unit tests for ai_user.actions — the action vocabulary."""
from __future__ import annotations

import pytest

from ai_user.actions import Action, KEYBOARD_AREA_TOKENS


def test_valid_action_names_construct() -> None:
    for name in ("screenshot", "left_click", "double_click", "type", "key", "scroll", "wait", "done"):
        Action(name=name)


def test_unsupported_action_name_raises() -> None:
    with pytest.raises(ValueError):
        Action(name="zoom")


def test_keyboard_area_tokens_cover_letters_digits_and_named_modifiers() -> None:
    assert "a" in KEYBOARD_AREA_TOKENS
    assert "z" in KEYBOARD_AREA_TOKENS
    assert "0" in KEYBOARD_AREA_TOKENS
    assert "9" in KEYBOARD_AREA_TOKENS
    assert "ctrl" in KEYBOARD_AREA_TOKENS
    assert "shift" in KEYBOARD_AREA_TOKENS
    assert "space" in KEYBOARD_AREA_TOKENS
    assert "f1" not in KEYBOARD_AREA_TOKENS


def test_action_is_frozen_and_comparable() -> None:
    a = Action(name="left_click", coordinate=(1, 2))
    b = Action(name="left_click", coordinate=(1, 2))
    c = Action(name="left_click", coordinate=(1, 3))
    assert a == b
    assert a != c


def test_reasoning_defaults_to_none() -> None:
    assert Action(name="screenshot").reasoning is None


def test_reasoning_can_be_set() -> None:
    action = Action(name="key", text="ctrl+s", reasoning="Saving my progress.")
    assert action.reasoning == "Saving my progress."
