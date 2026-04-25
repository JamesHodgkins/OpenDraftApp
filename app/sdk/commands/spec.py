"""Command metadata model for the public SDK."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Public command metadata used by built-ins and plugins.

    Parameters
    ----------
    id:
        Unique command identifier (for example ``"core.line"``).
    display_name:
        User-facing label shown in command pickers. Optional.
    description:
        Short help text.
    category:
        Logical grouping used by UIs.
    aliases:
        Alternate IDs that resolve to this command.
    icon:
        Optional icon name/path for command UIs.
    source:
        Origin label (for example ``"core"`` or plugin package name).
    min_api_version:
        Minimum command SDK API version the command expects.
    """

    id: str
    display_name: str | None = None
    description: str = ""
    category: str = "General"
    aliases: tuple[str, ...] = ()
    icon: str | None = None
    source: str = "core"
    min_api_version: str = "1.0"
