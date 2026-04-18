# OpenDraft — Architecture & Health Audit

**Date:** 2026-04-18  
**Scope:** Full codebase review — architecture, composition, technical debt, test coverage, and maintainability.  
**Total source:** ~8,500 LOC (app + controls), ~1,650 LOC tests.

---

## Executive Summary

OpenDraft is a well-structured PySide6 2D CAD application with clean separation between document model, editor controller, and UI. The command/registry pattern is solid, the undo system is thorough, and the entity hierarchy uses a clean auto-registration pattern. However, several areas show accumulating technical debt — particularly the **CADCanvas god class** (1,223 lines), **scattered geometry utilities**, **inconsistent use of shared helpers across modify commands**, and **untested UI wiring code** that carries the highest regression risk.

**Overall health: 6.5/10** — Good foundations with localised complexity hotspots.

---

## 1. God Objects & Oversized Classes

### 1.1 `CADCanvas` — 1,223 lines (CRITICAL)

`app/canvas.py` is the single largest file and handles far too many concerns:

| Concern | Approximate lines |
|---|---|
| Coordinate transforms & origin anchoring | ~80 |
| Mouse event handling (press/move/release) | ~250 |
| Selection rectangle dragging | ~60 |
| Grip hover & grip editing (click-click) | ~120 |
| OSNAP integration | ~40 |
| Draftmate/polar tracking integration | ~40 |
| Ortho constraint logic | ~30 |
| Dynamic input widget orchestration | ~50 |
| Keyboard event handling | ~60 |
| Grid rendering (adaptive multi-level) | ~100 |
| Entity rendering & preview | ~150 |
| Selection highlight & grip drawing | ~80 |
| Scene caching (rubber band optimisation) | ~40 |

**Impact:** Any change to one concern (e.g. snap behaviour) risks breaking another (e.g. grip editing). The `mouseMoveEvent` handler alone is ~180 lines with deeply nested conditionals.

**Recommendation:** Extract into composable subsystems:
- `ViewportTransform` — pan/zoom, coordinate mapping, origin anchor
- `GridRenderer` — adaptive grid painting
- `InteractionManager` — delegates to SelectionTool, GripTool, CommandInputTool based on editor state
- Keep `CADCanvas` as a thin shell that owns these and routes Qt events

### 1.2 `DynamicInputWidget` — 527 lines

Handles 7 distinct input modes (point, integer, float, string, choice, angle, length) in a single class, mixing input validation, placeholder text computation, custom painting, and keyboard routing.

**Recommendation:** Strategy pattern — one `InputMode` subclass per mode, with the widget delegating to the active strategy.

### 1.3 `LayerManagerDialog` — 540 lines

The `_append_row()` method is ~150 lines building a single table row with 4+ inline lambda closures. Layer property mutations are performed directly on the document inside lambdas, bypassing a consistent undo path.

**Recommendation:** Extract a `LayerRowBuilder` helper; route all mutations through `Editor` undo commands.

---

## 2. Technical Debt

### 2.1 No Shared Geometry Module

Geometry utilities are scattered across at least four locations:

| Location | Functions |
|---|---|
| `app/entities/base.py` | `_geo_dist`, `_geo_pt_seg_dist`, `_geo_angle_on_arc`, `_geo_seg_intersects_rect` |
| `app/commands/modify_trim.py` | `_line_circle_params`, `_circle_circle_angles`, `_normalize_angle`, `_arc_span`, 10+ others |
| `app/commands/modify_extend.py` | `_line_line_intersect`, `_line_circle_intersect_pts`, `_arc_boundary_angles` |
| `app/commands/modify_helpers.py` | `_rotate_pt`, `_mirror_pt`, `_scale_pt`, `_translate` |

`modify_extend.py` imports directly from `modify_trim.py`, creating a brittle cross-dependency between sibling command modules. Adding a new entity type (e.g. Spline) would require changes in 3+ files.

**Recommendation:** Create `app/geometry.py` consolidating all pure-math helpers. Entity and command modules then import from a single source of truth.

### 2.2 `Vec2` Lacks Arithmetic Operators

`Vec2` is a frozen dataclass with only `to_dict`/`from_dict`. Every arithmetic operation is written inline:

```python
dx = pt.x - from_point.x
dy = pt.y - from_point.y
Vec2(pt.x + t * dx, pt.y + t * dy)
```

This is repeated dozens of times across the codebase. Adding `__add__`, `__sub__`, `__mul__`, and a `distance_to()` method would eliminate significant boilerplate and reduce error surface.

### 2.3 Inconsistent Use of `modify_helpers`

`_transform_entity()` in `modify_helpers.py` is designed to generically transform any entity, but:

| Command | Uses `_transform_entity()`? | Notes |
|---|---|---|
| `modify_copy.py` | Yes | Correct usage |
| `modify_move.py` | Yes | Correct usage |
| `modify_rotate.py` | Partially | Reimplements arc angle mutation inline |
| `modify_scale.py` | Partially | Reimplements radius/arc scaling inline |
| `modify_mirror.py` | No | Entirely local `_mirror_entity()` function |

Each reimplementation is a maintenance hazard — adding a new entity type requires updating 3–5 command files.

### 2.4 Incomplete Entity Implementations

| Entity | `draw()` | `nearest_snap()` | `grip_points()` | `crosses_rect()` |
|---|---|---|---|---|
| `DimensionEntity` | Stub (`pass`) | Stub (`None`) | Implemented | Missing |
| `HatchEntity` | Stub (`pass`) | Stub (`None`) | Missing | Delegates |
| `TextEntity` | Implemented | Stub (`None`) | Implemented | Missing |

Missing `crosses_rect()` means window/crossing selection will silently skip Text and Dimension entities — a user-visible bug for any drawing that uses them.

### 2.5 Magic Numbers & Hardcoded Tolerances

```python
# app/commands/modify_extend.py
tolerance = 10.0   # in one place
tolerance = 20.0   # in another

# app/canvas.py
self._pick_tolerance_px: float = 7.0
self._grip_pick_px: float = 7.0
self._grip_half_size: int = 5

# app/editor/osnap_engine.py
aperture = 15  # pixels
```

These are not user-configurable and have inconsistent values across subsystems. A user working at high zoom will experience different pick sensitivity for entity selection vs. grip picking vs. OSNAP.

**Recommendation:** Centralise into an `EditorSettings` or `Preferences` dataclass and pass it through the constructor chain.

---

## 3. Architecture & Composition

### 3.1 Thread Safety Model

The Editor uses a worker thread + `queue.Queue` handshake, which is fundamentally sound. However:

- **No thread-safe guard on `_dynamic_callback`:** The GUI thread reads `self._dynamic_callback` in `get_dynamic()` while the command thread writes it via `set_dynamic()` / `clear_dynamic()`. Python's GIL makes this safe for reference assignment but not for the *closure captured state* — if a command captures mutable state in its lambda, the GUI thread can read it mid-mutation.
- **Race in cancel():** The `put_nowait` / `get_nowait` / `put_nowait` sequence in `cancel()` is not atomic. Two rapid Escape presses could leave the queue in an inconsistent state, though this is unlikely in practice.

### 3.2 `RibbonPanel.setup_document()` — Fragile Control Binding

This 150+ line method discovers child widgets via `findChildren(QPushButton, "colorSwatchBtn")` and wires them to the document with inline lambdas. This is:

- **Fragile:** Renaming an `objectName` silently breaks the binding with no error.
- **Untestable:** No unit tests exist for this wiring; a regression would only be caught via manual QA.
- **Hard to extend:** Adding a new property control means editing a monolithic method.

**Recommendation:** Introduce a binding protocol (e.g. `ControlBinding` interface) and register bindings declaratively alongside the ribbon config.

### 3.3 Signal Wiring Centralisation

`MainWindow.__init__` is 180+ lines of signal/slot wiring. While this is a common pattern in Qt applications, the volume makes it fragile:

- Escape handling is duplicated between `MainWindow._handle_escape` and `CADCanvas.keyPressEvent`.
- Canvas signals (`pointSelected`, `cancelRequested`, `orthoChanged`) are connected in `MainWindow` but consumed by `Editor` — the canvas has no direct reference to the editor for these, which is good, but the indirection makes the flow hard to trace.
- Ortho/Draftmate mutual exclusion is implemented in *two* places (status bar toggles and canvas F-key handlers).

### 3.4 Document Store as Dataclass

`DocumentStore` uses `@dataclass` but also needs a `QObject`-derived notifier for signals — hence the `_DocumentNotifier` companion. This is a pragmatic workaround, but it means:

- `DocumentStore` cannot be a `QObject` itself (no multiple inheritance with frozen dataclass fields).
- `_notifier` is excluded from `__init__`, `__repr__`, `__eq__` via `field(...)` — any inadvertent serialisation or deep-copy could break the change notification chain.

---

## 4. Test Coverage Gaps

### 4.1 Coverage by Subsystem

| Subsystem | Test file | LOC tested | Coverage assessment |
|---|---|---|---|
| Entities | `test_entities.py` (268 lines) | BBox, snap, serialisation | Solid for geometric entities |
| Document | `test_document.py` (164) | CRUD, layers, JSON I/O | Good |
| Canvas | `test_canvas.py` (182) | Transforms, pen overrides | Moderate |
| Geometry | `test_geometry.py` (138) | Distance, intersection | Good |
| Undo | `test_undo.py` (376) | All undo command types | Excellent |
| Editor | `test_editor.py` (34) | Selection delete only | **Very thin** |
| Dynamic Input | `test_dynamic_input_widget.py` (48) | Basic key routing only | **Minimal** |
| Draftmate | `test_draftmate.py` (191) | Tracking, alignment | Good |
| Hit testing | `test_hit_testing.py` (46) | Point and rect hits | Moderate |
| OSNAP | `test_osnap.py` (88) | Snap algorithm | Moderate |
| Commands | — | — | **No test file exists** |
| Ribbon/UI | — | — | **No test file exists** |
| Layer Manager | — | — | **No test file exists** |

### 4.2 Highest-Risk Untested Code

1. **All 17 command classes** — zero test coverage. Drawing and modify commands are the core user-facing functionality. A regression in `modify_trim.py` (492 lines of intersection math) would be invisible.
2. **`RibbonPanel.setup_document()`** — 150 lines of widget-to-document binding with no tests.
3. **`Editor.run_command` / worker thread lifecycle** — only `test_editor.py` (34 lines) exists, covering just selection deletion. The thread handshake, cancel flow, get_point/get_integer paths, and undo integration are untested.

---

## 5. Other Observations

### 5.1 No CI/CD Configuration

No `.github/workflows/`, `Makefile`, or `tox.ini` was found. Tests can be run via `pytest` but there is no automated pipeline ensuring they pass on every commit.

### 5.2 No Type Checking Enforcement

No `mypy.ini`, `pyrightconfig.json`, or `[tool.mypy]` section in `pyproject.toml`. Type hints are used inconsistently — some methods have full annotations, others use bare `List`, `Optional[object]`, or no hints at all. Enabling a type checker would catch several latent issues (e.g. loose `snap_candidates()` return types).

### 5.3 Serialisation Has No Schema Version Migration

`DocumentStore.from_dict()` reads `version` but doesn't act on it. If the JSON schema evolves (e.g. a new entity field), old files will silently produce entities with missing attributes. A migration layer would prevent data loss.

### 5.4 No Logging

The application uses `print()` for the stylesheet load failure and `warnings.warn()` for non-critical issues. No structured logging (`logging` module) is configured. For a desktop CAD app, logging to a file would aid user bug reports.

### 5.5 Entity Lookup is O(n)

`DocumentStore.get_entity()`, `remove_entity()`, and iteration-based lookups scan the full entity list. For typical drawings (hundreds of entities) this is fine, but for large drawings (10,000+) it will become a bottleneck. An `{id: entity}` index would be a low-cost optimisation.

### 5.6 Awkward Imports

`ArcEntity.crosses_rect()` uses `__import__('app.entities.base', fromlist=['BBox'])` instead of a top-level import — likely to avoid a circular import, but this is non-idiomatic and should be resolved with a deferred import or structural change.

---

## 6. Prioritised Recommendations

| Priority | Item | Effort | Impact |
|---|---|---|---|
| **P0** | Complete `DimensionEntity`/`HatchEntity` stubs (`draw`, `crosses_rect`, grips) | Low | Fixes user-visible selection bugs |
| **P0** | Add tests for command classes (at least draw_line, modify_trim, modify_move) | Medium | Protects core functionality |
| **P1** | Extract geometry into `app/geometry.py`; remove cross-imports between commands | Medium | Reduces coupling, eases new entity types |
| **P1** | Refactor `CADCanvas` — extract `ViewportTransform`, `GridRenderer`, `InteractionManager` | High | Unlocks maintainability for the largest file |
| **P1** | Add CI pipeline (GitHub Actions: pytest + type checker) | Low | Prevents regressions |
| **P2** | Extend `_transform_entity()` to handle arc/radius cases; unify modify commands | Medium | Eliminates duplication in 3 files |
| **P2** | Add `__add__`/`__sub__`/`__mul__` operators to `Vec2` | Low | Cleans up arithmetic across entire codebase |
| **P2** | Centralise tolerances/settings into `EditorSettings` dataclass | Low | Consistency, user configurability |
| **P2** | Add `DynamicInputWidget` input-mode strategy pattern | Medium | Reduces 527-line god class |
| **P3** | Refactor `RibbonPanel.setup_document()` into binding objects | Medium | Testability, extensibility |
| **P3** | Add `mypy` / `pyright` config and fix type errors | Medium | Catches latent bugs at dev time |
| **P3** | Add structured logging | Low | Aids debugging and user bug reports |
| **P3** | Add entity ID index to `DocumentStore` | Low | Performance for large drawings |

---

*End of audit.*
