"""CLI entry point for the AI user.

Usage:
    python -m ai_user.run --task draw_a_line
    python -m ai_user.run --list
    python -m ai_user.run --task draw_rectangle_100x50 --provider mistral
    python -m ai_user.run --task draw_rectangle_100x50 --visible
"""
from __future__ import annotations

import argparse
import os
import sys

_PROVIDERS = ("claude", "mistral")


def _make_brain(provider: str):
    if provider == "claude":
        from ai_user.brains_claude import ClaudeComputerUseBrain
        return ClaudeComputerUseBrain()
    if provider == "mistral":
        from ai_user.brains_mistral import MistralVisionBrain
        return MistralVisionBrain()
    raise ValueError(f"Unknown provider: {provider!r}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the AI user against OpenDraft.")
    parser.add_argument("--task", help="Task id to run (see --list).")
    parser.add_argument("--list", action="store_true", help="List available task ids and exit.")
    parser.add_argument(
        "--provider", choices=_PROVIDERS, default="claude",
        help="Which vision+tool-calling model drives the agent (default: claude).",
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Show the app window on-screen instead of offscreen rendering.",
    )
    args = parser.parse_args(argv)

    # Pick up ai_user/.env (e.g. MISTRAL_API_KEY) before constructing a
    # brain; never overrides an already-exported env var.
    from ai_user.dotenv_loader import load_ai_user_env
    load_ai_user_env()

    # Must happen before importing ai_user.app_harness, which sets the
    # offscreen default (via os.environ.setdefault) at import time.
    if args.visible:
        os.environ.pop("QT_QPA_PLATFORM", None)

    from ai_user.agent import AgentRunner
    from ai_user.app_harness import AppHarness
    from ai_user.best_scores import BestScoreStore
    from ai_user.tasks.basic_shapes import ALL_TASKS, TASKS_BY_ID

    if args.list or not args.task:
        for t in ALL_TASKS:
            print(f"{t.task_id:<28} {t.prompt}")
        return 0

    task = TASKS_BY_ID.get(args.task)
    if task is None:
        print(f"Unknown task id: {args.task!r}", file=sys.stderr)
        return 2

    harness = AppHarness()
    try:
        brain = _make_brain(args.provider)
        runner = AgentRunner(harness, brain, BestScoreStore())
        result = runner.run(task)
        _print_summary(result.score.summary())
        return 0 if result.score.completed else 1
    finally:
        harness.close()


def _print_summary(text: str) -> None:
    """Print the score summary, tolerating a console codepage (e.g. Windows'
    legacy cp1252) that can't encode every character an agent's own
    reasoning text might contain — a display limitation shouldn't crash an
    otherwise-successful run.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        print(text.encode(encoding, errors="replace").decode(encoding))


if __name__ == "__main__":
    raise SystemExit(main())
