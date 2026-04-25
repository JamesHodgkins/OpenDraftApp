"""
Undo / redo infrastructure for OpenDraft.

Provides :class:`UndoCommand` (abstract base), concrete command classes for
common document mutations, and :class:`UndoStack` which manages the history.

Usage (from the :class:`Editor`)::

    stack = UndoStack()
    stack.push(AddEntityUndoCommand(document, entity))
    stack.undo()   # removes the entity
    stack.redo()   # adds it back

The stack emits a Qt signal ``state_changed`` whenever the undo/redo
availability changes so the UI can enable/disable buttons.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class UndoCommand:
    """Abstract base for an undoable action.

    Subclasses must implement :meth:`undo` and :meth:`redo`.
    :meth:`redo` is also called once when the command is first pushed onto
    the stack (unless ``execute_on_push=False`` is passed to
    :meth:`UndoStack.push`).
    """

    #: Short human-readable label shown in UI (e.g. "Draw Line").
    description: str = ""

    def redo(self) -> None:
        """(Re-)apply the action."""
        raise NotImplementedError

    def undo(self) -> None:
        """Reverse the action."""
        raise NotImplementedError

    def __repr__(self) -> str:          # noqa: D105
        return f"<{self.__class__.__name__} {self.description!r}>"


# ---------------------------------------------------------------------------
# Concrete commands
# ---------------------------------------------------------------------------

class AddEntityUndoCommand(UndoCommand):
    """Undoable addition of a single entity to the document.

    Parameters
    ----------
    document:
        The :class:`~app.document.DocumentStore` to mutate.
    entity:
        The entity to add / remove.
    """

    def __init__(self, document, entity) -> None:  # noqa: ANN001
        from app.document import DocumentStore
        from app.entities import BaseEntity

        self._doc: DocumentStore = document
        self._entity: BaseEntity = entity
        self.description = f"Add {entity.__class__.__name__}"

    def redo(self) -> None:
        self._doc.add_entity(self._entity)

    def undo(self) -> None:
        self._doc.remove_entity(self._entity.id)


class RemoveEntitiesUndoCommand(UndoCommand):
    """Undoable removal of one or more entities from the document.

    The entities are stored together with their original indices so that
    undo re-inserts them at the correct positions in the entity list.

    Parameters
    ----------
    document:
        The :class:`~app.document.DocumentStore` to mutate.
    entities:
        Entities that were (or will be) removed, **in their original order**
        within the document's entity list.
    indices:
        Parallel list with the index each entity occupied *before* removal.
    """

    def __init__(self, document, entities, indices) -> None:  # noqa: ANN001
        from app.document import DocumentStore
        from app.entities import BaseEntity

        self._doc: DocumentStore = document
        self._entities: List[BaseEntity] = list(entities)
        self._indices: List[int] = list(indices)
        n = len(self._entities)
        self.description = f"Delete {n} entit{'y' if n == 1 else 'ies'}"

    def redo(self) -> None:
        # Remove in reverse order so indices stay valid.
        for ent in reversed(self._entities):
            self._doc.remove_entity(ent.id)

    def undo(self) -> None:
        # Re-insert in forward order at the saved indices.
        for idx, ent in zip(self._indices, self._entities):
            pos = min(idx, len(self._doc.entities))
            self._doc.entities.insert(pos, ent)
            # Keep the O(1) id index consistent with the entities list.
            self._doc._entity_by_id[ent.id] = ent
        self._doc._notify()


class SetEntityPropertiesUndoCommand(UndoCommand):
    """Undoable bulk change of one or more attributes on multiple entities.

    Each affected entity/attribute pair is stored so undo can restore the
    exact previous value.

    Parameters
    ----------
    document:
        The :class:`~app.document.DocumentStore` that owns the entities.
    changes:
        A list of ``(entity_id, attr_name, old_value, new_value)`` tuples.
    description:
        Human-readable label (e.g. ``"Change colour"``).
    """

    def __init__(
        self,
        document,
        changes: List[Tuple[str, str, Any, Any]],
        description: str = "Change properties",
    ) -> None:
        from app.document import DocumentStore

        self._doc: DocumentStore = document
        self._changes = list(changes)
        self.description = description

    def redo(self) -> None:
        for eid, attr, _old, new in self._changes:
            ent = self._doc.get_entity(eid)
            if ent is not None:
                setattr(ent, attr, new)
        self._doc._notify()

    def undo(self) -> None:
        for eid, attr, old, _new in self._changes:
            ent = self._doc.get_entity(eid)
            if ent is not None:
                setattr(ent, attr, old)
        self._doc._notify()


class SetLayerPropertyUndoCommand(UndoCommand):
    """Undoable change of a single property on a layer.

    Parameters
    ----------
    document:
        The :class:`~app.document.DocumentStore` that owns the layer.
    layer_name:
        Name of the target layer (looked up at undo/redo time).
    attr:
        Attribute name on :class:`~app.document.Layer` (e.g. ``"color"``).
    old_value:
        Value before the change.
    new_value:
        Value after the change.
    """

    def __init__(self, document, layer_name: str, attr: str,
                 old_value: Any, new_value: Any,
                 description: str = "Change layer property") -> None:
        from app.document import DocumentStore

        self._doc: DocumentStore = document
        self._layer_name = layer_name
        self._attr = attr
        self._old = old_value
        self._new = new_value
        self.description = description

    def _get_layer(self):
        """Locate the layer (may have been renamed — fall back to scan)."""
        return self._doc.get_layer(self._layer_name)

    def redo(self) -> None:
        lyr = self._get_layer()
        if lyr is not None:
            setattr(lyr, self._attr, self._new)
        self._doc._notify()

    def undo(self) -> None:
        lyr = self._get_layer()
        if lyr is not None:
            setattr(lyr, self._attr, self._old)
        self._doc._notify()


class RenameLayerUndoCommand(UndoCommand):
    """Undoable layer rename.

    Also updates ``document.active_layer`` if the renamed layer was active.
    """

    def __init__(self, document, old_name: str, new_name: str) -> None:
        from app.document import DocumentStore

        self._doc: DocumentStore = document
        self._old_name = old_name
        self._new_name = new_name
        self.description = f"Rename layer '{old_name}' → '{new_name}'"

    def redo(self) -> None:
        lyr = self._doc.get_layer(self._old_name)
        if lyr is not None:
            lyr.name = self._new_name
        if self._doc.active_layer == self._old_name:
            self._doc.active_layer = self._new_name
        self._doc._notify()

    def undo(self) -> None:
        lyr = self._doc.get_layer(self._new_name)
        if lyr is not None:
            lyr.name = self._old_name
        if self._doc.active_layer == self._new_name:
            self._doc.active_layer = self._old_name
        self._doc._notify()


class AddLayerUndoCommand(UndoCommand):
    """Undoable addition of a layer."""

    def __init__(self, document, layer) -> None:
        from app.document import DocumentStore, Layer

        self._doc: DocumentStore = document
        self._layer: Layer = layer
        self.description = f"Add layer '{layer.name}'"

    def redo(self) -> None:
        self._doc.add_layer(self._layer)

    def undo(self) -> None:
        self._doc.remove_layer(self._layer.name)


class RemoveLayerUndoCommand(UndoCommand):
    """Undoable removal of a layer.

    Stores the layer object, its position in the list, the entities that
    were reassigned to ``"default"`` and the previous active layer so
    everything can be fully reversed.
    """

    def __init__(self, document, layer, index: int,
                 reassigned_entities: List[Tuple[str, str]],
                 was_active: bool) -> None:
        from app.document import DocumentStore, Layer

        self._doc: DocumentStore = document
        self._layer: Layer = layer
        self._index: int = index
        # List of (entity_id, old_layer_name) for entities reassigned to "default".
        self._reassigned = list(reassigned_entities)
        self._was_active = was_active
        self.description = f"Delete layer '{layer.name}'"

    def redo(self) -> None:
        # Reassign entities to "default".
        for eid, _old_layer in self._reassigned:
            ent = self._doc.get_entity(eid)
            if ent is not None:
                ent.layer = "default"
        self._doc.remove_layer(self._layer.name)
        if self._was_active:
            self._doc.active_layer = "default"
        self._doc._notify()

    def undo(self) -> None:
        # Re-insert the layer at its original position.
        pos = min(self._index, len(self._doc.layers))
        self._doc.layers.insert(pos, self._layer)
        # Restore entity layer assignments.
        for eid, old_layer in self._reassigned:
            ent = self._doc.get_entity(eid)
            if ent is not None:
                ent.layer = old_layer
        if self._was_active:
            self._doc.active_layer = self._layer.name
        self._doc._notify()


class SetActiveLayerUndoCommand(UndoCommand):
    """Undoable change of the document's active layer."""

    def __init__(self, document, old_name: str, new_name: str) -> None:
        from app.document import DocumentStore

        self._doc: DocumentStore = document
        self._old = old_name
        self._new = new_name
        self.description = f"Set active layer '{new_name}'"

    def redo(self) -> None:
        self._doc.active_layer = self._new
        self._doc._notify()

    def undo(self) -> None:
        self._doc.active_layer = self._old
        self._doc._notify()


class CompositeUndoCommand(UndoCommand):
    """Undo command that groups multiple child commands as one step."""

    def __init__(
        self,
        commands: List[UndoCommand],
        description: str = "Composite edit",
    ) -> None:
        self._commands = list(commands)
        self.description = description

    def redo(self) -> None:
        for cmd in self._commands:
            cmd.redo()

    def undo(self) -> None:
        for cmd in reversed(self._commands):
            cmd.undo()


# ---------------------------------------------------------------------------
# Undo stack
# ---------------------------------------------------------------------------

class UndoStack(QObject):
    """Linear undo / redo history.

    Signals
    -------
    state_changed()
        Emitted whenever the undo or redo availability changes (push / undo /
        redo / clear).  Connect to update toolbar button enabled-states.
    """

    state_changed = Signal()

    def __init__(self, parent: Optional[QObject] = None, limit: int = 500) -> None:
        super().__init__(parent)
        self._stack: List[UndoCommand] = []
        self._index: int = -1  # points at most-recently-executed command
        self._limit: int = limit

    # ----- public API -----

    def push(self, cmd: UndoCommand, *, execute_on_push: bool = False) -> None:
        """Push *cmd* onto the stack.

        If *execute_on_push* is ``True`` the command's :meth:`redo` is
        called immediately; otherwise it is assumed the caller already
        performed the action and the command merely records it for later
        reversal.

        Any commands above the current position (the "redo tail") are
        discarded, following the standard linear undo model.
        """
        # Discard the redo tail.
        del self._stack[self._index + 1:]

        self._stack.append(cmd)
        self._index = len(self._stack) - 1

        # Enforce the history limit.
        if len(self._stack) > self._limit:
            excess = len(self._stack) - self._limit
            del self._stack[:excess]
            self._index -= excess

        if execute_on_push:
            cmd.redo()

        self.state_changed.emit()

    def undo(self) -> bool:
        """Undo the last command.  Returns ``True`` on success."""
        if not self.can_undo:
            return False
        self._stack[self._index].undo()
        self._index -= 1
        self.state_changed.emit()
        return True

    def redo(self) -> bool:
        """Redo the next command.  Returns ``True`` on success."""
        if not self.can_redo:
            return False
        self._index += 1
        self._stack[self._index].redo()
        self.state_changed.emit()
        return True

    def clear(self) -> None:
        """Discard all history."""
        self._stack.clear()
        self._index = -1
        self.state_changed.emit()

    # ----- queries -----

    @property
    def can_undo(self) -> bool:
        return self._index >= 0

    @property
    def can_redo(self) -> bool:
        return self._index < len(self._stack) - 1

    @property
    def undo_text(self) -> str:
        """Description of the command that would be undone, or ``""``."""
        if self.can_undo:
            return self._stack[self._index].description
        return ""

    @property
    def redo_text(self) -> str:
        """Description of the command that would be redone, or ``""``."""
        if self.can_redo:
            return self._stack[self._index + 1].description
        return ""

    @property
    def count(self) -> int:
        """Total number of commands on the stack (including undone ones)."""
        return len(self._stack)

    def __repr__(self) -> str:          # noqa: D105
        return (
            f"<UndoStack commands={len(self._stack)} "
            f"index={self._index} "
            f"can_undo={self.can_undo} can_redo={self.can_redo}>"
        )
