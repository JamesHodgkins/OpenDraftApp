"""The action vocabulary the AI user can request.

Mirrors the subset of Anthropic's ``computer_toolset_20260801`` member tools
that make sense for a single-window desktop app driven through Qt:
``screenshot``, ``left_click``, ``double_click``, ``type``, ``key``,
``scroll``, ``wait``, plus a harness-only ``done`` sentinel the agent uses to
end the episode. We deliberately don't wire up drag/middle-click/hold_key/
zoom — OpenDraft's tasks don't need them, and a smaller action surface means
fewer ways for the agent to do something the scoring rules can't classify.

Coordinates are always in *screenshot pixel space* (origin top-left),
matching the computer-use tool's coordinate contract. ``AppHarness``
translates those into real widget/global coordinates before injecting events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class Action:
    """One action requested by the agent for one turn.

    ``name`` is one of: screenshot, left_click, double_click, type, key,
    scroll, wait, done.
    """
    name: str
    coordinate: Optional[Tuple[int, int]] = None
    text: Optional[str] = None
    scroll_direction: Optional[str] = None
    scroll_amount: Optional[int] = None
    duration: Optional[float] = None
    # Free-form modifier keys accompanying a click, e.g. "shift".
    modifiers: Tuple[str, ...] = field(default_factory=tuple)
    # One-line rationale the agent gave for this action, if its Brain asked
    # for one (both bundled brains do) — surfaced in the score summary so a
    # run's transcript is debuggable after the fact instead of only showing
    # *what* it did. None for brains/actions that don't supply it.
    reasoning: Optional[str] = None
    # `type` only: when True, press Enter/Return immediately after typing
    # `text`, as a single atomic action. Added after live testing showed the
    # model reliably narrates "I will type X and press Enter to confirm" but
    # then only calls the tool once — typing X and leaving the confirming
    # Enter to a *separate* turn it doesn't always take. Structural fix: make
    # "type and confirm" one action the model can't half-do, rather than
    # relying on it remembering the second half next turn. See KNOWN_BUGS.
    submit: bool = False

    def __post_init__(self) -> None:
        valid = {
            "screenshot", "left_click", "double_click", "type", "key",
            "scroll", "wait", "done",
        }
        if self.name not in valid:
            raise ValueError(f"Unsupported action {self.name!r}; expected one of {sorted(valid)}")


# Keys that count toward the "+1 keyboard-area input" rule per the scoring
# spec: A-Z, 0-9, Ctrl, Shift, Space. Matched case-insensitively against the
# tokens of a `key` action's `text` (split on "+"), and against `type` text
# characters.
KEYBOARD_AREA_TOKENS = frozenset(
    list("abcdefghijklmnopqrstuvwxyz") + list("0123456789") + ["ctrl", "shift", "space"]
)
