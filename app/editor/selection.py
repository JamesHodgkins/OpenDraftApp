"""
Selection set — tracks which entities are currently selected.

Provides add / remove / toggle / clear operations and emits a Qt signal
whenever the selection changes so the canvas and property panels can update.
"""
from __future__ import annotations

from typing import Set

from PySide6.QtCore import QObject, Signal


class SelectionSet(QObject):
    """Ordered set of selected entity IDs with change notification."""

    # Emitted whenever the selection contents change.
    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ids: Set[str] = set()

    # ------------------------------------------------------------------ query

    @property
    def ids(self) -> Set[str]:
        """Return a *copy* of the current set of selected IDs."""
        return set(self._ids)

    def __contains__(self, entity_id: str) -> bool:
        return entity_id in self._ids

    def __len__(self) -> int:
        return len(self._ids)

    def __bool__(self) -> bool:
        return bool(self._ids)

    # --------------------------------------------------------------- mutation

    def add(self, entity_id: str) -> None:
        """Add *entity_id* to the selection (no-op if already present)."""
        if entity_id not in self._ids:
            self._ids.add(entity_id)
            self.changed.emit()

    def remove(self, entity_id: str) -> None:
        """Remove *entity_id* from the selection (no-op if not present)."""
        if entity_id in self._ids:
            self._ids.discard(entity_id)
            self.changed.emit()

    def toggle(self, entity_id: str) -> None:
        """Add if absent, remove if present."""
        if entity_id in self._ids:
            self._ids.discard(entity_id)
        else:
            self._ids.add(entity_id)
        self.changed.emit()

    def set(self, ids: Set[str]) -> None:
        """Replace the entire selection with *ids*."""
        if ids != self._ids:
            self._ids = set(ids)
            self.changed.emit()

    def extend(self, ids: Set[str]) -> None:
        """Add all *ids* to the current selection."""
        before = len(self._ids)
        self._ids |= ids
        if len(self._ids) != before:
            self.changed.emit()

    def subtract(self, ids: Set[str]) -> None:
        """Remove all *ids* from the current selection."""
        before = len(self._ids)
        self._ids -= ids
        if len(self._ids) != before:
            self.changed.emit()

    def clear(self) -> None:
        """Deselect everything."""
        if self._ids:
            self._ids.clear()
            self.changed.emit()
