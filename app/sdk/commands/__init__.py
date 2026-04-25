"""Public command SDK for core and third-party command authors."""
from app.sdk.commands.context import CommandContext
from app.sdk.commands.spec import CommandSpec


def register(spec: CommandSpec):
    """Lazy proxy to :func:`app.sdk.commands.api.register`."""
    from app.sdk.commands.api import register as _register

    return _register(spec)


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
):
    """Lazy proxy to :func:`app.sdk.commands.api.command`."""
    from app.sdk.commands.api import command as _command

    return _command(
        command_id,
        display_name=display_name,
        description=description,
        category=category,
        aliases=aliases,
        icon=icon,
        source=source,
        min_api_version=min_api_version,
    )


__all__ = [
    "CommandContext",
    "CommandSpec",
    "command",
    "register",
]
