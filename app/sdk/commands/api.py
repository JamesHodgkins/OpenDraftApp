"""Public registration API for SDK/plugin commands."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar

from app.editor.command_registry import register_sdk_command
from app.sdk.commands.spec import CommandSpec

if TYPE_CHECKING:
    from app.sdk.commands.context import CommandContext


class SupportsExecute(Protocol):
    """Protocol for class-based SDK commands."""

    def execute(self, ctx: "CommandContext") -> None:
        ...


SDKCommandImpl = Callable[["CommandContext"], None] | type[SupportsExecute]

T = TypeVar("T", bound=Any)


def register(spec: CommandSpec) -> Callable[[T], T]:
    """Register a class/function command with an explicit :class:`CommandSpec`."""

    def _decorator(impl: T) -> T:
        register_sdk_command(spec, impl)
        return impl

    return _decorator


def command(
    command_id: str,
    *,
    display_name: str | None = None,
    description: str = "",
    category: str = "General",
    aliases: tuple[str, ...] = (),
    icon: str | None = None,
    source: str = "plugin",
    min_api_version: str = "1.0",
) -> Callable[[T], T]:
    """Convenience decorator for SDK/plugin command registration."""
    spec = CommandSpec(
        id=command_id,
        display_name=display_name,
        description=description,
        category=category,
        aliases=aliases,
        icon=icon,
        source=source,
        min_api_version=min_api_version,
    )
    return register(spec)
