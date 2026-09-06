"""Persists the best (fewest-steps) completed run per task, as local JSON.

Keyed by task id. Only a completed run counts as a candidate best — an
incomplete episode never overwrites a recorded best, no matter how few steps
it took.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

DEFAULT_PATH = Path(__file__).parent / "scores" / "best_runs.json"


@dataclass
class BestRun:
    step_count: int
    total_points: int


class BestScoreStore:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = path
        self._data: Dict[str, BestRun] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for task_id, entry in raw.items():
            self._data[task_id] = BestRun(
                step_count=entry["step_count"],
                total_points=entry["total_points"],
            )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            task_id: {"step_count": run.step_count, "total_points": run.total_points}
            for task_id, run in self._data.items()
        }
        self.path.write_text(json.dumps(serializable, indent=2, sort_keys=True), encoding="utf-8")

    def best_for(self, task_id: str) -> Optional[int]:
        run = self._data.get(task_id)
        return run.step_count if run else None

    def record_if_better(self, task_id: str, step_count: int, total_points: int) -> bool:
        """Store this run as the new best for ``task_id`` if it beats (or is
        the first for) that task. Returns whether it was recorded.
        """
        current = self._data.get(task_id)
        if current is not None and step_count >= current.step_count:
            return False
        self._data[task_id] = BestRun(step_count=step_count, total_points=total_points)
        self._save()
        return True
