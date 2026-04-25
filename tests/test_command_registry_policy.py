"""Tests for command ID namespacing and collision policy."""
from __future__ import annotations

import pytest

from app.editor.base_command import CommandBase
from app.editor.command_registry import command, get_command, get_command_spec
from app.sdk.commands import CommandContext, command as sdk_command


def test_core_legacy_id_is_exposed_via_namespaced_id_and_alias() -> None:
    legacy_id = "policyLegacyCommand"
    canonical_id = "core.policy_legacy"

    @command(legacy_id)
    class _PolicyLegacy(CommandBase):
        def execute(self) -> None:
            return None

    cmd_from_legacy = get_command(legacy_id)
    cmd_from_namespaced = get_command(canonical_id)

    assert cmd_from_legacy is not None
    assert cmd_from_namespaced is cmd_from_legacy

    spec = get_command_spec(legacy_id)
    assert spec is not None
    assert spec.id == canonical_id
    assert legacy_id in spec.aliases


def test_non_core_non_namespaced_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be namespaced"):

        @sdk_command("badPluginCommand", source="tests")
        def _bad_plugin_command(_ctx: CommandContext) -> None:
            return None


def test_duplicate_command_id_registration_fails_fast() -> None:
    command_id = "tests.policy_duplicate_command"

    @command(command_id, source="tests")
    class _PolicyDuplicateOne(CommandBase):
        def execute(self) -> None:
            return None

    with pytest.raises(ValueError, match="Command id collision"):

        @command(command_id, source="tests")
        class _PolicyDuplicateTwo(CommandBase):
            def execute(self) -> None:
                return None


def test_alias_collision_fails_fast() -> None:
    shared_alias = "tests.shared_policy_alias"

    @command("tests.policy_alias_owner", source="tests", aliases=(shared_alias,))
    class _PolicyAliasOwner(CommandBase):
        def execute(self) -> None:
            return None

    with pytest.raises(ValueError, match="Alias collision"):

        @command("tests.policy_alias_other", source="tests", aliases=(shared_alias,))
        class _PolicyAliasOther(CommandBase):
            def execute(self) -> None:
                return None
