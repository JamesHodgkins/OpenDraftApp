"""
Editor — the central controller that runs commands and owns the document.

Architecture
------------
Commands run in a **dedicated worker thread** so they can block on user
input (``get_point``, ``get_integer``, …) without freezing the UI.

The handshake between the UI thread and a blocking command thread is
handled by a single :class:`queue.Queue`.  When a command calls
``get_point()``:

1. The editor emits ``input_mode_changed("point")`` and
   ``status_message("…")`` so the canvas and status bar update.
2. The command thread blocks on ``_input_queue.get()``.
3. The canvas (connected via ``provide_point``) puts a :class:`Vec2`
   into the queue when the user left-clicks.
4. ``get_point()`` returns the value to the command.

Pressing **Escape** calls :meth:`cancel`, which puts a sentinel value
into the queue and sets an internal event; the next ``_wait_for_input``
call raises :class:`CommandCancelled`, which propagates cleanly back to
the editor's thread runner without any special handling in the command.

Signals (all safe to connect to UI slots — Qt is thread-safe for signal
emission from non-GUI threads)
---------------------------------
``status_message(str)``        — prompt text for the status bar.
``input_mode_changed(str)``    — ``"point" | "integer" | "string" | "none"``.
``command_started(str)``       — action name of the newly running command.
``command_finished()``         — command ended (normal or cancelled).
``entity_added(object)``       — a :class:`BaseEntity` was added to the doc.
``entity_removed(str)``        — entity with this id was removed from the doc.
``document_changed()``         — generic "something changed" for canvas redraws.
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable, List, Optional

from PySide6.QtCore import QObject, Signal

from app.document import DocumentStore
from app.entities import BaseEntity, Vec2
from app.editor.base_command import CommandBase, CommandCancelled
from app.editor.command_registry import get_command
from app.editor.selection import SelectionSet
from app.editor.undo import (
    AddEntityUndoCommand,
    AddLayerUndoCommand,
    RemoveEntitiesUndoCommand,
    RemoveLayerUndoCommand,
    RenameLayerUndoCommand,
    SetActiveLayerUndoCommand,
    SetEntityPropertiesUndoCommand,
    SetLayerPropertyUndoCommand,
    UndoStack,
)


# Sentinel placed in the queue by cancel() to unblock a waiting command.
_SENTINEL = object()


class Editor(QObject):
    """Central editor controller.

    Parameters
    ----------
    document:
        The :class:`DocumentStore` this editor operates on.  If omitted a
        fresh empty document is created automatically.
    """

    # ------------------------------------------------------------------ signals
    status_message    = Signal(str)    # prompt / info text → status bar
    input_mode_changed = Signal(str)   # "point" | "integer" | "string" | "none"
    command_started   = Signal(str)    # command action-name
    command_finished  = Signal()       # command ended
    entity_added      = Signal(object) # BaseEntity instance
    entity_removed    = Signal(str)    # entity id
    document_changed  = Signal()       # generic redraw trigger
    undo_state_changed = Signal()      # undo/redo availability changed

    def __init__(
        self,
        document: Optional[DocumentStore] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._document: DocumentStore = document if document is not None else DocumentStore()
        self._thread: Optional[threading.Thread] = None
        self._input_queue: queue.Queue[Any] = queue.Queue(maxsize=1)
        self._cancelled = threading.Event()
        self._active_command: Optional[CommandBase] = None
        self._input_mode: str = "none"
        self._dynamic_callback: Optional[Callable[[Vec2], List[BaseEntity]]] = None
        # Set by commands before calling get_point() so the OSNAP engine can
        # compute perpendicular snaps relative to the previously selected point.
        self.snap_from_point: Optional[Vec2] = None

        # Selection set — tracks currently selected entity IDs.
        self.selection = SelectionSet(parent=self)

        # Undo / redo history.
        self._undo_stack = UndoStack(parent=self)
        self._undo_stack.state_changed.connect(self.undo_state_changed.emit)

        # Wire DocumentStore change notifications → document_changed signal so
        # any direct mutation of the document (e.g. from LayerManagerDialog)
        # propagates to UI without additional manual wiring.  The signal is
        # emitted on whatever thread performs the mutation; the canvas must
        # connect with Qt.QueuedConnection for thread safety.
        self._document.add_change_listener(self.document_changed.emit)

    # ---------------------------------------------------------------- properties

    @property
    def document(self) -> DocumentStore:
        """The document this editor is operating on."""
        return self._document

    @property
    def active_command(self) -> Optional[CommandBase]:
        """The currently running command, or ``None``."""
        return self._active_command

    @property
    def is_running(self) -> bool:
        """``True`` while a command thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    # --------------------------------------------------------------- command API

    def run_command(self, name: str) -> None:
        """Start the command registered under *name* in a worker thread.

        If another command is already running it is cancelled first.

        Parameters
        ----------
        name:
            Action-name string matching the ``@command("…")`` decorator,
            e.g. ``"lineCommand"``.
        """
        # Cancel any running command and wait for it to finish.
        if self.is_running:
            self.cancel()
            if self._thread:
                self._thread.join(timeout=2.0)
                if self._thread.is_alive():
                    import warnings
                    warnings.warn(
                        f"Command thread '{self._thread.name}' did not terminate "
                        "within 2 s after cancel — starting new command anyway.  "
                        "Check that all get_point/get_integer paths honour cancellation.",
                        RuntimeWarning,
                        stacklevel=2,
                    )

        cls = get_command(name)
        if cls is None:
            self.status_message.emit(f"Unknown command: {name}")
            return

        self._cancelled.clear()
        self._drain_queue()

        cmd = cls(self)
        self._active_command = cmd
        self._thread = threading.Thread(
            target=self._run_in_thread,
            args=(cmd, name),
            daemon=True,
            name=f"cmd-{name}",
        )
        self._thread.start()

    def cancel(self) -> None:
        """Cancel the currently running command (equivalent to pressing Escape).

        Safe to call from any thread.
        """
        if not self.is_running:
            return
        self._cancelled.set()
        # Unblock any queued ``_wait_for_input`` call.
        try:
            self._input_queue.put_nowait(_SENTINEL)
        except queue.Full:
            # A value is already in the queue; swap it for the sentinel so the
            # waiting call sees it immediately.
            try:
                self._input_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._input_queue.put_nowait(_SENTINEL)
            except queue.Full:
                pass

    # ---------------------------------------------------------- input providers
    # Called by the UI (canvas mouse clicks, dialog boxes, etc.)

    def provide_point(self, pt: Vec2) -> None:
        """Deliver a world-space point to the currently waiting command.

        Connect the canvas ``pointSelected`` signal here.
        """
        if self._input_mode != "point":
            return
        self._put_input(pt)

    def provide_integer(self, value: int) -> None:
        """Deliver an integer value to the currently waiting command."""
        if self._input_mode != "integer":
            return
        self._put_input(value)

    def provide_string(self, value: str) -> None:
        """Deliver a string value to the currently waiting command."""
        if self._input_mode != "string":
            return
        self._put_input(value)

    def provide_float(self, value: float) -> None:
        """Deliver a float value to the currently waiting command."""
        if self._input_mode != "float":
            return
        self._put_input(value)

    # ------------------------------------------------------- blocking input API
    # Called *from the command thread only*.

    def get_point(self, prompt: str = "Select a point") -> Vec2:
        """Block the command thread until the user clicks a point on the canvas.

        Raises :class:`~app.editor.base_command.CommandCancelled` if Escape
        is pressed before a point is provided.

        Parameters
        ----------
        prompt:
            Message displayed in the status bar while waiting.

        Returns
        -------
        Vec2
            The world-space point the user clicked.
        """
        self.status_message.emit(prompt)
        self._set_input_mode("point")
        return self._wait_for_input()

    def get_integer(self, prompt: str = "Enter an integer") -> int:
        """Block the command thread until an integer is provided.

        Raises :class:`~app.editor.base_command.CommandCancelled` if cancelled.
        """
        self.status_message.emit(prompt)
        self._set_input_mode("integer")
        return self._wait_for_input()

    def get_float(self, prompt: str = "Enter a value") -> float:
        """Block the command thread until a float is provided.

        Raises :class:`~app.editor.base_command.CommandCancelled` if cancelled.
        """
        self.status_message.emit(prompt)
        self._set_input_mode("float")
        return self._wait_for_input()

    def get_string(self, prompt: str = "Enter text") -> str:
        """Block the command thread until a string is provided.

        Raises :class:`~app.editor.base_command.CommandCancelled` if cancelled.
        """
        self.status_message.emit(prompt)
        self._set_input_mode("string")
        return self._wait_for_input()

    # -------------------------------------------- dynamic / rubberband preview
    # Called from the command thread; get_dynamic() called from the GUI thread.

    def set_dynamic(
        self,
        fn: Callable[[Vec2], List[BaseEntity]],
    ) -> None:
        """Register a callback that returns temporary preview entities.

        *fn* receives the current world-space mouse position and should return
        a list of entities to draw as a rubberband preview.  The callback is
        invoked on the GUI thread (via ``get_dynamic``) so it must be
        thread-safe (only capture immutable data or copies).
        """
        self._dynamic_callback = fn

    def clear_dynamic(self) -> None:
        """Remove the active preview callback and refresh the canvas."""
        self._dynamic_callback = None
        self.document_changed.emit()

    def get_dynamic(self, mouse: Vec2) -> List[BaseEntity]:
        """Return preview entities for *mouse* (call from GUI thread only)."""
        fn = self._dynamic_callback
        if fn is None:
            return []
        try:
            return fn(mouse) or []
        except Exception:
            return []

    # ---------------------------------------------------------- document writes
    # Convenience wrappers so commands don't need to import DocumentStore.

    def add_entity(self, entity: BaseEntity) -> BaseEntity:
        """Add *entity* to the document and emit :attr:`entity_added`.

        The entity's ``layer`` attribute is stamped with the document's
        current ``active_layer`` before insertion so all newly drawn objects
        land on the correct layer automatically.

        Any active property overrides (colour, line style, weight) stored on
        the document are also applied to the new entity so that "ByLayer"
        objects inherit the pending style described in the Properties panel.

        The addition is recorded on the undo stack so it can be reversed
        with :meth:`undo`.

        Returns the entity (for chaining).
        """
        doc = self._document
        entity.layer = doc.active_layer
        # Apply active overrides — None means "ByLayer" so only stamp when set.
        if doc.active_color is not None:
            entity.color = doc.active_color
        if doc.active_line_style is not None:
            entity.line_style = doc.active_line_style
        if doc.active_thickness is not None:
            entity.line_weight = doc.active_thickness
        doc.add_entity(entity)
        self.entity_added.emit(entity)
        self.document_changed.emit()

        # Record on the undo stack (entity is already in the document).
        self._undo_stack.push(AddEntityUndoCommand(doc, entity))

        return entity

    def remove_entity(self, entity_id: str) -> Optional[BaseEntity]:
        """Remove the entity with *entity_id* from the document.

        Returns the removed entity, or ``None`` if it was not found.
        """
        removed = self._document.remove_entity(entity_id)
        if removed is not None:
            self.entity_removed.emit(entity_id)
            self.document_changed.emit()
        return removed

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def delete_selection(self) -> list[BaseEntity]:
        """Remove all currently selected entities from the document.

        The selection set is cleared regardless of whether the entities
        actually existed in the document.  The removal is recorded on the
        undo stack as a single :class:`RemoveEntitiesUndoCommand` so the
        whole deletion can be reversed with one ``Ctrl+Z``.

        Returns a list of the removed entity objects (preserving the order
        in the selection set at the time of deletion).
        """
        doc = self._document
        removed_entities: list[BaseEntity] = []
        removed_indices: list[int] = []

        # Collect entities and their indices *before* any removal.
        for eid in list(self.selection.ids):
            for i, ent in enumerate(doc.entities):
                if ent.id == eid:
                    removed_entities.append(ent)
                    removed_indices.append(i)
                    break

        # Now remove them through the normal path (emits signals).
        for ent in removed_entities:
            self.remove_entity(ent.id)

        # Record a single undo command for the entire batch.
        if removed_entities:
            self._undo_stack.push(
                RemoveEntitiesUndoCommand(doc, removed_entities, removed_indices)
            )

        # clear selection regardless of success so user isn't left with stale
        # IDs that no longer exist.
        self.selection.clear()
        return removed_entities

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    @property
    def undo_stack(self) -> UndoStack:
        """The editor's undo/redo history stack."""
        return self._undo_stack

    def undo(self) -> bool:
        """Undo the last recorded action.

        Returns ``True`` if an action was undone.
        """
        ok = self._undo_stack.undo()
        if ok:
            self.document_changed.emit()
        return ok

    def redo(self) -> bool:
        """Redo the previously undone action.

        Returns ``True`` if an action was redone.
        """
        ok = self._undo_stack.redo()
        if ok:
            self.document_changed.emit()
        return ok

    # ------------------------------------------------------------------
    # Undoable property helpers (called from UI code)
    # ------------------------------------------------------------------

    def set_entity_properties(
        self,
        entity_ids: list[str],
        attr: str,
        new_value,
        *,
        description: str = "Change properties",
    ) -> None:
        """Set *attr* to *new_value* on every entity in *entity_ids*.

        Records the change on the undo stack so it can be reversed.
        """
        doc = self._document
        changes = []
        for eid in entity_ids:
            ent = doc.get_entity(eid)
            if ent is not None:
                old_val = getattr(ent, attr, None)
                setattr(ent, attr, new_value)
                changes.append((eid, attr, old_val, new_value))
        if changes:
            self._undo_stack.push(
                SetEntityPropertiesUndoCommand(doc, changes, description)
            )
            doc._notify()
            self.document_changed.emit()

    def set_layer_property(
        self,
        layer_name: str,
        attr: str,
        new_value,
        *,
        description: str = "Change layer property",
    ) -> None:
        """Set *attr* on the layer named *layer_name*.

        Records the change on the undo stack.
        """
        doc = self._document
        lyr = doc.get_layer(layer_name)
        if lyr is None:
            return
        old_val = getattr(lyr, attr, None)
        setattr(lyr, attr, new_value)
        self._undo_stack.push(
            SetLayerPropertyUndoCommand(
                doc, layer_name, attr, old_val, new_value, description
            )
        )
        doc._notify()
        self.document_changed.emit()

    def rename_layer(self, old_name: str, new_name: str) -> None:
        """Rename a layer and record it on the undo stack."""
        doc = self._document
        lyr = doc.get_layer(old_name)
        if lyr is None:
            return
        lyr.name = new_name
        if doc.active_layer == old_name:
            doc.active_layer = new_name
        self._undo_stack.push(RenameLayerUndoCommand(doc, old_name, new_name))
        doc._notify()
        self.document_changed.emit()

    def add_layer(self, layer) -> None:
        """Add a layer and record it on the undo stack."""
        doc = self._document
        doc.add_layer(layer)
        self._undo_stack.push(AddLayerUndoCommand(doc, layer))
        self.document_changed.emit()

    def remove_layer_undoable(
        self,
        layer_name: str,
        *,
        reassign_to: str = "default",
    ) -> bool:
        """Remove a layer, reassign its entities, and record on undo stack.

        Returns ``True`` if the layer was actually removed.
        """
        doc = self._document
        lyr = doc.get_layer(layer_name)
        if lyr is None or layer_name == "default":
            return False

        # Find the index before removal.
        layer_index = next(
            (i for i, l in enumerate(doc.layers) if l.name == layer_name), 0
        )

        # Collect entities to reassign.
        reassigned = []
        for ent in doc.entities:
            if ent.layer == layer_name:
                reassigned.append((ent.id, ent.layer))
                ent.layer = reassign_to

        was_active = doc.active_layer == layer_name
        doc.remove_layer(layer_name)
        if was_active:
            doc.active_layer = reassign_to

        self._undo_stack.push(
            RemoveLayerUndoCommand(
                doc, lyr, layer_index, reassigned, was_active
            )
        )
        doc._notify()
        self.document_changed.emit()
        return True

    def set_active_layer(self, new_name: str) -> None:
        """Change the active layer and record it on the undo stack."""
        doc = self._document
        old_name = doc.active_layer
        if old_name == new_name:
            return
        doc.active_layer = new_name
        self._undo_stack.push(SetActiveLayerUndoCommand(doc, old_name, new_name))
        doc._notify()
        self.document_changed.emit()

    # -------------------------------------------------------------- internals

    def _run_in_thread(self, cmd: CommandBase, name: str) -> None:
        """Target function for the command worker thread."""
        self.command_started.emit(name)
        try:
            cmd.execute()
        except CommandCancelled:
            pass
        except Exception as exc:
            # Surface the error in the status bar and console without crashing.
            self.status_message.emit(f"Command error: {exc}")
            import traceback
            traceback.print_exc()
        finally:
            self._active_command = None
            self._dynamic_callback = None
            self.snap_from_point = None
            self._set_input_mode("none")
            self.status_message.emit("")
            self.command_finished.emit()

    def _wait_for_input(self) -> Any:
        """Block the command thread until a value or sentinel arrives."""
        while True:
            try:
                value = self._input_queue.get(timeout=0.05)
                if value is _SENTINEL:
                    raise CommandCancelled()
                return value
            except queue.Empty:
                # Periodically check for a cancellation that arrived without
                # going through the queue (shouldn't normally happen, but
                # provides an extra safety net).
                if self._cancelled.is_set():
                    raise CommandCancelled()

    def _put_input(self, value: Any) -> None:
        """Place *value* in the input queue (non-blocking; drops if full)."""
        try:
            self._input_queue.put_nowait(value)
        except queue.Full:
            pass  # A value already queued; the command isn't waiting yet.

    def _set_input_mode(self, mode: str) -> None:
        # Always emit so the dynamic input widget re-activates on every new
        # get_point/get_integer/… call, even when the mode hasn't changed
        # (e.g. two consecutive get_point() calls in the same command).
        self._input_mode = mode
        self.input_mode_changed.emit(mode)

    def _drain_queue(self) -> None:
        """Discard any leftover values from a previous command."""
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except queue.Empty:
                break

    def __repr__(self) -> str:          # noqa: D105
        state = "running" if self.is_running else "idle"
        return f"<Editor {state} entities={len(self._document)}>"
