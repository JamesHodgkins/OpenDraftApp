"""Tests for refreshable command catalog APIs."""
from __future__ import annotations

import app.editor.command_registry as registry
from app.editor.base_command import CommandBase
from app.editor.command_registry import (
    command,
    command_catalog,
    command_catalog_version,
    get_command,
    get_command_spec,
    refresh_command_catalog,
    unregister_commands_by_source,
)
from app.sdk.commands import CommandContext, command as sdk_command


class _FakeEntryPoint:
    def __init__(self, name: str, loader):
        self.name = name
        self._loader = loader

    def load(self):
        return self._loader()


def test_command_catalog_snapshot_is_copy_and_version_increments() -> None:
    start_version = command_catalog_version()

    @command("tests.catalog_copy_command", source="tests")
    class _CatalogCopyCommand(CommandBase):
        def execute(self) -> None:
            return None

    snapshot = command_catalog()
    assert "tests.catalog_copy_command" in snapshot
    snapshot.pop("tests.catalog_copy_command")

    # Removing from the snapshot must not mutate the live registry.
    assert get_command_spec("tests.catalog_copy_command") is not None
    assert command_catalog_version() > start_version


def test_unregister_commands_by_source_removes_aliases() -> None:
    alias = "tests.catalog_alias"

    @command(
        "tests.catalog_source_command",
        source="tests",
        aliases=(alias,),
    )
    class _CatalogSourceCommand(CommandBase):
        def execute(self) -> None:
            return None

    assert get_command("tests.catalog_source_command") is not None
    assert get_command(alias) is not None

    removed = unregister_commands_by_source({"tests"})
    assert "tests.catalog_source_command" in removed
    assert get_command("tests.catalog_source_command") is None
    assert get_command(alias) is None


def test_refresh_command_catalog_reloads_plugins(monkeypatch) -> None:
    @sdk_command("tests.catalog_stale_plugin_command", source="tests")
    def _stale_plugin_cmd(_ctx: CommandContext) -> None:
        return None

    def _bootstrap() -> None:
        @sdk_command("tests.catalog_fresh_plugin_command", source="tests")
        def _fresh_plugin_cmd(_ctx: CommandContext) -> None:
            return None

    ep = _FakeEntryPoint("catalog_plugin", loader=lambda: _bootstrap)

    def _fake_entry_points(*, group: str):
        assert group == "opendraft.commands"
        return [ep]

    monkeypatch.setattr(registry.importlib_metadata, "entry_points", _fake_entry_points)

    before_version = command_catalog_version()
    report = refresh_command_catalog(
        plugin_entry_point_group="opendraft.commands",
        reload_plugins=True,
        remove_non_core=True,
    )

    assert "tests.catalog_stale_plugin_command" in report.removed_command_ids
    assert report.loaded_entry_points == ("catalog_plugin",)
    assert get_command("tests.catalog_stale_plugin_command") is None
    assert get_command("tests.catalog_fresh_plugin_command") is not None
    assert report.command_count == len(command_catalog())
    assert report.catalog_version >= before_version
