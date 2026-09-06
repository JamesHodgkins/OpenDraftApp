"""Unit tests for ai_user.best_scores — persisted best-run tracking."""
from __future__ import annotations

from ai_user.best_scores import BestScoreStore


def test_first_recorded_run_is_always_best(tmp_path) -> None:
    store = BestScoreStore(path=tmp_path / "best.json")

    recorded = store.record_if_better("draw_a_line", step_count=5, total_points=3)

    assert recorded is True
    assert store.best_for("draw_a_line") == 5


def test_fewer_steps_beats_previous_best(tmp_path) -> None:
    store = BestScoreStore(path=tmp_path / "best.json")
    store.record_if_better("draw_a_line", step_count=5, total_points=3)

    recorded = store.record_if_better("draw_a_line", step_count=3, total_points=8)

    assert recorded is True
    assert store.best_for("draw_a_line") == 3


def test_equal_or_more_steps_does_not_overwrite(tmp_path) -> None:
    store = BestScoreStore(path=tmp_path / "best.json")
    store.record_if_better("draw_a_line", step_count=5, total_points=3)

    recorded_equal = store.record_if_better("draw_a_line", step_count=5, total_points=99)
    recorded_more = store.record_if_better("draw_a_line", step_count=7, total_points=99)

    assert recorded_equal is False
    assert recorded_more is False
    assert store.best_for("draw_a_line") == 5


def test_best_for_unknown_task_is_none(tmp_path) -> None:
    store = BestScoreStore(path=tmp_path / "best.json")

    assert store.best_for("nonexistent_task") is None


def test_persists_across_instances(tmp_path) -> None:
    path = tmp_path / "best.json"
    store = BestScoreStore(path=path)
    store.record_if_better("draw_circle_radius_5", step_count=4, total_points=1)

    reloaded = BestScoreStore(path=path)

    assert reloaded.best_for("draw_circle_radius_5") == 4


def test_tasks_are_tracked_independently(tmp_path) -> None:
    store = BestScoreStore(path=tmp_path / "best.json")
    store.record_if_better("draw_a_line", step_count=5, total_points=3)
    store.record_if_better("draw_circle_radius_5", step_count=2, total_points=3)

    assert store.best_for("draw_a_line") == 5
    assert store.best_for("draw_circle_radius_5") == 2
