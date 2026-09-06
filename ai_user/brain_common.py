"""Shared helpers for Brain implementations that translate a vendor's tool
call into our ``Action`` vocabulary.

Both ``brains_claude.ClaudeComputerUseBrain`` and
``brains_mistral.MistralVisionBrain`` produce the same ``Action`` objects
from a per-vendor function-call payload — this module holds the one bit of
logic that's genuinely shared between them.
"""
from __future__ import annotations

from typing import Any, Dict

from ai_user.actions import Action

SUPPORTED_ACTIONS = {"screenshot", "left_click", "double_click", "type", "key", "scroll", "wait"}


def action_from_tool_input(action_name: str, tool_input: Dict[str, Any]) -> Action:
    """Build an ``Action`` from a decoded ``{action_name: ..., **params}``
    payload. Any action name we don't wire up (zoom, mouse_move, hold_key,
    ...) becomes a harmless ``screenshot`` rather than crashing the episode.
    """
    if action_name not in SUPPORTED_ACTIONS:
        return Action(name="screenshot")

    coordinate = tool_input.get("coordinate")
    modifiers = ()
    if action_name in ("left_click", "double_click") and tool_input.get("text"):
        modifiers = tuple(tool_input["text"].split("+"))

    return Action(
        name=action_name,
        coordinate=tuple(coordinate) if coordinate else None,
        text=tool_input.get("text") if action_name in ("type", "key") else None,
        scroll_direction=tool_input.get("scroll_direction"),
        scroll_amount=tool_input.get("scroll_amount"),
        duration=tool_input.get("duration"),
        modifiers=modifiers,
        reasoning=tool_input.get("reasoning"),
        submit=bool(tool_input.get("submit")) if action_name == "type" else False,
    )
