"""
Document store — the central in-memory representation of an OpenDraft file.

A :class:`DocumentStore` holds all drawing entities, layer definitions and
document-level state.  It can be serialised to / deserialised from the
JSON format described in the project's web-app prototype.

Typical usage::

    from app.document import DocumentStore

    doc = DocumentStore()
    doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(100, 0)))

    # Persist
    doc.save_json("drawing.json")

    # Load
    doc2 = DocumentStore.load_json("drawing.json")
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from PySide6.QtCore import QObject, Signal as _Signal
import warnings

from app.entities import BaseEntity, entity_from_dict


# ---------------------------------------------------------------------------
# Qt change notifier
# ---------------------------------------------------------------------------

class _DocumentNotifier(QObject):
    """Minimal QObject companion so DocumentStore can emit a proper Qt signal."""
    changed = _Signal()


# ---------------------------------------------------------------------------
# Layer model
# ---------------------------------------------------------------------------

@dataclass
class Layer:
    """A named drawing layer with display properties."""

    name: str = "default"
    color: str = "#ffffff"
    visible: bool = True
    line_style: str = "solid"
    thickness: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "color": self.color,
            "visible": self.visible,
            "lineStyle": self.line_style,
            "thickness": self.thickness,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Layer":
        return cls(
            name=d.get("name", "default"),
            color=d.get("color", "#ffffff"),
            visible=bool(d.get("visible", True)),
            line_style=d.get("lineStyle", "solid"),
            thickness=float(d.get("thickness", 1.0)),
        )

    def __repr__(self) -> str:          # noqa: D105
        return f"<Layer {self.name!r}>"


# ---------------------------------------------------------------------------
# Document store
# ---------------------------------------------------------------------------

@dataclass
class DocumentStore:
    """In-memory representation of a single OpenDraft drawing.

    Attributes
    ----------
    version:
        File-format version string.
    entities:
        Ordered list of all drawing entities.
    layers:
        All layer definitions; always contains at least the ``"default"``
        layer.
    active_layer:
        Name of the currently active layer (new entities are placed here).
    active_color:
        If set, overrides the layer colour for new entities.
    active_line_style:
        If set, overrides the layer line-style for new entities.
    active_thickness:
        If set, overrides the layer thickness for new entities.
    """

    version: str = "1.0"
    entities: List[BaseEntity] = field(default_factory=list)
    layers: List[Layer] = field(default_factory=lambda: [Layer()])
    active_layer: str = "default"
    active_color: Optional[str] = None
    active_line_style: Optional[str] = None
    active_thickness: Optional[float] = None

    # Qt-based change notifier — provides a proper Signal instead of bare callbacks.
    # ``field(...)`` keeps it out of ``__init__``, ``__repr__``, equality, and JSON.
    _notifier: _DocumentNotifier = field(
        default_factory=_DocumentNotifier, init=False, repr=False, compare=False
    )

    # O(1) entity lookup by id — kept in sync with ``entities`` list.
    _entity_by_id: Dict[str, BaseEntity] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        # Rebuild the id index from the initial entities list (set by from_dict).
        self._entity_by_id = {e.id: e for e in self.entities}

    # ------------------------------------------------------------------
    # Change notification
    # ------------------------------------------------------------------

    def add_change_listener(self, fn: Callable[[], None]) -> None:
        """Register *fn* to be called (no arguments) on any document mutation.

        Internally connects *fn* to the ``_DocumentNotifier.changed`` Qt signal,
        so callers that need thread-safe delivery should wrap *fn* in a Qt slot
        connected with ``Qt.QueuedConnection`` before passing it here.
        """
        self._notifier.changed.connect(fn)

    def remove_change_listener(self, fn: Callable[[], None]) -> None:
        """Unregister a previously registered change listener."""
        # PySide6 may emit a RuntimeWarning when disconnecting a slot that
        # isn't connected; suppress that specific warning here so tests remain quiet.
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="Failed to disconnect", category=RuntimeWarning
                )
                self._notifier.changed.disconnect(fn)
        except RuntimeError:
            pass  # was not connected

    def _notify(self) -> None:
        """Emit the Qt ``changed`` signal to notify all registered listeners."""
        self._notifier.changed.emit()

    # ------------------------------------------------------------------
    # Entity CRUD
    # ------------------------------------------------------------------

    def add_entity(self, entity: BaseEntity) -> BaseEntity:
        """Append *entity* to the store and return it."""
        self.entities.append(entity)
        self._entity_by_id[entity.id] = entity
        self._notify()
        return entity

    def remove_entity(self, entity_id: str) -> Optional[BaseEntity]:
        """Remove the entity with *entity_id* and return it, or ``None``."""
        entity = self._entity_by_id.pop(entity_id, None)
        if entity is None:
            return None
        self.entities.remove(entity)
        self._notify()
        return entity

    def get_entity(self, entity_id: str) -> Optional[BaseEntity]:
        """Return the entity with *entity_id*, or ``None``."""
        return self._entity_by_id.get(entity_id)

    def entities_on_layer(self, layer_name: str) -> Iterator[BaseEntity]:
        """Yield every entity assigned to *layer_name*."""
        return (e for e in self.entities if e.layer == layer_name)

    def clear(self) -> None:
        """Remove all entities from the document."""
        self.entities.clear()
        self._entity_by_id.clear()
        self._notify()

    # ------------------------------------------------------------------
    # Layer helpers
    # ------------------------------------------------------------------

    def add_layer(self, layer: Layer) -> Layer:
        """Add *layer* to the document (no-op if the name already exists)."""
        if not self.get_layer(layer.name):
            self.layers.append(layer)
            self._notify()
        return layer

    def get_layer(self, name: str) -> Optional[Layer]:
        """Return the layer with *name*, or ``None``."""
        for lyr in self.layers:
            if lyr.name == name:
                return lyr
        return None

    def remove_layer(self, name: str) -> Optional[Layer]:
        """Remove the layer with *name* and return it, or ``None``.

        The ``"default"`` layer cannot be removed.
        """
        if name == "default":
            return None
        for i, lyr in enumerate(self.layers):
            if lyr.name == name:
                removed = self.layers.pop(i)
                self._notify()
                return removed
        return None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the document to a JSON-compatible dict."""
        return {
            "version": self.version,
            "entities": [e.to_dict() for e in self.entities],
            "layers": [lyr.to_dict() for lyr in self.layers],
            "activeLayer": self.active_layer,
            "currentActiveColor": self.active_color,
            "currentActiveLineStyle": self.active_line_style,
            "currentActiveThickness": self.active_thickness,
        }

    @classmethod
    def _migrate(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        """Upgrade older document dicts to the current schema.

        Called automatically by :meth:`from_dict` before deserialisation.
        Add a new ``if version == "x.y":`` block here whenever the schema
        changes so that old saved files continue to load cleanly.
        """
        import copy as _copy
        d = _copy.deepcopy(d)
        # Normalise missing version to "1.0"
        d.setdefault("version", "1.0")
        # Future migration steps go here, e.g.:
        #   if d["version"] == "0.9":
        #       d = _migrate_0_9_to_1_0(d)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DocumentStore":
        """Deserialise a document from a dict (e.g. loaded from JSON)."""
        d = cls._migrate(d)
        layers = [Layer.from_dict(l) for l in d.get("layers", [])]
        if not layers:
            layers = [Layer()]

        return cls(
            version=d.get("version", "1.0"),
            entities=[entity_from_dict(e) for e in d.get("entities", [])],
            layers=layers,
            active_layer=d.get("activeLayer", "default"),
            active_color=d.get("currentActiveColor"),
            active_line_style=d.get("currentActiveLineStyle"),
            active_thickness=d.get("currentActiveThickness"),
        )

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def save_json(self, path: str | Path, *, indent: int = 2) -> None:
        """Write the document to *path* as formatted JSON."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=indent)

    @classmethod
    def load_json(cls, path: str | Path) -> "DocumentStore":
        """Load and return a :class:`DocumentStore` from a JSON file."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.entities)

    def __iter__(self) -> Iterator[BaseEntity]:
        return iter(self.entities)

    def __repr__(self) -> str:          # noqa: D105
        return (
            f"<DocumentStore v={self.version!r} "
            f"entities={len(self.entities)} layers={len(self.layers)}>"
        )
