"""
app.editor — command-driven editor for OpenDraft.

Exported symbols
----------------
``Editor``              Central editor controller (QObject).
``CommandBase``         Abstract base for all command classes.
``CommandCancelled``    Exception raised when the user cancels a command.
``command``             ``@command("actionName")`` registration decorator.
``get_command``         Look up a registered command class by action name.
``registered_commands`` Return the full action-name → class registry dict.
"""
from app.editor.base_command import CommandBase, CommandCancelled
from app.editor.command_registry import command, get_command, registered_commands
from app.editor.editor import Editor
from app.editor.osnap_engine import OsnapEngine, SnapResult, SnapType
from app.editor.selection import SelectionSet

__all__ = [
    "Editor",
    "CommandBase",
    "CommandCancelled",
    "OsnapEngine",
    "SnapResult",
    "SnapType",
    "SelectionSet",
    "command",
    "get_command",
    "registered_commands",
]
