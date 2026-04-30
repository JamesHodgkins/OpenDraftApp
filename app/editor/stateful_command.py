"""Stateful command base and export descriptor.

Commands that inherit from :class:`StatefulCommandBase` run on the GUI thread
and declare editable properties via :func:`export`.  The editor shows a popup
while the command is active; property changes automatically trigger
:meth:`~StatefulCommandBase.update`, and Enter / Escape call
:meth:`~StatefulCommandBase.commit` / :meth:`~StatefulCommandBase.cancel`.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING

from app.editor.base_command import CommandBase
from app.entities import Vec2

if TYPE_CHECKING:
    from app.editor.editor import Editor


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ExportInfo:
    """Metadata for a single exported property."""

    name: str
    label: str
    input_kind: str
    default: Any


@dataclass(frozen=True, slots=True)
class PartialPoint:
    """Partially specified point (``x`` and/or ``y`` may be ``None``).

    Used by controller-panel point rows so commands can preview geometry while
    one component is still cursor-driven.
    """

    x: float | None = None
    y: float | None = None

    def is_empty(self) -> bool:
        return self.x is None and self.y is None

    def is_complete(self) -> bool:
        return self.x is not None and self.y is not None


# ---------------------------------------------------------------------------
# Descriptor
# ---------------------------------------------------------------------------

class ExportDescriptor:
    """Data descriptor that stores a per-instance exported property.

    Usage::

        class MyCommand(StatefulCommandBase):
            start = export(Vec2(0, 0), label="Start", input_kind="point")
    """

    def __init__(
        self,
        default: Any = None,
        *,
        label: str = "",
        input_kind: str = "point",
    ) -> None:
        self._default = default
        self.label = label
        self.input_kind = input_kind
        self.name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        if not self.label:
            self.label = name.replace("_", " ").title()

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return self
        try:
            return instance.__dict__[self.name]
        except KeyError:
            return self._default

    def __set__(self, instance: Any, value: Any) -> None:
        if instance is None:
            return
        instance.__dict__[self.name] = value
        # Notify the command so it can refresh its preview.
        updater: Callable[[], None] | None = getattr(instance, "update", None)
        if updater is not None and callable(updater):
            try:
                updater()
            except Exception:
                # Don't let a preview refresh crash the command.
                import traceback

                traceback.print_exc()

    def info(self) -> ExportInfo:
        return ExportInfo(
            name=self.name,
            label=self.label,
            input_kind=self.input_kind,
            default=self._default,
        )


def export(
    default: Any = None,
    *,
    label: str = "",
    input_kind: str = "point",
) -> ExportDescriptor:
    """Declare an exported property on a :class:`StatefulCommandBase`.

    Parameters
    ----------
    default:
        Initial value when the command starts.
    label:
        User-facing label shown in the properties popup.
    input_kind:
        How the property receives input: ``"point"``, ``"vector"``,
        ``"float"``, ``"integer"``, ``"string"``, ``"angle"`` or
        ``"length"``.
    """
    return ExportDescriptor(default, label=label, input_kind=input_kind)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class StatefulCommandBase(CommandBase):
    """Base class for commands that run statefully on the GUI thread.

    Subclasses declare exported fields with :func:`export` and override
    :meth:`start`, :meth:`update`, :meth:`commit`, and optionally
    :meth:`cancel`.

    The editor detects this base class at runtime and routes it through the
    stateful execution path (no worker thread).

        Authoring helpers
        -----------------
        ``StatefulCommandBase`` provides a small helper API so command scripts can
        focus on geometry logic instead of repetitive input plumbing:

        - :meth:`begin` resets exports and selects the active export.
        - :meth:`point_value` / :meth:`vector_value` resolve committed values.
        - :meth:`point_preview` / :meth:`vector_preview` resolve live values,
            including :class:`PartialPoint` textbox input.
        - :meth:`set_snap_for_active` centralizes active-export snap anchor routing.
    """

    #: Set automatically by the ``@command`` decorator.
    command_name: str = ""

    def __init__(self, editor: "Editor") -> None:
        super().__init__(editor)
        self._active_export: str = ""
        self._is_committed: bool = False
        self._exports: list[ExportInfo] = []
        self._discover_exports()

    # -- introspection ------------------------------------------------------

    def _discover_exports(self) -> None:
        exports: list[ExportInfo] = []
        for cls in reversed(self.__class__.__mro__):
            for _name, obj in cls.__dict__.items():
                if isinstance(obj, ExportDescriptor):
                    exports.append(obj.info())
        # Deduplicate while preserving MRO order (child overrides parent).
        seen: set[str] = set()
        deduped: list[ExportInfo] = []
        for info in exports:
            if info.name not in seen:
                seen.add(info.name)
                deduped.append(info)
        self._exports = deduped

    def exports(self) -> list[ExportInfo]:
        """Return metadata for every exported property on this command."""
        return list(self._exports)

    # -- active export ------------------------------------------------------

    @property
    def active_export(self) -> str:
        """Name of the exported property currently receiving canvas input."""
        return self._active_export

    @active_export.setter
    def active_export(self, name: str) -> None:
        valid = {e.name for e in self._exports}
        if name and name not in valid:
            raise ValueError(
                f"'{name}' is not an exported property of {self.__class__.__name__}. "
                f"Valid: {valid}"
            )
        if name == self._active_export:
            return
        self._active_export = name
        updater: Callable[[], None] | None = getattr(self, "update", None)
        if updater is not None and callable(updater):
            try:
                updater()
            except Exception:
                import traceback

                traceback.print_exc()

    def advance_active_export(self) -> None:
        """Move ``active_export`` to the next property that is currently unset (``None``).

        If every property has a value, ``active_export`` is left unchanged.
        """
        exports = self.exports()
        if not exports:
            return
        current_idx = next(
            (i for i, e in enumerate(exports) if e.name == self._active_export), -1
        )
        # Search forward from current position.
        for i in range(current_idx + 1, len(exports)):
            if getattr(self, exports[i].name, None) is None:
                self.active_export = exports[i].name
                return
        # Wrap around and search from the beginning.
        for i in range(len(exports)):
            if getattr(self, exports[i].name, None) is None:
                self.active_export = exports[i].name
                return

    # -- authoring helpers -------------------------------------------------

    def begin(
        self,
        *,
        active_export: str,
        reset: Sequence[str],
        snap_from: Vec2 | None = None,
    ) -> None:
        """Initialize common state for a fresh command run.

        Parameters
        ----------
        active_export:
            Export that should receive the next input.
        reset:
            Export names to reset to ``None`` at command start.
        snap_from:
            Optional initial snap anchor.
        """
        for name in reset:
            setattr(self, name, None)
        self.active_export = active_export
        self.editor.snap_from_point = snap_from

    @staticmethod
    def first_set(*values: Vec2 | None) -> Vec2 | None:
        """Return the first concrete point from *values*, else ``None``."""
        for value in values:
            if isinstance(value, Vec2):
                return value
        return None

    @staticmethod
    def _resolve_complete_vec2(value: Any) -> Vec2 | None:
        """Resolve a committed vector/point value from export storage."""
        if isinstance(value, Vec2):
            return value
        if isinstance(value, PartialPoint) and value.is_complete():
            x = value.x
            y = value.y
            if x is None or y is None:
                return None
            return Vec2(x, y)
        return None

    @staticmethod
    def _resolve_preview_vec2(
        value: Any,
        cursor: Vec2,
        *,
        base: Vec2 | None = None,
    ) -> Vec2 | None:
        """Resolve a live preview vector/point from export storage.

        When ``base`` is provided, partial values are interpreted as vector
        components relative to ``base`` (cursor - base).
        """
        if isinstance(value, Vec2):
            return value
        if isinstance(value, PartialPoint):
            if value.is_empty():
                return None
            ref = cursor if base is None else cursor - base
            return Vec2(
                ref.x if value.x is None else value.x,
                ref.y if value.y is None else value.y,
            )
        return None

    def point_value(self, name: str) -> Vec2 | None:
        """Return resolved point value for export *name*."""
        return self._resolve_complete_vec2(getattr(self, name, None))

    def vector_value(self, name: str) -> Vec2 | None:
        """Return resolved vector value for export *name*."""
        return self._resolve_complete_vec2(getattr(self, name, None))

    def point_preview(self, name: str, cursor: Vec2) -> Vec2 | None:
        """Return live preview point for export *name*."""
        return self._resolve_preview_vec2(getattr(self, name, None), cursor)

    def vector_preview(
        self,
        name: str,
        cursor: Vec2,
        *,
        base: Vec2 | None = None,
    ) -> Vec2 | None:
        """Return live preview vector for export *name*."""
        return self._resolve_preview_vec2(
            getattr(self, name, None),
            cursor,
            base=base,
        )

    def number_value(self, name: str) -> float | None:
        """Return numeric value for export *name* when set, else ``None``."""
        value = getattr(self, name, None)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def string_value(self, name: str) -> str | None:
        """Return string value for export *name* when set, else ``None``."""
        value = getattr(self, name, None)
        if isinstance(value, str):
            return value
        return None

    def set_snap_for_active(
        self,
        mapping: Mapping[str, Vec2 | None | Sequence[Vec2 | None]],
        *,
        default: Vec2 | None | Sequence[Vec2 | None] = (),
    ) -> None:
        """Set ``editor.snap_from_point`` from an active-export mapping.

        ``mapping`` keys are export names (``active_export`` values). Each
        value can be a single point or an ordered sequence of candidate points.
        The first non-``None`` candidate is used.
        """
        choice = mapping.get(self.active_export, default)
        if isinstance(choice, Vec2) or choice is None:
            candidates = (choice,)
        else:
            candidates = tuple(choice)
        self.editor.snap_from_point = self.first_set(*candidates)

    # -- lifecycle hooks (override in subclasses) ---------------------------

    def start(self) -> None:
        """Called once when the command is activated.

        Set initial property values here.  Setting an exported property
        automatically triggers :meth:`update` via the descriptor.
        """

    def update(self) -> None:
        """Called automatically whenever an exported property changes.

        Typically used to refresh the dynamic preview via
        ``self.editor.set_dynamic(...)``.
        """

    def commit(self) -> None:
        """Called when the user presses Enter to finalize the command.

        Override to add entities, record undo, etc.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement commit()"
        )

    def cancel(self) -> None:
        """Called when the user presses Escape to abort.

        Default behavior clears dynamic preview and snap anchor. Override when
        a command needs custom cancel semantics (for example finalize-on-escape).
        """
        self.editor.clear_dynamic()
        self.editor.snap_from_point = None

    def seed_from_previous(self, prev: "StatefulCommandBase") -> None:
        """Called once after :meth:`start` when a Repeat-command run auto-launches.

        ``prev`` is the just-committed instance from the previous run.  The
        default implementation is a no-op (a fresh command).  Override to
        chain values from *prev* — e.g. ``DrawLineCommand`` sets
        ``self.start_point = prev.end_point`` so consecutive lines join up.
        """

    # ---- introspection used by the auto-complete logic --------------------

    def all_exports_set(self) -> bool:
        """Return ``True`` when every exported property has a non-``None`` value."""
        return all(
            getattr(self, info.name, None) is not None for info in self._exports
        )

    def __repr__(self) -> str:  # noqa: D105
        return f"<{self.__class__.__name__} exports={self._exports}>"
