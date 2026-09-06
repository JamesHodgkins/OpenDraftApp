"""Claude computer-use Brain — decides actions via the Anthropic API using
the ``computer_toolset_20260801`` tool.

Requires ``anthropic`` installed and ``ANTHROPIC_API_KEY`` (or another
credential source the SDK resolves).
"""
from __future__ import annotations

import base64
import dataclasses
import math
from typing import List, Optional

from ai_user.actions import Action
from ai_user.brain_common import action_from_tool_input

MODEL_ID = "claude-opus-5"
COMPUTER_TOOL_TYPE = "computer_toolset_20260801"

# Resolution ceiling for computer_toolset_20260801 (Opus 4.7+ tier), per the
# Anthropic computer-use spec: long edge <= 2576px, <= ~3.75 total megapixels.
_MAX_LONG_EDGE = 2576
_MAX_VISUAL_PIXELS = 4784 * 1024  # generous stand-in for the "4784 visual tokens" cap

_SYSTEM_PROMPT = (
    "You are operating OpenDraft, a 2D CAD desktop application, entirely "
    "through screenshots and simulated mouse/keyboard input — exactly as a "
    "human user would. You cannot inspect the application's internal state, "
    "only what the screenshot shows. Prefer the keyboard (typing command "
    "names and values into the command bar, pressing Enter/Space/Escape) "
    "over dragging the mouse freehand, since precise numeric input is more "
    "reliable than eyeballing points on the canvas. Before every tool call, "
    "say one short sentence explaining why you're taking that specific "
    "action given what the screenshot shows — this is kept for later review "
    "of what you were doing and why, so always include it. When the "
    "screenshot shows the task is complete, stop requesting tool actions and "
    "reply with a short confirmation in plain text instead."
)


def _scale_factor(width: int, height: int) -> float:
    long_edge_scale = _MAX_LONG_EDGE / max(width, height)
    pixel_scale = math.sqrt(_MAX_VISUAL_PIXELS / (width * height))
    return min(1.0, long_edge_scale, pixel_scale)


class ClaudeComputerUseBrain:
    """Drives decisions via the real Anthropic API, using the
    ``computer_toolset_20260801`` tool.
    """

    def __init__(self, model: str = MODEL_ID) -> None:
        try:
            import anthropic  # local import: keep this an optional dependency
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "ClaudeComputerUseBrain requires the 'anthropic' package. "
                "Install it with: pip install anthropic"
            ) from exc

        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = model
        self._messages: List[dict] = []
        self._pending_tool_use_id: Optional[str] = None

    def reset(self, prompt: str) -> None:
        self._messages = []
        self._pending_tool_use_id = None
        self._messages.append({
            "role": "user",
            "content": [{
                "type": "text",
                "text": f"Task: {prompt}\n\nA screenshot of the current app state follows.",
            }],
        })

    def next_action(self, screenshot_png: bytes, width: int, height: int) -> Action:
        # OpenDraft's window size (1600x1000 default) is well under the
        # computer-use resolution ceiling (long edge <= 2576px), so no
        # downscaling is needed in practice; _scale_factor documents the
        # limit for anyone changing the default window size.
        assert _scale_factor(width, height) == 1.0, (
            f"screenshot {width}x{height} exceeds the computer-use resolution "
            "ceiling — downscale before sending, and un-scale returned "
            "coordinates in AppHarness.perform()"
        )
        b64 = base64.standard_b64encode(screenshot_png).decode("ascii")
        image_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        }
        if self._pending_tool_use_id:
            self._messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": self._pending_tool_use_id,
                    "toolset_name": "computer",
                    "content": [image_block],
                }],
            })
        else:
            # First turn: no pending tool_use to answer yet, just hand over
            # the initial screenshot as plain user content.
            self._messages.append({"role": "user", "content": [image_block]})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            tools=[{"type": COMPUTER_TOOL_TYPE}],
            messages=self._messages,
        )
        self._messages.append({"role": "assistant", "content": response.content})

        # A `text` block preceding the `tool_use` block in the same turn is
        # the model's one-line rationale (asked for in the system prompt) —
        # collect it so it can ride along on the Action for later review.
        reasoning_parts = [block.text for block in response.content if block.type == "text" and block.text]
        reasoning = " ".join(reasoning_parts).strip() or None

        for block in response.content:
            if block.type == "tool_use" and getattr(block, "toolset_name", None) == "computer":
                self._pending_tool_use_id = block.id
                action = action_from_tool_input(block.name, block.input)
                return dataclasses.replace(action, reasoning=reasoning)

        # No tool_use block => the model considers the task finished; its
        # text (collected above) is the completion summary.
        self._pending_tool_use_id = None
        return Action(name="done", reasoning=reasoning)

    def observe_result(self, action: Action, note: str) -> None:
        # Feedback is folded into the next screenshot's tool_result; nothing
        # extra to send here for the simple action set we support.
        pass
