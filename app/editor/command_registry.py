"""
Command registry — maps action-name strings to command classes.

The ``@command`` decorator registers a :class:`~app.editor.CommandBase`
subclass under a name that matches the ``action`` strings used in the
ribbon configuration::

    from app.editor import command
    from app.editor.base_command import CommandBase

    @command("lineCommand")
    class DrawLineCommand(CommandBase):
        def execute(self) -> None:
            ...

Registered commands can be looked up via :func:`get_command` and all
registered names via :func:`registered_commands`.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Type

from app.editor.base_command import CommandBase

# ---------------------------------------------------------------------------
# Internal registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, Type[CommandBase]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def command(name: str) -> Callable[[Type[CommandBase]], Type[CommandBase]]:
    """Class decorator that registers a command under *name*.

    Parameters
    ----------
    name:
        The action-name string (e.g. ``"lineCommand"``).  Must be unique;
        registering a second class under the same name overwrites the first.

    Example
    -------
    ::

        @command("lineCommand")
        class DrawLineCommand(CommandBase):
            def execute(self) -> None:
                ...
    """
    def _decorator(cls: Type[CommandBase]) -> Type[CommandBase]:
        cls.command_name = name
        _REGISTRY[name] = cls
        return cls

    return _decorator


def get_command(name: str) -> Optional[Type[CommandBase]]:
    """Return the command class registered under *name*, or ``None``."""
    return _REGISTRY.get(name)


def registered_commands() -> Dict[str, Type[CommandBase]]:
    """Return a shallow copy of the full registry dict."""
    return dict(_REGISTRY)
