# OpenDraft — Codebase Audit (2026-04-30)

Findings-only report. Each item carries a severity (`P0` user-visible bug or
shipped stub, `P1` code-health issue, `P2` housekeeping / drift). No fix
recommendations are made here; the audit is intended to drive a follow-up
TODO sweep.

---

## Summary

| Severity | Count |
| :--- | ---: |
| P0 — user-visible bug / missing implementation | 8 |
| P1 — code health (orphans, swallowed exceptions, duplication, dead exports) | 32 |
| P2 — housekeeping / TODO.md drift | 11 |
| **Total** | **51** |

Top headline items:

- One scratch file (`editor_change.md`) sits in the repo root with stray Python at lines 49-54.
- One newly-added UI module (`app/ui/command_properties_popup.py`) has zero inbound references — it is wired up nowhere.
- Three entity types still ship with stubbed protocol methods (`HatchEntity.draw`, `HatchEntity.grip_points`/`move_grip`, `DimensionEntity.nearest_snap`, `TextEntity.nearest_snap`).
- 25+ `except`/silent-fail sites where Qt signal emissions, queue operations, and parser routines swallow exceptions with `pass` or a return-only fallback.
- `app/editor/__init__.py` re-exports two types (`ActionValidationReport`, `CommandCatalogRefreshResult`) that are not used by any consumer.
- 22 production command classes have no tests that reference them by class name; the AA-P0 entry "Command tests — draw commands" / "modify commands" is still open.

---

## P0 — User-visible bugs / shipped stubs

### P0-1 — `HatchEntity.draw` is a no-op stub
[app/entities/hatch.py:57-58](app/entities/hatch.py)

```python
def draw(self, painter, world_to_screen, scale: float) -> None:
    pass  # hatch fill rendering not yet implemented
```

A hatch entity present in a document will never appear on the canvas. Already tracked in `TODO.md` Priority 1 ("HatchEntity.draw()"); flagged here so it is captured in the active P0 list.

### P0-2 — `HatchEntity.grip_points` / `move_grip` not overridden
[app/entities/hatch.py](app/entities/hatch.py)

`HatchEntity` does not override `grip_points()` or `move_grip()` — both fall back to the `BaseEntity` defaults at [app/entities/base.py:380-393](app/entities/base.py), which return `[]` / no-op. A user cannot grip-edit a hatch.

### P0-3 — `DimensionEntity.nearest_snap` returns `None`
[app/entities/dimension.py:99-100](app/entities/dimension.py)

```python
def nearest_snap(self, cursor: Vec2) -> Optional[object]:
    return None
```

`DimensionEntity.snap_candidates` does emit endpoint snaps, but `nearest_snap` is the entry-point used during nearest-point projection; this stub means dimension geometry is not snappable in that mode.

### P0-4 — `TextEntity.nearest_snap` returns `None`
[app/entities/text.py:52-53](app/entities/text.py)

Same pattern as `DimensionEntity.nearest_snap`. `TextEntity.snap_candidates` returns the insertion point; `nearest_snap` is a stub.

### P0-5 — `HatchEntity.nearest_snap` returns `None`
[app/entities/hatch.py:51-52](app/entities/hatch.py)

Same stub.

### P0-6 — `DimensionEntity.crosses_rect` not overridden
[app/entities/dimension.py](app/entities/dimension.py)

No `crosses_rect` override — the entity falls back to `BaseEntity.crosses_rect` at [app/entities/base.py:363-374](app/entities/base.py), which uses an axis-aligned bounding-box intersection. This produces conservative (too-permissive) crossing-window selection for dimensions; users can pick dimensions in regions where no dimension geometry actually crosses the selection rectangle. (TODO.md/AA-P0 wording "silently skipped" is incorrect — they are *over*-selected, not skipped.)

### P0-7 — `TextEntity.crosses_rect` not overridden
[app/entities/text.py](app/entities/text.py)

Same as above. Falls back to bbox-only test.

### P0-8 — `editor_change.md` is a scratch file with stray Python
[editor_change.md](editor_change.md)

Lines 1-48 are legitimate design notes; lines 49-54 are pasted from a notebook and contain literal Python:

```49:54:editor_change.md
"""

# Save as MD file
file_name = "command_update.md"
with open(file_name, "w") as f:
    f.write(md_content)
```

The file is untracked in git. Either delete it or move the design notes into `Docs/` and strip the Python tail.

---

## P1 — Code health

### Orphaned / unused modules

#### P1-1 — `app/ui/command_properties_popup.py` has zero inbound references
[app/ui/command_properties_popup.py:186](app/ui/command_properties_popup.py)

Defines `class CommandPropertiesPopup(QFrame)` (~285 lines including styling) but the symbol is not imported by `main_window.py`, `canvas.py`, `top_terminal.py`, `properties_panel.py`, or any test. The file is untracked in git. Either it is in-flight work or fully orphaned.

#### P1-2 — `app/editor/stateful_command.py` has only a single live consumer
[app/editor/stateful_command.py](app/editor/stateful_command.py)

`StatefulCommandBase` is the new GUI-thread command base, but the only command currently subclassing it is `DrawLineCommand` ([app/commands/draw_line.py](app/commands/draw_line.py)). The migration of other commands has not yet happened, so the rest of the framework (export descriptors, `advance_active_export`, `command_properties_popup` UI, `properties_panel` integration) is exercised by exactly one path in production. Treat as a "partially landed feature" rather than dead code.

### Swallowed exceptions — `except: pass` / empty body

The following sites silently discard errors. Each is listed once; "wraps" describes the operation that fails silently.

| Severity | Location | Wraps |
| :--- | :--- | :--- |
| P1-3  | [app/canvas.py:240](app/canvas.py)  | `editor.input_mode_changed.connect` in canvas constructor |
| P1-4  | [app/canvas.py:418](app/canvas.py)  | `mouseMoved.emit` during active grip drag |
| P1-5  | [app/canvas.py:466](app/canvas.py)  | `mouseMoved.emit` after resolving display point |
| P1-6  | [app/canvas.py:605](app/canvas.py)  | `MainWindow.open_properties_panel` from context menu |
| P1-7  | [app/canvas.py:767](app/canvas.py)  | `terminalKeyEvent.emit` forwarding |
| P1-8  | [app/main_window.py:255](app/main_window.py) | `canvas.mouseMoved.connect` for status bar / properties cursor |
| P1-9  | [app/ui/top_terminal.py:468](app/ui/top_terminal.py) | `unpolish/polish` match-button stylesheet refresh |
| P1-10 | [app/editor/editor.py:502](app/editor/editor.py) | `cmd.cancel()` in `cancel_command` |
| P1-11 | [app/commands/modify_helpers.py:126](app/commands/modify_helpers.py) | `setattr` while applying undo snapshot to live entity |
| P1-12 | [app/commands/modify_helpers.py:228](app/commands/modify_helpers.py) | `setattr` while applying transform snapshot to live entity |

These ten sites are the highest-risk: they sit on the GUI-thread signal/slot path or on undo-snapshot restore. Failures here will silently corrupt UI state or undo history with no log.

The following are also `pass`-only but are intentional control-flow handlers; they are listed for completeness but lower priority:

| Location | Kind | Wraps |
| :--- | :--- | :--- |
| [app/document.py:167](app/document.py) | `except RuntimeError: pass` | Disconnect signal that is not connected (commented) |
| [app/editor/editor.py:455, 459, 1236, 1241](app/editor/editor.py) | `except queue.Empty/Full: pass` | Input queue edge cases (race-safe) |
| [app/editor/editor.py:1177](app/editor/editor.py) | `except CommandCancelled: pass` | Worker thread normal-cancel path |
| [app/commands/draw_point.py:17](app/commands/draw_point.py), [app/commands/draw_spline.py:36](app/commands/draw_spline.py) | `except CommandCancelled: pass` | Exit pick loops |
| [app/ui/properties_panel.py:393, 452](app/ui/properties_panel.py), [app/ui/command_properties_popup.py:180](app/ui/command_properties_popup.py), [app/ui/top_terminal.py:691, 699, 707, 715](app/ui/top_terminal.py) | `except ValueError: pass` | Numeric parser failures from user input |

### Stderr-only / log-only handlers (no surfacing)

| Severity | Location | Wraps |
| :--- | :--- | :--- |
| P1-13 | [app/canvas.py:1102](app/canvas.py) | `entity.draw` in `_draw_entity` — `traceback.print_exc()` only |
| P1-14 | [app/canvas.py:1241](app/canvas.py) | `entity.draw` in thumbnail export — `traceback.print_exc()` only |
| P1-15 | [app/editor/stateful_command.py:81](app/editor/stateful_command.py) | Export-descriptor `update()` call — `traceback.print_exc()` only |

These three printed-traceback sites bypass the `_log` logger entirely and emit to stderr, so failures inside an entity's `draw()` go to the console (where most users will never look) instead of the rotating log file configured by `app/logger.py`.

### Silent-return / fallback handlers (worth noting)

| Severity | Location | Wraps |
| :--- | :--- | :--- |
| P1-16 | [app/editor/editor.py:906](app/editor/editor.py) | `get_dynamic` preview callback — `return []` on any exception |
| P1-17 | [app/canvas.py:25](app/canvas.py) | `_resolve_color_str` — falls back to `QColor(color_str)` on any exception |
| P1-18 | [app/canvas.py:574](app/canvas.py) | Context-menu hit-test — `clicked_id = None` on any exception |
| P1-19 | [app/canvas.py:734](app/canvas.py) | `escapePressed.emit` failure — silently runs local `handle_escape()` |
| P1-20 | [app/ui/top_terminal.py:591, 629](app/ui/top_terminal.py) | `provide_command_option` / `event.key()` — bare `except Exception` |

### Unused imports / dead exports

#### P1-21 — Unused `QObject`, `QEvent` imports in `main_window.py`
[app/main_window.py:19](app/main_window.py)

```python
from PySide6.QtCore import Qt, QObject, QEvent
```

`Qt` is used; `QObject` and `QEvent` appear nowhere else in the file.

#### P1-22 — `__all__` exports nothing imports
[app/editor/__init__.py:65-104](app/editor/__init__.py)

The following names are listed in `__all__` but have **zero** uses outside `app/editor/`:

- `ActionValidationReport` — only defined / referenced inside `app/editor/command_registry.py` and re-exported by `__init__.py`.
- `CommandCatalogRefreshResult` — same.

The following are exported but only have a single external consumer (`app/main_window.py` or one test); flagged so the export surface is reviewed:

- `unregister_commands_by_source` — single test consumer ([tests/test_command_catalog_refresh.py:59](tests/test_command_catalog_refresh.py)); also called internally by `refresh_command_catalog`.
- `command_catalog_version` — single test consumer ([tests/test_command_catalog_refresh.py:28](tests/test_command_catalog_refresh.py)).
- `registered_commands`, `unregister_command` — referenced only inside `app/editor/` and the `__init__` re-export list; effectively editor-internal.
- `SnapResult`, `SnapType` re-exported from `app.editor` — every external consumer imports them from `app.editor.osnap_engine` or `app.entities.snap_types`, not from `app.editor`.

#### P1-23 — Unused imports in tests
[tests/conftest.py:12, 19](tests/conftest.py)

- `BaseEntity`, `BBox` (line 12) and `SnapResult` (line 19) are imported but not used in `conftest.py`.

[tests/test_hit_testing.py:8-9](tests/test_hit_testing.py)

- `CircleEntity` and `RectangleEntity` are imported but not used; the file only exercises line fixtures.

### Duplication / inconsistency

#### P1-24 — Inconsistent `Vec2` import paths
Across `app/` and `tests/` `Vec2` is sometimes imported via the package barrel (`from app.entities import Vec2`) and sometimes directly from the implementation module (`from app.entities.base import Vec2`). Examples of each style coexist in the same areas (e.g. [app/editor/hit_testing.py](app/editor/hit_testing.py), [app/entities/dimension.py](app/entities/dimension.py), [app/editor/draftmate.py](app/editor/draftmate.py) use `app.entities.base`; most other modules use `app.entities`). Same class, two paths.

#### P1-25 — Repeated `copy.deepcopy` snapshot patterns without a shared helper
The pattern "deep-copy entity → mutate → push undo" is open-coded in five+ places without a shared helper:

- [app/canvas_grip_flow.py:97-98, 136, 171](app/canvas_grip_flow.py) — grip drag snapshots
- [app/commands/modify_helpers.py:41, 213](app/commands/modify_helpers.py)
- [app/commands/modify_move.py:45, 65](app/commands/modify_move.py)
- [app/commands/modify_mirror.py:22](app/commands/modify_mirror.py)
- [app/commands/modify_offset.py:29, 42, 52, 95](app/commands/modify_offset.py)
- [app/document.py:298](app/document.py)

These are not bug-equivalent but they are the most likely site for a future inconsistency (e.g. shallow-vs-deep copy drift).

#### P1-26 — Elliptical-arc UI gap
[app/entities/ellipse.py:19-35](app/entities/ellipse.py) supports `start_param`/`end_param` for arcs, but [app/commands/draw_ellipse.py:57-62](app/commands/draw_ellipse.py) only commits a full ellipse. The model is half-implemented relative to the draw command. (TODO.md marks "Ellipse — include elliptical arcs" as `[x]` complete; the entity ships, the user-facing draw command does not.)

### Test coverage gaps

#### P1-27 — Production commands have no class-level tests
Grep for any production command class name under `tests/` returns zero hits. The 22 commands below have no test that imports their class:

`DrawLineCommand`, `DrawCircleCommand`, `DrawArcCenterStartEndCommand`, `DrawArcStartEndRadiusCommand`, `DrawArc3PointCommand`, `DrawRectCommand`, `DrawPolylineCommand`, `DrawTextCommand`, `DrawSplineCommand`, `DrawEllipseCommand`, `DrawPointCommand`, `LinearDimensionCommand`, `AlignedDimensionCommand`, `MoveCommand`, `CopyCommand`, `RotateCommand`, `ScaleCommand`, `MirrorCommand`, `DeleteCommand`, `TrimCommand`, `ExtendCommand`, `OffsetCommand`, `FilletCommand`, `ChamferCommand`.

`tests/test_editor.py` does run `moveCommand`, `copyCommand`, `rotateCommand`, `scaleCommand` end-to-end via `Editor.run_command(action_name)` — partial coverage by string action-name, not by class. This matches `TODO.md` AA-P0 entries "Command tests — draw commands" / "Command tests — modify commands"; both are still open.

#### P1-28 — Entity-method coverage gaps
Currently exercised by `tests/test_entities.py` and `tests/test_hit_testing.py`:

- `nearest_snap` — `LineEntity`, `CircleEntity`, `RectangleEntity`, `PolylineEntity` only.
- `crosses_rect` — `LineEntity`, `CircleEntity`, `BaseEntity` defaults; plus the line fixture in `test_hit_testing.py`.

**Not** referenced from any test:

- `nearest_snap` — `ArcEntity`, `EllipseEntity`, `PointEntity`, `SplineEntity`, `TextEntity`, `HatchEntity`, `DimensionEntity`.
- `crosses_rect` — `RectangleEntity`, `PolylineEntity`, `ArcEntity`, `EllipseEntity`, `SplineEntity`, `PointEntity`, `TextEntity`, `HatchEntity`, `DimensionEntity`.
- `draw` — none of the concrete entities (every test either runs through the editor or the canvas paint cache).
- `grip_points` — none of the concrete entities.

### Logging

#### P1-29 — Three diagnostic sites use `traceback.print_exc()` instead of `_log`
See P1-13, P1-14, P1-15 above. `app/logger.py` configures a rotating file handler; these sites bypass it.

#### P1-30 — TODO.md asks for "structured logging"; current logger is plain
[app/logger.py](app/logger.py)

`configure_logging()` sets up a standard `logging.Formatter`-based pipeline with a rotating file plus console handler. TODO.md's "Logging — structured application log with levels" item is partially satisfied (levels, rotation) but not "structured" in the JSON / structlog sense some teams expect. Marked here so the TODO entry can be closed precisely or rewritten.

### Misc

#### P1-31 — Missing `Space` repeat-last-command path
[TODO_COMPLETED.md:6-7](TODO_COMPLETED.md) and [TODO.md:167](TODO.md) describe Enter **or** Space repeating the last command on an empty canvas. Only `Key_Return` is wired in [app/ui/top_terminal.py:601-608](app/ui/top_terminal.py); a Grep for `Key_Space` under `app/` returns zero hits. Either the feature description should be tightened or the binding added.

#### P1-32 — `app/sdk/commands/api.py` only-loaded by sibling
[app/sdk/commands/api.py](app/sdk/commands/api.py)

The only inbound import is from [app/sdk/commands/__init__.py](app/sdk/commands/__init__.py)'s lazy loader (`register` / `command`). No external module imports `app.sdk.commands.api` directly; consumers go through `context` / `spec`. Likely intentional (façade pattern), flagged so the indirection is documented.

---

## P2 — TODO.md drift / housekeeping

### TODO.md items still marked `[ ]` that already have an implementation

#### P2-1 — "Crossing window vs enclosing window"
[TODO.md:68](TODO.md) marks this as still open, but the behaviour is already wired in [app/canvas_interaction.py:68-70](app/canvas_interaction.py) (`is_window_selection`) and consumed by [app/canvas.py:812-824](app/canvas.py).

#### P2-2 — "Properties palette"
[TODO.md:92](TODO.md) marks this as still open. The implementation is the docked `PropertiesPanel` at [app/ui/properties_panel.py](app/ui/properties_panel.py) (53 KB) wired in [app/main_window.py:258-270](app/main_window.py) as `_props_dock` with `togglePropertiesPanel`.

### TODO.md items marked `[x]` that look incomplete or imprecise

#### P2-3 — "Spline / Bezier" complete (P2-3 is informational)
Entity at [app/entities/spline.py](app/entities/spline.py) and command at [app/commands/draw_spline.py](app/commands/draw_spline.py) confirmed; `[x]` is correct.

#### P2-4 — "Ellipse — include elliptical arcs" partially complete
See P1-26: entity supports arc params; draw command does not.

#### P2-5 — "Repeat last command — Enter or Space" partially complete
See P1-31: only Enter is wired.

### Confirmed still missing (matches `[ ]` in TODO.md)

These were re-verified against the code; the TODO entries are accurate:

- Construction Line (Xline / Ray) — no `XlineEntity`/`RayEntity`.
- Divide / Measure (along entity) commands — none.
- Stretch / Break / Join / Explode commands — none.
- Array (Rectangular / Polar) — none.
- Lengthen / Shorten — none.
- Select All (`Ctrl+A`) — no shortcut binding in [app/main_window.py](app/main_window.py).
- Quick Properties tooltip — none.
- Match Properties — none.
- Layer lock / freeze — `Layer` dataclass in [app/document.py](app/document.py) only has `visible`.
- Linetype loading from `.lin` files — no parser.
- Zoom Extents / Zoom All / Zoom Window — no implementation.
- Cursor crosshair (full-screen) — only `Qt.CursorShape.CrossCursor`, not a painted full-viewport crosshair.
- Settings persistence — no `QSettings`/config-file persistence found.

### Misc housekeeping

#### P2-6 — `editor_change.md` should not live at repo root
See P0-8. Move to `Docs/` or delete.

#### P2-7 — Two new modules untracked in git without tests
`app/editor/stateful_command.py` and `app/ui/command_properties_popup.py` (per the snapshot `git status`) introduce new public surface without dedicated test files.

#### P2-8 — `app/editor/__init__.py` re-export list to be reviewed
See P1-22.

#### P2-9 — `Vec2` import-style inconsistency
See P1-24. Pick one canonical import path and (optionally) lint-enforce it.

#### P2-10 — Conftest / hit-testing test imports are dead
See P1-23.

#### P2-11 — `TODO.md` "Audit Actions" wording for P0 selection bugs is imprecise
The "Dimension/Text entities silently skipped by selection" wording in [TODO.md:234-237](TODO.md) does not match observed behaviour — both fall back to bbox-AABB selection (over-permissive), they are not skipped. Update the wording when the issue is closed.

---

## Appendix A — Per-file findings index

| File | Findings |
| :--- | :--- |
| `editor_change.md` | P0-8, P2-6 |
| `app/canvas.py` | P1-3, P1-4, P1-5, P1-6, P1-7, P1-13, P1-14, P1-17, P1-18, P1-19 |
| `app/main_window.py` | P1-8, P1-21 |
| `app/document.py` | (informational only — `RuntimeError pass` at 167) |
| `app/editor/editor.py` | P1-10, P1-16 |
| `app/editor/stateful_command.py` | P1-2, P1-15 |
| `app/editor/__init__.py` | P1-22, P2-8 |
| `app/entities/hatch.py` | P0-1, P0-2, P0-5 |
| `app/entities/dimension.py` | P0-3, P0-6 |
| `app/entities/text.py` | P0-4, P0-7 |
| `app/entities/ellipse.py` | P1-26 |
| `app/commands/modify_helpers.py` | P1-11, P1-12, P1-25 |
| `app/commands/modify_move.py` | P1-25 |
| `app/commands/modify_mirror.py` | P1-25 |
| `app/commands/modify_offset.py` | P1-25 |
| `app/commands/draw_ellipse.py` | P1-26 |
| `app/commands/*` (22 classes) | P1-27 |
| `app/canvas_grip_flow.py` | P1-25 |
| `app/ui/top_terminal.py` | P1-9, P1-20, P1-31 |
| `app/ui/command_properties_popup.py` | P1-1, P2-7 |
| `app/sdk/commands/api.py` | P1-32 |
| `tests/conftest.py` | P1-23, P2-10 |
| `tests/test_hit_testing.py` | P1-23, P2-10 |
| `tests/test_entities.py` (gaps) | P1-28 |
| `app/logger.py` | P1-30 |

---

## Appendix B — Methodology

### Tools used

- Static grep / glob via repository-wide patterns (no Python execution).
- Manual reads of key files: `app/canvas.py` (~1260 lines), `app/editor/editor.py` (~1262 lines), `app/entities/base.py`, every `app/entities/*.py`, every `app/commands/*.py`, `app/main_window.py`, `app/ui/properties_panel.py` (selected ranges), `app/ui/top_terminal.py` (selected ranges), `app/editor/__init__.py`, `app/editor/command_registry.py`, plus all test files.
- Cross-reference of `__all__` exports against repo-wide imports.
- Verification of TODO.md state by code search for each implementation symbol.

### Files / directories explicitly **not** audited

- `.venv/`, `.venv-ci/`, `.pytest_cache/`, `__pycache__/`, `.xdg-runtime/`, `assets/`, `Docs/` (docs, not code), `LICENSE`, `pyproject.toml`/`requirements.txt` (intentionally minimal — no orphan dependencies surveyed).
- `controls/` (Qt ribbon toolkit) — confirmed inbound from `app/ribbon_bridge.py` and `app/main_window.py`; internal layout not audited.
- `scripts/` — confirmed Linux thumbnailer / CI helpers; not audited beyond purpose.

### Deliberate non-goals

- No fix recommendations are included (per audit scope: findings only).
- No architectural review (out of standard scope).
- No `TODO.md` updates were made.
- No code edits.
