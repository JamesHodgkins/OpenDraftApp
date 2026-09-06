"""Mistral vision Brain — decides actions via the Mistral API.

Mistral has no computer-use preset tool (unlike Anthropic's
``computer_toolset_20260801``), so this defines an ordinary function-calling
tool, ``computer_action``, whose parameters mirror our ``Action``
vocabulary. The model gets the screenshot as an ``image_url`` content block
(a base64 data URI) alongside the task text, and must call ``computer_action``
to act — same perceive/decide/act contract as the Claude brain, different
wire format.

Requires ``mistralai`` installed and ``MISTRAL_API_KEY`` (or another
credential source the SDK resolves).
"""
from __future__ import annotations

import base64
import json
from typing import List

from ai_user.actions import Action
from ai_user.brain_common import SUPPORTED_ACTIONS, action_from_tool_input

MODEL_ID = "mistral-large-latest"  # vision=True, function_calling=True per client.models.list()
TOOL_NAME = "computer_action"

_SYSTEM_PROMPT = (
    "You are operating OpenDraft, a 2D CAD desktop application, entirely "
    "through screenshots and simulated mouse/keyboard input — exactly as a "
    "human user would. You cannot inspect the application's internal state, "
    "only what the screenshot shows. Prefer the keyboard (typing command "
    "names and values into the command bar) over dragging the mouse "
    "freehand, since precise numeric input is more reliable than eyeballing "
    "points on the canvas. On every turn you must call the computer_action "
    "tool exactly once to act — never call it more than once per turn, "
    "since each screenshot only reflects one action at a time. "
    "IMPORTANT: whenever you use 'type' to enter a command name, a "
    "coordinate, or any other value that should be submitted right away, "
    "set submit=true in the same call — this types the text AND presses "
    "Enter to confirm it in one action, so you never leave a value typed "
    "but unconfirmed. Only use submit=false if you deliberately want to "
    "leave text in the field without submitting it yet. "
    "IMPORTANT: the small status label near the command bar (e.g. 'First "
    "corner', 'Radius', 'End vector') names exactly what value the app is "
    "currently waiting for — read it before deciding what to type. Do not "
    "rely on prior CAD experience or convention if the label says "
    "something else; a multi-step command like a rectangle asks for one "
    "point/value at a time, in the order the label shows, and skipping a "
    "step because you expect a different workflow will leave the command "
    "stuck. Most labels, including 'First corner' and 'Opposite corner', "
    "want a plain absolute coordinate ('x,y', e.g. '100,50') — do NOT use "
    "an '@dx,dy' relative-offset prefix unless the label is explicitly "
    "named 'vector' or similar; using '@' for a plain corner/point label "
    "will not be accepted and the command will silently stay stuck waiting "
    "for that same value. If typing a value doesn't advance to the next "
    "label on the next screenshot, you used the wrong format — try a plain "
    "'x,y' coordinate instead. Never assume a previous action succeeded — "
    "check what the latest screenshot actually shows before deciding your "
    "next action. When the screenshot shows the task is complete, stop "
    "calling the tool and reply with a short confirmation in plain text "
    "instead."
)

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Perform one input action against the app shown in the most recent "
            "screenshot. Coordinates are pixel offsets from the top-left of that "
            "screenshot."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": (
                        "One short sentence explaining why you're taking this "
                        "specific action right now, given what the screenshot shows."
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": sorted(SUPPORTED_ACTIONS),
                    "description": "Which input action to perform.",
                },
                "coordinate": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "[x, y] pixel coordinate, required for left_click/double_click.",
                },
                "text": {
                    "type": "string",
                    "description": (
                        "For 'type': the literal text to type. For 'key': a key "
                        "name or combo, e.g. 'Return', 'ctrl+s', 'a'."
                    ),
                },
                "submit": {
                    "type": "boolean",
                    "description": (
                        "'type' only. When true, presses Enter immediately after "
                        "typing `text`, submitting it in this same action instead "
                        "of leaving it typed-but-unconfirmed. Use true whenever the "
                        "value should be confirmed right away (the common case)."
                    ),
                },
                "scroll_direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right"],
                },
                "scroll_amount": {"type": "integer"},
                "duration": {"type": "number", "description": "Seconds, for 'wait'."},
            },
            "required": ["reasoning", "action"],
            "additionalProperties": False,
        },
    },
}


class MistralVisionBrain:
    """Drives decisions via the real Mistral API (vision + function calling)."""

    def __init__(self, model: str = MODEL_ID) -> None:
        try:
            from mistralai.client import Mistral
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "MistralVisionBrain requires the 'mistralai' package. "
                "Install it with: pip install mistralai"
            ) from exc

        self.client = Mistral()
        self.model = model
        self._messages: List[dict] = []
        # Mistral can return *multiple* tool_calls in one assistant turn even
        # when asked for exactly one — every tool_call in a turn requires a
        # matching `tool` reply before the next request, or the API rejects
        # the whole conversation with "Not the same number of function calls
        # and responses". We execute only the first as our next Action, but
        # must still answer every other pending id so the transcript stays
        # valid.
        self._pending_tool_call_ids: List[str] = []

    def reset(self, prompt: str) -> None:
        self._messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Task: {prompt}\n\nA screenshot of the current app state follows.",
                    },
                ],
            },
        ]
        self._pending_tool_call_ids = []

    def next_action(self, screenshot_png: bytes, width: int, height: int) -> Action:
        b64 = base64.standard_b64encode(screenshot_png).decode("ascii")
        image_block = {
            "type": "image_url",
            "image_url": f"data:image/png;base64,{b64}",
        }

        if self._pending_tool_call_ids:
            # Reply to every pending tool call from the previous turn (the
            # one we acted on gets the real screenshot; any extras the model
            # incorrectly batched in get a stub result, since only one
            # action can actually be performed per turn), then hand over a
            # fresh user turn with the resulting screenshot.
            first_id, *extra_ids = self._pending_tool_call_ids
            self._messages.append({
                "role": "tool",
                "tool_call_id": first_id,
                "name": TOOL_NAME,
                "content": "ok",
            })
            for extra_id in extra_ids:
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": extra_id,
                    "name": TOOL_NAME,
                    "content": (
                        "Not executed — only one action can be performed per "
                        "turn. Call the tool again next turn if this is still "
                        "needed."
                    ),
                })
            self._messages.append({"role": "user", "content": [image_block]})
        else:
            # First turn: fold the screenshot into the existing user message.
            self._messages[-1]["content"].append(image_block)

        response = self.client.chat.complete(
            model=self.model,
            messages=self._messages,
            tools=[_TOOL_SCHEMA],
            tool_choice="auto",
            stream=False,
        )
        message = response.choices[0].message
        self._messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": message.tool_calls,
        })

        tool_calls = message.tool_calls or []
        if tool_calls:
            self._pending_tool_call_ids = [c.id for c in tool_calls]
            call = tool_calls[0]
            try:
                args = json.loads(call.function.arguments)
            except (TypeError, ValueError):
                args = {}
            action_name = args.pop("action", "screenshot")
            return action_from_tool_input(action_name, args)

        # No tool call => the model considers the task finished.
        self._pending_tool_call_ids = []
        return Action(name="done")

    def observe_result(self, action: Action, note: str) -> None:
        # Feedback is folded into the next screenshot's tool-result turn;
        # nothing extra to send here for the simple action set we support.
        pass
