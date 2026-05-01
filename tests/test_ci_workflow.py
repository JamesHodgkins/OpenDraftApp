"""Guardrails for GitHub Actions CI workflow regressions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


WORKFLOW_FILE = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _step_by_name(steps: list[object], name: str) -> dict[str, Any] | None:
    for step in steps:
        if isinstance(step, dict) and step.get("name") == name:
            return step
    return None


def test_ci_workflow_is_valid_yaml_with_test_job() -> None:
    payload = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))

    assert isinstance(payload, dict)
    assert payload.get("name") == "CI"

    jobs = payload.get("jobs")
    assert isinstance(jobs, dict)

    test_job = jobs.get("test")
    assert isinstance(test_job, dict)

    steps = test_job.get("steps")
    assert isinstance(steps, list)
    assert steps


def test_ci_workflow_runs_pytest_and_pyright() -> None:
    payload = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    jobs = payload.get("jobs")
    assert isinstance(jobs, dict)

    test_job = jobs.get("test")
    assert isinstance(test_job, dict)

    steps = test_job.get("steps")
    assert isinstance(steps, list)

    test_step = _step_by_name(steps, "Run tests (headless)")
    assert isinstance(test_step, dict)

    test_command = str(test_step.get("run", ""))
    assert "pytest -ra -vv --maxfail=1" in test_command

    pyright_step = _step_by_name(steps, "Run Pyright type-check")
    assert isinstance(pyright_step, dict)

    pyright_command = str(pyright_step.get("run", ""))
    assert "pyright --outputjson > pyright-report.json || true" in pyright_command
