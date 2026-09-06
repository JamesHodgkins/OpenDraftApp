"""Implements the AI-user scoring rules.

Rules (as specified):

* +1 for each input which uses the keyboard area (A-Z, 0-9, Ctrl, Shift, Space).
* -2 for each time the user has to click in the properties/control input area
  (top-right of the viewport — i.e. the Controller dock).
* -10 every time the user has to repeat an action because the app loses
  focus, or does not "register" an input.
* +10 if the task is completed in fewer steps than the previous best.

"Repeat an action" is operationalised as: the agent performs the *same*
action (same name/coordinate/text) two turns in a row, OR the focused widget
changed to something other than what the previous action's own click/type
targeted (a focus-steal) between one action and the next. Both are read from
``ActionOutcome`` the harness already reports per step; the scorer never
inspects application state itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ai_user.actions import Action
from ai_user.app_harness import ActionOutcome, ScreenRegion

KEYBOARD_INPUT_POINTS = 1
PROPERTIES_CLICK_PENALTY = -2
REPEATED_ACTION_PENALTY = -10
NEW_BEST_BONUS = 10


@dataclass
class StepRecord:
    step_index: int
    action: Action
    outcome: ActionOutcome
    points: int
    reasons: List[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    steps: List[StepRecord] = field(default_factory=list)
    total_points: int = 0
    completed: bool = False
    step_count: int = 0
    is_new_best: bool = False
    previous_best: Optional[int] = None

    def summary(self) -> str:
        lines = [f"Steps taken: {self.step_count}", f"Completed: {self.completed}"]
        for s in self.steps:
            reason = "; ".join(s.reasons) if s.reasons else ""
            lines.append(f"  [{s.step_index:>3}] {s.action.name:<12} {s.points:+d}  {reason}")
            if s.action.reasoning:
                # Plain ASCII marker, not a unicode arrow — Windows consoles
                # commonly run a legacy codepage (cp1252) that can't encode
                # arbitrary unicode, and this is printed via plain `print()`.
                lines.append(f"        -> {s.action.reasoning}")
        lines.append(f"Total points: {self.total_points}")
        if self.is_new_best:
            lines.append(f"New best! (previous best: {self.previous_best})")
        return "\n".join(lines)


class ScoreKeeper:
    """Accumulates per-step scores across one task episode."""

    def __init__(self) -> None:
        self._steps: List[StepRecord] = []
        self._last_action: Optional[Action] = None

    def record(self, action: Action, outcome: ActionOutcome) -> StepRecord:
        points = 0
        reasons: List[str] = []

        if outcome.used_keyboard_area:
            points += KEYBOARD_INPUT_POINTS
            reasons.append(f"keyboard input ({KEYBOARD_INPUT_POINTS:+d})")

        if action.name in ("left_click", "double_click") and outcome.region == ScreenRegion.PROPERTIES_PANEL:
            points += PROPERTIES_CLICK_PENALTY
            reasons.append(f"click in properties/control area ({PROPERTIES_CLICK_PENALTY:+d})")

        repeated = self._is_repeat_of_last(action)
        focus_stolen = self._focus_was_stolen(action, outcome)
        if repeated or focus_stolen:
            points += REPEATED_ACTION_PENALTY
            why = "identical repeated action" if repeated else "focus lost / input not registered"
            reasons.append(f"{why} ({REPEATED_ACTION_PENALTY:+d})")

        record = StepRecord(
            step_index=len(self._steps),
            action=action,
            outcome=outcome,
            points=points,
            reasons=reasons,
        )
        self._steps.append(record)
        self._last_action = action
        return record

    def _is_repeat_of_last(self, action: Action) -> bool:
        if self._last_action is None:
            return False
        if action.name in ("screenshot", "wait", "done"):
            return False
        return (
            action.name == self._last_action.name
            and action.coordinate == self._last_action.coordinate
            and action.text == self._last_action.text
        )

    def _focus_was_stolen(self, action: Action, outcome: ActionOutcome) -> bool:
        """A click/type/key that should have landed on (or kept) a widget,
        but the widget holding focus right after differs from what a
        well-behaved app should have focused — approximated here as: the
        action targeted a specific widget via a click, yet focus afterwards
        is still whatever it was *before* the click (nothing took focus),
        which is the observable symptom of KNOWN_BUGS-style focus-steal bugs.
        """
        if action.name not in ("left_click", "double_click"):
            return False
        if outcome.region == ScreenRegion.OTHER:
            return False
        return outcome.focus_after is outcome.focus_before

    def finalize(self, completed: bool, step_count: int, previous_best: Optional[int]) -> ScoreResult:
        total = sum(s.points for s in self._steps)
        is_new_best = completed and (previous_best is None or step_count < previous_best)
        if is_new_best:
            total += NEW_BEST_BONUS
        return ScoreResult(
            steps=list(self._steps),
            total_points=total,
            completed=completed,
            step_count=step_count,
            is_new_best=is_new_best,
            previous_best=previous_best,
        )
