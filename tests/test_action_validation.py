"""Tests for startup action resolution and validation helpers."""
from __future__ import annotations

from app.config.ribbon_config import ribbon_action_names
from app.editor.base_command import CommandBase
from app.editor.command_registry import command, validate_action_sources, validate_actions


def test_validate_actions_classifies_local_command_and_unresolved() -> None:
    @command("tests.validate_actions_command", source="tests")
    class _ValidateActionsCommand(CommandBase):
        def execute(self) -> None:
            return None

    report = validate_actions(
        ["toggleLayerModal", "tests.validate_actions_command", "missing.action"],
        local_actions=["toggleLayerModal"],
    )

    assert report.local_actions == ("toggleLayerModal",)
    assert report.command_actions == ("tests.validate_actions_command",)
    assert report.unresolved_actions == ("missing.action",)


def test_validate_action_sources_reports_each_source() -> None:
    @command("tests.validate_action_sources_command", source="tests")
    class _ValidateActionSourcesCommand(CommandBase):
        def execute(self) -> None:
            return None

    reports = validate_action_sources(
        {
            "ribbon": {"tests.validate_action_sources_command", "unknown.ribbon"},
            "palette": {"toggleLayerModal", "unknown.palette"},
        },
        local_actions={"toggleLayerModal"},
    )

    assert reports["ribbon"].command_actions == ("tests.validate_action_sources_command",)
    assert reports["ribbon"].unresolved_actions == ("unknown.ribbon",)
    assert reports["palette"].local_actions == ("toggleLayerModal",)
    assert reports["palette"].unresolved_actions == ("unknown.palette",)


def test_ribbon_action_names_extracts_split_and_stack_actions() -> None:
    panel_defs = {
        "Demo": {
            "tools": [
                {
                    "label": "Split",
                    "type": "split",
                    "mainAction": "demo.main",
                    "items": [{"label": "Item", "action": "demo.item"}],
                },
                {
                    "type": "stack",
                    "columns": [[{"label": "Stack", "type": "small", "action": "demo.stack"}]],
                },
                {"label": "Plain", "type": "large", "action": "demo.plain"},
            ]
        }
    }

    actions = ribbon_action_names(panel_defs)
    assert actions == {"demo.main", "demo.item", "demo.stack", "demo.plain"}
