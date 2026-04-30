"""
app.editor — command-driven editor for OpenDraft.

Exported symbols
----------------
``Editor``              Central editor controller (QObject).
``EditorTransaction``   Public undo/notification transaction helper.
``CommandOptionSelection`` Typed command-option selection result.
``CommandBase``         Abstract base for all command classes.
``StatefulCommandBase`` Base for stateful commands with exported properties.
``export``              Descriptor factory for stateful command properties.
``CommandCancelled``    Exception raised when the user cancels a command.
``command``             ``@command("actionName")`` registration decorator.
``get_command``         Look up a registered command class by action name.
``registered_commands`` Return the full action-name → class registry dict.
``get_command_spec``    Look up command metadata for a command id/alias.
``registered_command_specs`` Return full command-id → metadata registry.
``command_catalog``     Snapshot of command-id → metadata registry.
``command_catalog_version`` Monotonic version for catalog changes.
``apply_command_specs`` Merge rich metadata specs into registered commands.
``autodiscover_entry_points`` Load plugin commands via Python entry points.
``unregister_command`` Remove a command by id/alias from the catalog.
``unregister_commands_by_source`` Remove commands by source label.
``refresh_command_catalog`` Rebuild plugin command catalog for picker refresh.
``validate_actions`` Validate actions against local handlers + command registry.
``validate_action_sources`` Validate multiple named action sources.
"""
from app.editor.base_command import CommandBase, CommandCancelled
from app.editor.stateful_command import StatefulCommandBase, export
from app.editor.command_registry import (
    ActionValidationReport,
    CommandCatalogRefreshResult,
    apply_command_specs,
    autodiscover_entry_points,
    command_catalog,
    command_catalog_version,
    command,
    get_command,
    get_command_spec,
    refresh_command_catalog,
    registered_commands,
    registered_command_specs,
    unregister_command,
    unregister_commands_by_source,
    validate_actions,
    validate_action_sources,
)
from app.editor.editor import CommandOptionSelection, Editor, EditorTransaction
from app.editor.osnap_engine import OsnapEngine, SnapResult, SnapType
from app.editor.selection import SelectionSet
from app.editor.undo import (
    AddEntityUndoCommand,
    AddLayerUndoCommand,
    CompositeUndoCommand,
    RemoveEntitiesUndoCommand,
    RemoveLayerUndoCommand,
    RenameLayerUndoCommand,
    SetActiveLayerUndoCommand,
    SetEntityPropertiesUndoCommand,
    SetLayerPropertyUndoCommand,
    UndoCommand,
    UndoStack,
)

__all__ = [
    "Editor",
    "EditorTransaction",
    "CommandOptionSelection",
    "CommandBase",
    "StatefulCommandBase",
    "export",
    "CommandCancelled",
    "OsnapEngine",
    "SnapResult",
    "SnapType",
    "SelectionSet",
    "UndoCommand",
    "UndoStack",
    "AddEntityUndoCommand",
    "AddLayerUndoCommand",
    "CompositeUndoCommand",
    "RemoveEntitiesUndoCommand",
    "RemoveLayerUndoCommand",
    "RenameLayerUndoCommand",
    "SetActiveLayerUndoCommand",
    "SetEntityPropertiesUndoCommand",
    "SetLayerPropertyUndoCommand",
    "command",
    "apply_command_specs",
    "autodiscover_entry_points",
    "command_catalog",
    "command_catalog_version",
    "refresh_command_catalog",
    "unregister_command",
    "unregister_commands_by_source",
    "ActionValidationReport",
    "CommandCatalogRefreshResult",
    "validate_actions",
    "validate_action_sources",
    "get_command",
    "get_command_spec",
    "registered_commands",
    "registered_command_specs",
]
