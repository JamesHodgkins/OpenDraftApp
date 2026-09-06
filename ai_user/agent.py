"""The agent loop: a Brain decides actions, the harness executes them, the
scorer tallies points, and a task verifier decides completion.

The decision-making step is behind the small ``Brain`` protocol so the loop
itself — turn limits, scoring, screenshot capture, done-detection — can be
exercised in tests without a live API key, and so different vendors'
vision+tool-calling models can be swapped in without touching the loop:
``brains_claude.ClaudeComputerUseBrain`` (Anthropic, computer-use tool) and
``brains_mistral.MistralVisionBrain`` (Mistral, a custom function-calling
tool) both implement it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from ai_user.actions import Action
from ai_user.app_harness import AppHarness
from ai_user.best_scores import BestScoreStore
from ai_user.scoring import ScoreKeeper, ScoreResult
from ai_user.tasks import Task


class Brain(Protocol):
    """Decides the next action given the current screenshot + running
    transcript. Implementations may keep their own multi-turn state.
    """

    def reset(self, prompt: str) -> None:
        ...

    def next_action(self, screenshot_png: bytes, width: int, height: int) -> Action:
        ...

    def observe_result(self, action: Action, note: str) -> None:
        """Feed back the outcome of the previous action (e.g. an error) before
        asking for the next one."""
        ...


@dataclass
class EpisodeResult:
    task: Task
    score: ScoreResult


class AgentRunner:
    """Runs one task episode end-to-end against a real ``AppHarness``."""

    def __init__(self, harness: AppHarness, brain: Brain, best_scores: Optional[BestScoreStore] = None) -> None:
        self.harness = harness
        self.brain = brain
        self.best_scores = best_scores or BestScoreStore()

    def run(self, task: Task) -> EpisodeResult:
        keeper = ScoreKeeper()
        self.brain.reset(task.prompt)

        completed = False
        step_count = 0
        for step in range(task.max_steps):
            width, height = self.harness.window_size()
            png = self.harness.screenshot_png_bytes()
            action = self.brain.next_action(png, width, height)

            if action.name == "done":
                step_count = step
                completed = bool(task.verify(self._document()))
                break

            outcome = self.harness.perform(action)
            keeper.record(action, outcome)
            step_count = step + 1

            if task.verify(self._document()):
                # Task is objectively done even if the agent hasn't said so —
                # still let it emit `done` next turn for a clean stop, but
                # cap the episode here so a wandering agent can't rack up
                # extra penalty steps after finishing.
                completed = True
                self.brain.observe_result(action, "Task appears complete.")
                break

            self.brain.observe_result(action, "ok")

        previous_best = self.best_scores.best_for(task.task_id)
        result = keeper.finalize(completed=completed, step_count=step_count, previous_best=previous_best)
        if completed:
            self.best_scores.record_if_better(task.task_id, step_count, result.total_points)
        return EpisodeResult(task=task, score=result)

    def _document(self):
        return self.harness.window.editor.document
