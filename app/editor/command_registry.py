"""Command registry for core and plugin command implementations.

This module provides:

- ``@command(...)`` for legacy/core class-based command registration.
- ``register_sdk_command(...)`` for SDK/plugin registration.
- Command metadata storage and lookup via ``CommandSpec``.
- Built-in package autodiscovery and plugin entry-point autodiscovery.
"""
from __future__ import annotations

import importlib
import importlib.metadata as importlib_metadata
import inspect
import logging
import pkgutil
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Type

from app.editor.base_command import CommandBase
from app.sdk.commands.context import CommandContext
from app.sdk.commands.spec import CommandSpec

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, Type[CommandBase]] = {}
_SPECS: Dict[str, CommandSpec] = {}
_ALIASES: Dict[str, str] = {}
_CATALOG_VERSION: int = 0
_NAMESPACED_ID_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)+$"
)


def _is_namespaced_command_id(command_id: str) -> bool:
    return bool(_NAMESPACED_ID_RE.fullmatch(command_id))


def _slugify_legacy_command_id(command_id: str) -> str:
    """Convert legacy IDs like ``lineCommand`` to a namespaced slug token."""
    name = re.sub(r"(?i)command$", "", command_id)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"[^A-Za-z0-9]+", "_", name)
    name = name.strip("_").lower()
    return name or "command"


def _canonical_command_id(command_id: str, *, source: str) -> tuple[str, tuple[str, ...]]:
    """Return canonical id and implicit aliases for *command_id*.

    Core commands may use legacy un-namespaced IDs for compatibility with
    existing ribbon action strings; they are canonicalized to ``core.<slug>``
    and the legacy id becomes an alias.
    """
    if not command_id:
        raise ValueError("Command id must be a non-empty string")

    if _is_namespaced_command_id(command_id):
        return command_id, ()

    if source == "core":
        canonical = f"core.{_slugify_legacy_command_id(command_id)}"
        return canonical, (command_id,)

    raise ValueError(
        f"Command id {command_id!r} must be namespaced (for example 'vendor.tool')"
    )


def _humanize_command_id(command_id: str) -> str:
    """Convert IDs like ``lineCommand`` / ``core.line`` to user labels."""
    label = command_id.split(".")[-1]
    label = re.sub(r"(?i)command$", "", label)
    parts = re.sub(r"([A-Z])", r" \1", label).replace("_", " ").split()
    return " ".join(p.capitalize() for p in parts) if parts else command_id


def _description_from_docstring(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.splitlines()[0] if doc else ""


def _normalize_spec(spec: CommandSpec, *, default_source: str) -> CommandSpec:
    display_name = spec.display_name or _humanize_command_id(spec.id)
    category = spec.category or "General"
    source = spec.source or default_source

    # Preserve alias order while removing duplicates and self-aliases.
    unique_aliases: list[str] = []
    for alias in spec.aliases:
        if not alias or alias == spec.id or alias in unique_aliases:
            continue
        unique_aliases.append(alias)

    return CommandSpec(
        id=spec.id,
        display_name=display_name,
        description=spec.description,
        category=category,
        aliases=tuple(unique_aliases),
        icon=spec.icon,
        source=source,
        min_api_version=spec.min_api_version,
    )


def _merge_specs(base: CommandSpec, overlay: CommandSpec) -> CommandSpec:
    """Merge *overlay* metadata onto *base* while preserving base data."""
    merged_aliases: tuple[str, ...] = tuple(dict.fromkeys(base.aliases + overlay.aliases))
    category = base.category
    if overlay.category and overlay.category != "General":
        category = overlay.category

    return CommandSpec(
        id=base.id,
        display_name=overlay.display_name or base.display_name,
        description=overlay.description or base.description,
        category=category,
        aliases=merged_aliases,
        icon=overlay.icon or base.icon,
        source=overlay.source or base.source,
        min_api_version=overlay.min_api_version or base.min_api_version,
    )


def _clear_aliases(command_id: str) -> None:
    stale = [alias for alias, target in _ALIASES.items() if target == command_id]
    for alias in stale:
        _ALIASES.pop(alias, None)


def _register_aliases(spec: CommandSpec) -> None:
    for alias in spec.aliases:
        if alias == spec.id:
            continue
        prior = _ALIASES.get(alias)
        if prior and prior != spec.id:
            raise ValueError(
                f"Alias collision: {alias!r} already resolves to {prior!r}, "
                f"cannot assign to {spec.id!r}"
            )
        _ALIASES[alias] = spec.id


def _resolve_command_id(name: str) -> str:
    return _ALIASES.get(name, name)


def _touch_catalog() -> None:
    global _CATALOG_VERSION
    _CATALOG_VERSION += 1


def _unregister_command_id(command_id: str) -> bool:
    had_entry = command_id in _REGISTRY or command_id in _SPECS
    if not had_entry:
        return False
    _REGISTRY.pop(command_id, None)
    _SPECS.pop(command_id, None)
    _clear_aliases(command_id)
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ActionValidationReport:
    """Resolution summary for a set of action names."""

    local_actions: tuple[str, ...]
    command_actions: tuple[str, ...]
    unresolved_actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommandCatalogRefreshResult:
    """Summary of a command-catalog refresh operation."""

    removed_command_ids: tuple[str, ...]
    loaded_entry_points: tuple[str, ...]
    command_count: int
    catalog_version: int


def validate_actions(
    action_names: "list[str] | tuple[str, ...] | set[str]",
    *,
    local_actions: "list[str] | tuple[str, ...] | set[str]" = (),
) -> ActionValidationReport:
    """Classify actions as local, command-backed, or unresolved."""
    local = set(local_actions)
    resolved_local: list[str] = []
    resolved_command: list[str] = []
    unresolved: list[str] = []

    for name in sorted(set(action_names)):
        if name in local:
            resolved_local.append(name)
            continue
        if get_command(name) is not None:
            resolved_command.append(name)
            continue
        unresolved.append(name)

    return ActionValidationReport(
        local_actions=tuple(resolved_local),
        command_actions=tuple(resolved_command),
        unresolved_actions=tuple(unresolved),
    )


def validate_action_sources(
    action_sources: Mapping[str, "list[str] | tuple[str, ...] | set[str]"],
    *,
    local_actions: "list[str] | tuple[str, ...] | set[str]" = (),
) -> Dict[str, ActionValidationReport]:
    """Validate multiple named action sources.

    Example
    -------
    ``{"ribbon": {"lineCommand", "undo"}, "palette": {...}}``
    """
    reports: Dict[str, ActionValidationReport] = {}
    for source_name, actions in action_sources.items():
        reports[source_name] = validate_actions(actions, local_actions=local_actions)
    return reports


def command(
    name: str,
    *,
    display_name: str | None = None,
    description: str = "",
    category: str = "General",
    aliases: tuple[str, ...] = (),
    icon: str | None = None,
    source: str = "core",
    min_api_version: str = "1.0",
) -> Callable[[Type[CommandBase]], Type[CommandBase]]:
    """Class decorator that registers a command under *name*.

    Core commands may pass legacy action IDs (for example ``lineCommand``),
    which are canonicalized to namespaced IDs (for example ``core.line``) and
    exposed under the legacy ID as an alias.
    """

    def _decorator(cls: Type[CommandBase]) -> Type[CommandBase]:
        canonical_name, implicit_aliases = _canonical_command_id(name, source=source)
        merged_aliases = tuple(dict.fromkeys((*implicit_aliases, *aliases)))

        if canonical_name in _REGISTRY and _REGISTRY[canonical_name] is not cls:
            raise ValueError(
                f"Command id collision: {canonical_name!r} already registered by "
                f"{_REGISTRY[canonical_name].__name__}, cannot register {cls.__name__}"
            )

        cls.command_name = canonical_name
        _REGISTRY[canonical_name] = cls

        doc_description = _description_from_docstring(cls)
        spec_description = description or doc_description

        spec = _normalize_spec(
            CommandSpec(
                id=canonical_name,
                display_name=display_name,
                description=spec_description,
                category=category,
                aliases=merged_aliases,
                icon=icon,
                source=source,
                min_api_version=min_api_version,
            ),
            default_source=source,
        )
        _SPECS[canonical_name] = spec
        _clear_aliases(canonical_name)
        _register_aliases(spec)
        _touch_catalog()
        return cls

    return _decorator


def register_sdk_command(spec: CommandSpec, impl: Any) -> Type[CommandBase]:
    """Register an SDK/plugin command implementation.

    ``spec.id`` must be namespaced for non-core sources.
    """
    source = spec.source or "plugin"
    canonical_id, implicit_aliases = _canonical_command_id(spec.id, source=source)
    spec = _normalize_spec(
        CommandSpec(
            id=canonical_id,
            display_name=spec.display_name,
            description=spec.description,
            category=spec.category,
            aliases=tuple(dict.fromkeys((*implicit_aliases, *spec.aliases))),
            icon=spec.icon,
            source=source,
            min_api_version=spec.min_api_version,
        ),
        default_source=source,
    )

    if inspect.isclass(impl) and issubclass(impl, CommandBase):
        adapter_cls: Type[CommandBase] = impl
    else:
        if not callable(impl):
            raise TypeError("SDK command impl must be callable or a class")

        class _SdkAdapter(CommandBase):
            command_name = canonical_id

            def execute(self) -> None:
                ctx = CommandContext(self.editor)
                if inspect.isclass(impl):
                    instance = impl()
                    execute = getattr(instance, "execute", None)
                    if execute is None or not callable(execute):
                        raise TypeError(
                            f"{impl.__name__} must define execute(self, ctx)"
                        )
                    execute(ctx)
                    return
                impl(ctx)

        safe_name = re.sub(r"[^0-9a-zA-Z_]", "_", spec.id)
        _SdkAdapter.__name__ = f"SdkAdapter_{safe_name}"
        _SdkAdapter.__qualname__ = _SdkAdapter.__name__
        _SdkAdapter.__doc__ = spec.description or f"SDK command adapter for {spec.id}."
        adapter_cls = _SdkAdapter

    if canonical_id in _REGISTRY and _REGISTRY[canonical_id] is not adapter_cls:
        raise ValueError(
            f"Command id collision: {canonical_id!r} already registered by "
            f"{_REGISTRY[canonical_id].__name__}, cannot register {adapter_cls.__name__}"
        )

    adapter_cls.command_name = canonical_id
    _REGISTRY[canonical_id] = adapter_cls
    _SPECS[canonical_id] = spec
    _clear_aliases(canonical_id)
    _register_aliases(spec)
    _touch_catalog()
    return adapter_cls


def apply_command_specs(
    specs: Mapping[str, CommandSpec],
    *,
    only_registered: bool = True,
) -> None:
    """Merge command metadata specs into the registry."""
    changed = False
    for key, incoming in specs.items():
        candidate_id = key or incoming.id
        if not candidate_id:
            continue

        source = incoming.source or "core"
        resolved_candidate = _resolve_command_id(candidate_id)
        if resolved_candidate != candidate_id:
            target_id = resolved_candidate
            inferred_aliases: tuple[str, ...] = (candidate_id,)
        else:
            target_id, inferred_aliases = _canonical_command_id(candidate_id, source=source)

        if incoming.id and incoming.id != target_id and incoming.id not in inferred_aliases:
            inferred_aliases = (*inferred_aliases, incoming.id)

        if only_registered and target_id not in _REGISTRY:
            continue

        normalized_incoming = _normalize_spec(
            CommandSpec(
                id=target_id,
                display_name=incoming.display_name,
                description=incoming.description,
                category=incoming.category,
                aliases=tuple(dict.fromkeys((*incoming.aliases, *inferred_aliases))),
                icon=incoming.icon,
                source=incoming.source,
                min_api_version=incoming.min_api_version,
            ),
            default_source=source,
        )

        base_spec = _SPECS.get(target_id)
        if base_spec is None:
            _SPECS[target_id] = normalized_incoming
            _clear_aliases(target_id)
            _register_aliases(normalized_incoming)
            changed = True
            continue

        merged = _merge_specs(base_spec, normalized_incoming)
        merged = _normalize_spec(merged, default_source=base_spec.source or "core")
        if merged == base_spec:
            continue
        _SPECS[target_id] = merged
        _clear_aliases(target_id)
        _register_aliases(merged)
        changed = True

    if changed:
        _touch_catalog()


def get_command(name: str) -> Optional[Type[CommandBase]]:
    """Return the command class registered under *name*, or ``None``."""
    resolved = _resolve_command_id(name)
    return _REGISTRY.get(resolved)


def get_command_spec(name: str) -> Optional[CommandSpec]:
    """Return metadata for *name* (command id or alias), or ``None``."""
    resolved = _resolve_command_id(name)
    return _SPECS.get(resolved)


def registered_commands() -> Dict[str, Type[CommandBase]]:
    """Return a shallow copy of the full registry dict."""
    return dict(_REGISTRY)


def registered_command_specs() -> Dict[str, CommandSpec]:
    """Return a shallow copy of command metadata keyed by command id."""
    return dict(_SPECS)


def command_catalog() -> Dict[str, CommandSpec]:
    """Return a snapshot of the current command catalog."""
    return registered_command_specs()


def command_catalog_version() -> int:
    """Return the monotonic command-catalog version."""
    return _CATALOG_VERSION


def unregister_command(name: str) -> bool:
    """Remove a command (id or alias) from the registry and catalog."""
    command_id = _resolve_command_id(name)
    removed = _unregister_command_id(command_id)
    if removed:
        _touch_catalog()
    return removed


def unregister_commands_by_source(
    sources: "set[str] | list[str] | tuple[str, ...]",
) -> tuple[str, ...]:
    """Remove all commands whose metadata source is in *sources*."""
    source_set = set(sources)
    removed_ids: list[str] = []
    for command_id, spec in list(_SPECS.items()):
        if spec.source in source_set and _unregister_command_id(command_id):
            removed_ids.append(command_id)
    if removed_ids:
        _touch_catalog()
    return tuple(sorted(removed_ids))


def refresh_command_catalog(
    *,
    plugin_entry_point_group: str = "opendraft.commands",
    reload_plugins: bool = True,
    remove_non_core: bool = True,
) -> CommandCatalogRefreshResult:
    """Refresh the catalog so pickers can repopulate after plugin changes.

    When ``remove_non_core`` is true, all currently registered non-core
    commands are removed before optional plugin re-discovery.  This lets the
    catalog reflect plugin unload/install changes in one deterministic pass.
    """
    removed: tuple[str, ...] = ()
    if remove_non_core:
        non_core_sources = {
            spec.source for spec in _SPECS.values() if spec.source != "core"
        }
        if non_core_sources:
            removed = unregister_commands_by_source(non_core_sources)

    loaded: list[str] = []
    if reload_plugins:
        loaded = autodiscover_entry_points(plugin_entry_point_group)

    return CommandCatalogRefreshResult(
        removed_command_ids=removed,
        loaded_entry_points=tuple(loaded),
        command_count=len(_SPECS),
        catalog_version=_CATALOG_VERSION,
    )


def autodiscover(package: str) -> None:
    """Import every module in *package* so their ``@command`` decorators fire."""
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
            _log.warning("autodiscover: failed to import %r: %s", modname, exc)


def autodiscover_entry_points(group: str = "opendraft.commands") -> list[str]:
    """Load plugin command entry points from *group*.

    Entry-point targets may be either:

    - A module/object that registers commands as an import side effect.
    - A zero-argument callable that performs registration when invoked.

    Returns a list of successfully loaded entry-point names.
    """
    try:
        entries = importlib_metadata.entry_points(group=group)
    except TypeError:
        # Backward-compat path for older importlib.metadata APIs.
        eps = importlib_metadata.entry_points()
        entries = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
    except Exception as exc:
        _log.warning("entry-point discovery: failed to enumerate %r: %s", group, exc)
        return []

    loaded: list[str] = []
    for ep in entries:
        try:
            target = ep.load()
            if callable(target):
                target()
            loaded.append(ep.name)
        except Exception as exc:
            _log.warning(
                "entry-point discovery: failed to load %r from %r: %s",
                ep.name,
                group,
                exc,
            )
    return loaded
