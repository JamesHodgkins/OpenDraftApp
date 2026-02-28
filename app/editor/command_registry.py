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

Use :func:`autodiscover` instead of an explicit ``import app.commands``
side-effect import so the discovery intent is clear and linter tools
cannot silently remove it::

    from app.editor.command_registry import autodiscover
    autodiscover("app.commands")
"""
from __future__ import annotations

import importlib
import pkgutil
import warnings
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


def autodiscover(package: str) -> None:
    """Import every module in *package* so their ``@command`` decorators fire.

    This is the preferred alternative to a bare ``import app.commands``
    side-effect import which linters may silently remove.

    Parameters
    ----------
    package:
        Dotted Python package name, e.g. ``"app.commands"``.

    Example
    -------
    ::

        from app.editor.command_registry import autodiscover
        autodiscover("app.commands")
    """
    pkg = importlib.import_module(package)
    pkg_path = getattr(pkg, "__path__", [])
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        path=pkg_path,
        prefix=package + ".",
        onerror=lambda name: None,
    ):
        try:
            importlib.import_module(modname)
        except Exception as exc:
            warnings.warn(
                f"autodiscover: failed to import {modname!r}: {exc}",
                stacklevel=2,
            )
