"""Unit tests for ai_user.brains_mistral.MistralVisionBrain — exercised with
a fake client so no network call / API key is needed. Verifies the request
shape sent to Mistral (vision image_url block, tool schema) and correct
decoding of the tool_call response into an Action.
"""
from __future__ import annotations

import json
import sys
import types

import pytest


class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: dict) -> None:
        self.id = call_id
        self.function = _FakeFunction(name, json.dumps(arguments))


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [_FakeChoice(message)]


class _FakeChatNamespace:
    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeMistralClient:
    def __init__(self, responses) -> None:
        self.chat = _FakeChatNamespace(responses)


@pytest.fixture
def fake_mistralai_module(monkeypatch):
    """Install a fake ``mistralai.client`` module so MistralVisionBrain can
    be imported/constructed without the real package installed."""
    fake_client_module = types.ModuleType("mistralai.client")

    holder = {}

    class _Mistral:
        def __init__(self, *args, **kwargs):
            holder["instance"] = holder["queued_client"]

        def __getattr__(self, name):
            return getattr(holder["instance"], name)

    fake_client_module.Mistral = _Mistral
    fake_mistralai = types.ModuleType("mistralai")
    fake_mistralai.client = fake_client_module

    monkeypatch.setitem(sys.modules, "mistralai", fake_mistralai)
    monkeypatch.setitem(sys.modules, "mistralai.client", fake_client_module)
    return holder


def _make_brain(fake_mistralai_module, responses):
    from ai_user.brains_mistral import MistralVisionBrain

    fake_mistralai_module["queued_client"] = _FakeMistralClient(responses)
    return MistralVisionBrain()


def test_reset_seeds_system_and_task_messages(fake_mistralai_module) -> None:
    brain = _make_brain(fake_mistralai_module, responses=[])

    brain.reset("Draw a line.")

    roles = [m["role"] for m in brain._messages]
    assert roles == ["system", "user"]
    assert "Draw a line." in brain._messages[1]["content"][0]["text"]


def test_next_action_sends_vision_image_block_and_tool_schema(fake_mistralai_module) -> None:
    tool_call = _FakeToolCall("call_1", "computer_action", {"action": "left_click", "coordinate": [5, 6]})
    response = _FakeResponse(_FakeMessage(tool_calls=[tool_call]))
    brain = _make_brain(fake_mistralai_module, responses=[response])
    brain.reset("Draw a line.")

    action = brain.next_action(b"\x89PNGfakepngbytes", 1600, 1000)

    sent_kwargs = brain.client.chat.calls[0]
    assert sent_kwargs["tools"][0]["function"]["name"] == "computer_action"
    image_blocks = [c for c in brain._messages[1]["content"] if c["type"] == "image_url"]
    assert len(image_blocks) == 1
    assert image_blocks[0]["image_url"].startswith("data:image/png;base64,")

    assert action.name == "left_click"
    assert action.coordinate == (5, 6)


def test_tool_schema_requires_reasoning_alongside_action(fake_mistralai_module) -> None:
    from ai_user.brains_mistral import _TOOL_SCHEMA

    params = _TOOL_SCHEMA["function"]["parameters"]
    assert "reasoning" in params["properties"]
    assert "reasoning" in params["required"]


def test_reasoning_is_decoded_onto_the_returned_action(fake_mistralai_module) -> None:
    tool_call = _FakeToolCall(
        "call_1", "computer_action",
        {"action": "key", "text": "ctrl+s", "reasoning": "Saving my progress before continuing."},
    )
    response = _FakeResponse(_FakeMessage(tool_calls=[tool_call]))
    brain = _make_brain(fake_mistralai_module, responses=[response])
    brain.reset("Draw a line.")

    action = brain.next_action(b"png1", 1600, 1000)

    assert action.reasoning == "Saving my progress before continuing."


def test_next_action_with_no_tool_call_returns_done(fake_mistralai_module) -> None:
    response = _FakeResponse(_FakeMessage(content="Looks complete!", tool_calls=[]))
    brain = _make_brain(fake_mistralai_module, responses=[response])
    brain.reset("Draw a line.")

    action = brain.next_action(b"\x89PNGfakepngbytes", 1600, 1000)

    assert action.name == "done"


def test_second_turn_replies_to_pending_tool_call_before_new_image(fake_mistralai_module) -> None:
    first_call = _FakeToolCall("call_1", "computer_action", {"action": "screenshot"})
    responses = [
        _FakeResponse(_FakeMessage(tool_calls=[first_call])),
        _FakeResponse(_FakeMessage(content="All done.", tool_calls=[])),
    ]
    brain = _make_brain(fake_mistralai_module, responses=responses)
    brain.reset("Draw a line.")

    brain.next_action(b"png1", 1600, 1000)
    brain.next_action(b"png2", 1600, 1000)

    tool_reply_messages = [m for m in brain._messages if m.get("role") == "tool"]
    assert len(tool_reply_messages) == 1
    assert tool_reply_messages[0]["tool_call_id"] == "call_1"


def test_multiple_tool_calls_in_one_turn_all_get_a_reply(fake_mistralai_module) -> None:
    # Regression test: observed live against the real Mistral API — despite
    # the system prompt asking for exactly one call per turn, the model can
    # still return several tool_calls in a single assistant message (e.g.
    # 'type' followed by 'key'). Every one of them MUST get a matching
    # `tool` reply before the next request, or the real API rejects the
    # whole conversation with "Not the same number of function calls and
    # responses" (400, invalid_request_message_order) — this bit a live run
    # (see conversation history) before the fix.
    first_call = _FakeToolCall("call_1", "computer_action", {"action": "type", "text": "line"})
    second_call = _FakeToolCall("call_2", "computer_action", {"action": "key", "text": "Return"})
    responses = [
        _FakeResponse(_FakeMessage(tool_calls=[first_call, second_call])),
        _FakeResponse(_FakeMessage(content="All done.", tool_calls=[])),
    ]
    brain = _make_brain(fake_mistralai_module, responses=responses)
    brain.reset("Draw a line.")

    action = brain.next_action(b"png1", 1600, 1000)
    # Only the first call becomes this turn's Action — we can only perform
    # one input action per turn.
    assert action.name == "type"

    brain.next_action(b"png2", 1600, 1000)

    tool_reply_ids = [m["tool_call_id"] for m in brain._messages if m.get("role") == "tool"]
    assert tool_reply_ids == ["call_1", "call_2"]
