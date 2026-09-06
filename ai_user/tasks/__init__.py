"""Task definitions for the AI user.

A task is a plain prompt (what the agent is told, in natural language — it
must interpret and execute it purely through the GUI) plus a ``verify``
function that inspects the app's real ``DocumentStore`` afterward to decide
whether the task was actually completed. The verifier is the *only* place
internal state is read; it exists to make scoring objective, not to help the
agent — the agent itself never sees it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.document import DocumentStore


@dataclass(frozen=True)
class Task:
    task_id: str
    prompt: str
    verify: Callable[[DocumentStore], bool]
    max_steps: int = 40
