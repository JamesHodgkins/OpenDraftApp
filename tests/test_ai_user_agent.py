"""Tests for ai_user.agent.AgentRunner using a scripted fake Brain — no
network/API dependency. Verifies the loop mechanics: turn limits, done
handling, verifier-triggered early stop, and best-score bookkeeping.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from typing import List

import pytest

from app.entities import LineEntity, Vec2

from ai_user.actions import Action
from ai_user.agent import AgentRunner
from ai_user.app_harness import AppHarness
from ai_user.best_scores import BestScoreStore
from ai_user.tasks import Task


class ScriptedBrain:
    """Replays a fixed list of actions, ignoring the screenshot entirely —
    a stand-in for a live Claude decision loop in tests."""

    def __init__(self, script: List[Action]) -> None:
        self.script = list(script)
        self.index = 0
        self.reset_calls = 0
        self.observed: List[str] = []

    def reset(self, prompt: str) -> None:
        self.reset_calls += 1
        self.index = 0

    def next_action(self, screenshot_png: bytes, width: int, height: int) -> Action:
        if self.index >= len(self.script):
            return Action(name="done")
        action = self.script[self.index]
        self.index += 1
        return action

    def observe_result(self, action: Action, note: str) -> None:
        self.observed.append(note)


@pytest.fixture
def harness():
    h = AppHarness()
    yield h
    h.close()


def _never_complete_task(max_steps: int = 5) -> Task:
    return Task(task_id="test_never_complete", prompt="Do nothing achievable.", verify=lambda doc: False, max_steps=max_steps)


def _line_exists_task(max_steps: int = 10) -> Task:
    return Task(task_id="test_line_exists", prompt="Draw a line.", verify=lambda doc: any(isinstance(e, LineEntity) for e in doc.entities), max_steps=max_steps)


def test_runner_stops_when_brain_emits_done(harness, tmp_path) -> None:
    brain = ScriptedBrain([Action(name="done")])
    runner = AgentRunner(harness, brain, BestScoreStore(path=tmp_path / "best.json"))

    result = runner.run(_never_complete_task())

    assert result.score.step_count == 0
    assert result.score.completed is False


def test_runner_respects_max_steps_when_brain_never_stops(harness, tmp_path) -> None:
    # Script longer than max_steps; ScriptedBrain will keep returning
    # `screenshot` actions (a real no-op) forever if not capped.
    brain = ScriptedBrain([Action(name="screenshot") for _ in range(100)])
    task = _never_complete_task(max_steps=4)
    runner = AgentRunner(harness, brain, BestScoreStore(path=tmp_path / "best.json"))

    result = runner.run(task)

    assert result.score.step_count == 4
    assert result.score.completed is False


def test_runner_detects_completion_via_verifier_and_stops_early(harness, tmp_path) -> None:
    # Directly add a line to the document to simulate the verifier tripping
    # after the agent's very first action, without needing a real drawing
    # flow driven through the GUI for this loop-mechanics test.
    def add_line_as_side_effect():
        harness.window.editor.document.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        return Action(name="screenshot")

    class OneShotBrain:
        def __init__(self):
            self.calls = 0

        def reset(self, prompt):
            self.calls = 0

        def next_action(self, screenshot_png, width, height):
            self.calls += 1
            if self.calls == 1:
                return add_line_as_side_effect()
            return Action(name="done")

        def observe_result(self, action, note):
            pass

    brain = OneShotBrain()
    runner = AgentRunner(harness, brain, BestScoreStore(path=tmp_path / "best.json"))

    result = runner.run(_line_exists_task())

    assert result.score.completed is True
    assert result.score.step_count == 1  # stopped right after the action that satisfied verify()


def test_completed_run_updates_best_score_store(harness, tmp_path) -> None:
    def add_line_as_side_effect():
        harness.window.editor.document.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        return Action(name="screenshot")

    class OneShotBrain:
        def reset(self, prompt):
            self.calls = 0

        def next_action(self, screenshot_png, width, height):
            self.calls = getattr(self, "calls", 0) + 1
            if self.calls == 1:
                return add_line_as_side_effect()
            return Action(name="done")

        def observe_result(self, action, note):
            pass

    store = BestScoreStore(path=tmp_path / "best.json")
    runner = AgentRunner(harness, OneShotBrain(), store)

    result = runner.run(_line_exists_task())

    assert result.score.is_new_best is True
    assert store.best_for("test_line_exists") == 1


def test_brain_reset_is_called_once_per_run(harness, tmp_path) -> None:
    brain = ScriptedBrain([Action(name="done")])
    runner = AgentRunner(harness, brain, BestScoreStore(path=tmp_path / "best.json"))

    runner.run(_never_complete_task())

    assert brain.reset_calls == 1
