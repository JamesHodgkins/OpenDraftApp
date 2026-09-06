"""Unit tests for ai_user.scoring — the point rules.

These construct ActionOutcome directly rather than driving a real Qt window,
so the scoring rules can be verified in isolation from Qt/harness plumbing.
"""
from __future__ import annotations

from ai_user.actions import Action
from ai_user.app_harness import ActionOutcome, ScreenRegion
from ai_user.scoring import (
    KEYBOARD_INPUT_POINTS,
    NEW_BEST_BONUS,
    PROPERTIES_CLICK_PENALTY,
    REPEATED_ACTION_PENALTY,
    ScoreKeeper,
)


class _Widget:
    """A cheap stand-in for a focus-tracked widget identity."""


def test_keyboard_input_scores_positive() -> None:
    keeper = ScoreKeeper()
    w = _Widget()
    action = Action(name="key", text="ctrl+s")
    outcome = ActionOutcome(region=ScreenRegion.OTHER, focus_before=w, focus_after=w, used_keyboard_area=True)

    record = keeper.record(action, outcome)

    assert record.points == KEYBOARD_INPUT_POINTS


def test_click_in_properties_panel_is_penalized() -> None:
    keeper = ScoreKeeper()
    w1, w2 = _Widget(), _Widget()
    action = Action(name="left_click", coordinate=(10, 10))
    outcome = ActionOutcome(
        region=ScreenRegion.PROPERTIES_PANEL, focus_before=w1, focus_after=w2, used_keyboard_area=False,
    )

    record = keeper.record(action, outcome)

    assert record.points == PROPERTIES_CLICK_PENALTY


def test_click_in_viewport_is_not_penalized() -> None:
    keeper = ScoreKeeper()
    w1, w2 = _Widget(), _Widget()
    action = Action(name="left_click", coordinate=(10, 10))
    outcome = ActionOutcome(
        region=ScreenRegion.VIEWPORT, focus_before=w1, focus_after=w2, used_keyboard_area=False,
    )

    record = keeper.record(action, outcome)

    assert record.points == 0


def test_repeating_the_identical_action_is_penalized() -> None:
    keeper = ScoreKeeper()
    w = _Widget()
    action = Action(name="key", text="a")
    outcome = ActionOutcome(region=ScreenRegion.OTHER, focus_before=w, focus_after=w, used_keyboard_area=True)

    first = keeper.record(action, outcome)
    second = keeper.record(action, outcome)

    assert first.points == KEYBOARD_INPUT_POINTS  # no penalty the first time
    assert second.points == KEYBOARD_INPUT_POINTS + REPEATED_ACTION_PENALTY


def test_click_that_fails_to_move_focus_is_treated_as_unregistered_input() -> None:
    keeper = ScoreKeeper()
    w = _Widget()
    action = Action(name="left_click", coordinate=(5, 5))
    # focus_after is the SAME object as focus_before => nothing took focus.
    outcome = ActionOutcome(region=ScreenRegion.VIEWPORT, focus_before=w, focus_after=w, used_keyboard_area=False)

    record = keeper.record(action, outcome)

    assert record.points == REPEATED_ACTION_PENALTY


def test_click_that_moves_focus_is_not_treated_as_lost_focus() -> None:
    keeper = ScoreKeeper()
    w1, w2 = _Widget(), _Widget()
    action = Action(name="left_click", coordinate=(5, 5))
    outcome = ActionOutcome(region=ScreenRegion.VIEWPORT, focus_before=w1, focus_after=w2, used_keyboard_area=False)

    record = keeper.record(action, outcome)

    assert record.points == 0


def test_screenshot_and_wait_are_never_penalized_as_repeats() -> None:
    keeper = ScoreKeeper()
    w = _Widget()
    outcome = ActionOutcome(region=ScreenRegion.OTHER, focus_before=w, focus_after=w, used_keyboard_area=False)

    keeper.record(Action(name="screenshot"), outcome)
    second = keeper.record(Action(name="screenshot"), outcome)

    assert second.points == 0


def test_finalize_awards_new_best_bonus_when_fewer_steps_than_previous_best() -> None:
    keeper = ScoreKeeper()

    result = keeper.finalize(completed=True, step_count=5, previous_best=10)

    assert result.is_new_best is True
    assert result.total_points == NEW_BEST_BONUS


def test_finalize_does_not_award_bonus_when_not_better() -> None:
    keeper = ScoreKeeper()

    result = keeper.finalize(completed=True, step_count=10, previous_best=10)

    assert result.is_new_best is False
    assert result.total_points == 0


def test_finalize_does_not_award_bonus_when_incomplete_even_if_fewer_steps() -> None:
    keeper = ScoreKeeper()

    result = keeper.finalize(completed=False, step_count=2, previous_best=10)

    assert result.is_new_best is False
    assert result.total_points == 0


def test_finalize_awards_bonus_on_first_ever_completed_run() -> None:
    keeper = ScoreKeeper()

    result = keeper.finalize(completed=True, step_count=3, previous_best=None)

    assert result.is_new_best is True
    assert result.total_points == NEW_BEST_BONUS


def test_total_points_sums_all_recorded_steps_plus_bonus() -> None:
    keeper = ScoreKeeper()
    w = _Widget()
    kb_outcome = ActionOutcome(region=ScreenRegion.OTHER, focus_before=w, focus_after=w, used_keyboard_area=True)
    panel_outcome = ActionOutcome(
        region=ScreenRegion.PROPERTIES_PANEL, focus_before=w, focus_after=_Widget(), used_keyboard_area=False,
    )

    keeper.record(Action(name="key", text="a"), kb_outcome)
    keeper.record(Action(name="left_click", coordinate=(1, 1)), panel_outcome)

    result = keeper.finalize(completed=True, step_count=2, previous_best=None)

    assert result.total_points == KEYBOARD_INPUT_POINTS + PROPERTIES_CLICK_PENALTY + NEW_BEST_BONUS


def test_summary_includes_action_reasoning_when_present() -> None:
    keeper = ScoreKeeper()
    w = _Widget()
    outcome = ActionOutcome(region=ScreenRegion.OTHER, focus_before=w, focus_after=w, used_keyboard_area=True)
    action = Action(name="key", text="ctrl+s", reasoning="Saving my progress before continuing.")

    keeper.record(action, outcome)
    result = keeper.finalize(completed=False, step_count=1, previous_best=None)

    assert "Saving my progress before continuing." in result.summary()


def test_summary_omits_reasoning_line_when_absent() -> None:
    keeper = ScoreKeeper()
    w = _Widget()
    outcome = ActionOutcome(region=ScreenRegion.OTHER, focus_before=w, focus_after=w, used_keyboard_area=True)

    keeper.record(Action(name="key", text="a"), outcome)
    result = keeper.finalize(completed=False, step_count=1, previous_best=None)

    assert "->" not in result.summary()
