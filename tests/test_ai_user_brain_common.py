"""Unit tests for ai_user.brain_common — the shared tool-call -> Action
translation used by both vendor Brain implementations."""
from __future__ import annotations

from ai_user.actions import Action
from ai_user.brain_common import action_from_tool_input


def test_left_click_with_coordinate() -> None:
    action = action_from_tool_input("left_click", {"coordinate": [12, 34]})

    assert action == Action(name="left_click", coordinate=(12, 34))


def test_left_click_with_modifier_text() -> None:
    action = action_from_tool_input("left_click", {"coordinate": [1, 2], "text": "shift"})

    assert action.modifiers == ("shift",)


def test_type_carries_text() -> None:
    action = action_from_tool_input("type", {"text": "hello"})

    assert action == Action(name="type", text="hello")


def test_key_carries_text() -> None:
    action = action_from_tool_input("key", {"text": "ctrl+s"})

    assert action == Action(name="key", text="ctrl+s")


def test_scroll_carries_direction_and_amount() -> None:
    action = action_from_tool_input("scroll", {"scroll_direction": "down", "scroll_amount": 3})

    assert action.scroll_direction == "down"
    assert action.scroll_amount == 3


def test_wait_carries_duration() -> None:
    action = action_from_tool_input("wait", {"duration": 1.5})

    assert action.duration == 1.5


def test_unsupported_action_becomes_harmless_screenshot() -> None:
    action = action_from_tool_input("zoom", {"region": [0, 0, 10, 10]})

    assert action == Action(name="screenshot")


def test_missing_coordinate_is_none_not_empty_tuple() -> None:
    action = action_from_tool_input("left_click", {})

    assert action.coordinate is None


def test_reasoning_is_carried_through_when_present() -> None:
    action = action_from_tool_input("key", {"text": "ctrl+s", "reasoning": "Saving my work."})

    assert action.reasoning == "Saving my work."


def test_reasoning_defaults_to_none_when_absent() -> None:
    action = action_from_tool_input("type", {"text": "hello"})

    assert action.reasoning is None


def test_type_with_submit_true_is_carried_through() -> None:
    action = action_from_tool_input("type", {"text": "0,0", "submit": True})

    assert action.submit is True


def test_type_submit_defaults_to_false_when_absent() -> None:
    action = action_from_tool_input("type", {"text": "0,0"})

    assert action.submit is False


def test_submit_is_ignored_for_non_type_actions() -> None:
    # `submit` only makes sense for `type` — a model incorrectly sending it
    # alongside e.g. `key` should not silently start submitting other
    # actions too.
    action = action_from_tool_input("key", {"text": "ctrl+s", "submit": True})

    assert action.submit is False
