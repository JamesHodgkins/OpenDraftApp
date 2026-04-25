"""Tests for core command metadata enrichment."""
from __future__ import annotations

from app.config.ribbon_config import command_specs_from_ribbon
from app.editor.command_registry import (
    apply_command_specs,
    autodiscover,
    get_command,
    get_command_spec,
)


def test_command_specs_from_ribbon_extracts_rich_fields() -> None:
    specs = command_specs_from_ribbon()

    line = specs["lineCommand"]
    assert line.id == "lineCommand"
    assert line.display_name == "Line"
    assert line.category == "Draw"
    assert line.icon == "draw_line"
    assert line.source == "core"
    assert line.min_api_version == "1.0"

    rotate = specs["rotateCommand"]
    assert rotate.display_name == "Rotate"
    assert rotate.category == "Modify"
    assert rotate.icon == "mod_rotate"


def test_apply_command_specs_enriches_registered_core_commands() -> None:
    autodiscover("app.commands")
    apply_command_specs(command_specs_from_ribbon())

    line_spec = get_command_spec("lineCommand")
    assert line_spec is not None
    assert line_spec.display_name == "Line"
    assert line_spec.category == "Draw"
    assert line_spec.icon == "draw_line"
    assert line_spec.source == "core"
    assert line_spec.min_api_version == "1.0"
    assert line_spec.description

    rotate_spec = get_command_spec("rotateCommand")
    assert rotate_spec is not None
    assert rotate_spec.display_name == "Rotate"
    assert rotate_spec.category == "Modify"
    assert rotate_spec.icon == "mod_rotate"

    # Non-command ribbon actions should not be added by default.
    assert get_command("undo") is None
    assert get_command_spec("undo") is None
