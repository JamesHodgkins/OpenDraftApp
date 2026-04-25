"""Tests for plugin command discovery via Python entry points."""
from __future__ import annotations

import app.editor.command_registry as registry
from app.editor.command_registry import get_command
from app.sdk.commands import CommandContext, command as sdk_command


class _FakeEntryPoint:
    def __init__(self, name: str, loader):
        self.name = name
        self._loader = loader

    def load(self):
        return self._loader()


def test_autodiscover_entry_points_loads_callable_plugin(monkeypatch) -> None:
    called: list[str] = []

    def _bootstrap() -> None:
        called.append("bootstrap")

        @sdk_command("tests.entrypoint_discovery_command", source="tests")
        def _plugin_cmd(_ctx: CommandContext) -> None:
            return None

    ep = _FakeEntryPoint("demo_plugin", loader=lambda: _bootstrap)

    def _fake_entry_points(*, group: str):
        assert group == "opendraft.commands"
        return [ep]

    monkeypatch.setattr(registry.importlib_metadata, "entry_points", _fake_entry_points)

    loaded = registry.autodiscover_entry_points("opendraft.commands")
    assert loaded == ["demo_plugin"]
    assert called == ["bootstrap"]
    assert get_command("tests.entrypoint_discovery_command") is not None


def test_autodiscover_entry_points_continues_after_plugin_failure(monkeypatch) -> None:
    def _bad_loader():
        raise RuntimeError("boom")

    def _good_bootstrap() -> None:
        @sdk_command("tests.entrypoint_survivor_command", source="tests")
        def _plugin_cmd(_ctx: CommandContext) -> None:
            return None

    eps = [
        _FakeEntryPoint("bad_plugin", loader=lambda: _bad_loader()),
        _FakeEntryPoint("good_plugin", loader=lambda: _good_bootstrap),
    ]

    def _fake_entry_points(*, group: str):
        assert group == "opendraft.commands"
        return eps

    monkeypatch.setattr(registry.importlib_metadata, "entry_points", _fake_entry_points)

    loaded = registry.autodiscover_entry_points("opendraft.commands")
    assert loaded == ["good_plugin"]
    assert get_command("tests.entrypoint_survivor_command") is not None
