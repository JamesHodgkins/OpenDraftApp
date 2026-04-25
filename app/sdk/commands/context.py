"""Stable command context wrapper exposed to SDK commands."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from app.entities import BaseEntity, Vec2

if TYPE_CHECKING:
    from app.document import DocumentStore
    from app.editor.editor import CommandOptionSelection, Editor, EditorTransaction
    from app.editor.selection import SelectionSet
    from app.editor.settings import EditorSettings
    from app.editor.undo import UndoCommand


class CommandContext:
    """Stable command-facing API that wraps the internal Editor.

    SDK and plugin commands should target this context instead of reaching
    into private editor/document internals.
    """

    def __init__(self, editor: "Editor") -> None:
        self._editor = editor

    # ------------------------------------------------------------------
    # State / core handles
    # ------------------------------------------------------------------

    @property
    def document(self) -> "DocumentStore":
        return self._editor.document

    @property
    def selection(self) -> "SelectionSet":
        return self._editor.selection

    @property
    def settings(self) -> "EditorSettings":
        return self._editor.settings

    @property
    def is_running(self) -> bool:
        return self._editor.is_running

    @property
    def input_mode(self) -> str:
        return self._editor.input_mode

    @property
    def last_command_name(self) -> str | None:
        return self._editor.last_command_name

    # ------------------------------------------------------------------
    # Prompt / status
    # ------------------------------------------------------------------

    def status(self, message: str) -> None:
        self._editor.status_message.emit(message)

    # ------------------------------------------------------------------
    # Input methods
    # ------------------------------------------------------------------

    def get_point(self, prompt: str = "Select a point") -> Vec2:
        return self._editor.get_point(prompt)

    def get_integer(self, prompt: str = "Enter an integer") -> int:
        return self._editor.get_integer(prompt)

    def get_float(self, prompt: str = "Enter a value") -> float:
        return self._editor.get_float(prompt)

    def get_length(self, prompt: str = "Enter length", base: Vec2 | None = None) -> float:
        return self._editor.get_length(prompt, base)

    def get_angle(
        self,
        prompt: str = "Enter angle (degrees)",
        center: Vec2 | None = None,
        *,
        allow_command_options: bool = False,
    ) -> float | "CommandOptionSelection":
        return self._editor.get_angle(
            prompt,
            center,
            allow_command_options=allow_command_options,
        )

    def get_string(self, prompt: str = "Enter text") -> str:
        return self._editor.get_string(prompt)

    def get_choice(self, prompt: str, options: list[str]) -> str:
        return self._editor.get_choice(prompt, options)

    def get_command_option(self, prompt: str, options: list[str]) -> str:
        return self._editor.get_command_option(prompt, options)

    def parse_command_option(self, value: Any) -> str | None:
        return self._editor.parse_command_option(value)

    # ------------------------------------------------------------------
    # Dynamic preview / highlights
    # ------------------------------------------------------------------

    def set_dynamic(self, fn: Callable[[Vec2], list[BaseEntity]]) -> None:
        self._editor.set_dynamic(fn)

    def clear_dynamic(self) -> None:
        self._editor.clear_dynamic()

    def preview(self, fn: Callable[[Vec2], list[BaseEntity]]) -> Any:
        """Return a context manager that scopes dynamic preview lifecycle."""
        return self._editor.preview(fn)

    def set_highlight(self, entities: list[BaseEntity]) -> None:
        self._editor.set_highlight(entities)

    def clear_highlight(self) -> None:
        self._editor.clear_highlight()

    def highlighted(self, entities: list[BaseEntity]) -> Any:
        """Return a context manager that scopes highlight lifecycle."""
        return self._editor.highlighted(entities)

    # ------------------------------------------------------------------
    # Context menu command options
    # ------------------------------------------------------------------

    @property
    def command_options(self) -> list[str]:
        return self._editor.command_option_labels

    def set_command_options(self, options: list[str]) -> None:
        self._editor.set_command_options(options)

    def clear_command_options(self) -> None:
        self._editor.clear_command_options()

    # ------------------------------------------------------------------
    # Snap / input behavior toggles
    # ------------------------------------------------------------------

    @property
    def snap_from_point(self) -> Vec2 | None:
        return self._editor.snap_from_point

    @snap_from_point.setter
    def snap_from_point(self, value: Vec2 | None) -> None:
        self._editor.snap_from_point = value

    @property
    def suppress_osnap(self) -> bool:
        return self._editor.suppress_osnap

    @suppress_osnap.setter
    def suppress_osnap(self, value: bool) -> None:
        self._editor.suppress_osnap = bool(value)

    @property
    def suppress_dynamic_input(self) -> bool:
        return self._editor.suppress_dynamic_input

    @suppress_dynamic_input.setter
    def suppress_dynamic_input(self, value: bool) -> None:
        self._editor.suppress_dynamic_input = bool(value)

    # ------------------------------------------------------------------
    # Document mutations
    # ------------------------------------------------------------------

    def add_entity(self, entity: BaseEntity) -> BaseEntity:
        return self._editor.add_entity(entity)

    def remove_entity(self, entity_id: str) -> BaseEntity | None:
        return self._editor.remove_entity(entity_id)

    def delete_selection(self) -> list[BaseEntity]:
        return self._editor.delete_selection()

    def set_entity_properties(
        self,
        entity_ids: list[str],
        attr: str,
        new_value: Any,
        *,
        description: str = "Change properties",
    ) -> None:
        self._editor.set_entity_properties(
            entity_ids,
            attr,
            new_value,
            description=description,
        )

    def set_layer_property(
        self,
        layer_name: str,
        attr: str,
        new_value: Any,
        *,
        description: str = "Change layer property",
    ) -> None:
        self._editor.set_layer_property(
            layer_name,
            attr,
            new_value,
            description=description,
        )

    # ------------------------------------------------------------------
    # Undo / command orchestration
    # ------------------------------------------------------------------

    def undo(self) -> bool:
        return self._editor.undo()

    def redo(self) -> bool:
        return self._editor.redo()

    def push_undo(self, command: "UndoCommand") -> None:
        self._editor.push_undo_command(command)

    def transaction(self, description: str = "Command change") -> "EditorTransaction":
        return self._editor.transaction(description=description)

    def notify_document(self) -> None:
        self._editor.notify_document()

    def run_command(self, command_id: str) -> None:
        self._editor.run_command(command_id)

    def cancel(self) -> None:
        self._editor.cancel()
