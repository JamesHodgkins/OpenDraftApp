# OpenDraft — Development TODO

A prioritized list of missing features, unimplemented stubs, and future improvements.

Once tasks are complete, they are purged over to TODO_COMPLETED.md for record.

Tracking note (2026-04-24): Undo entity index sync regression fix logged in TODO_COMPLETED.md.
Tracking note (2026-04-24): Move/Copy displacement input now uses base-point vector semantics for Ortho and dynamic vector entry; details logged in TODO_COMPLETED.md.
Tracking note (2026-04-24): Added fallback vector rubberband visual feedback for base-point point input; details logged in TODO_COMPLETED.md.
Tracking note (2026-04-24): Vector rubberband now remains visible even when command-specific preview entities are active.
Tracking note (2026-04-24): Rotate/Scale commands now use vector point input flow (with retained angle/factor options) for ortho and rubberband consistency.
Tracking note (2026-04-24): Rotate base vector now defines the effective zero-axis for standard rotation-vector picks.
Tracking note (2026-04-24): Rotate prompts/options now explicitly indicate when input is relative to the base vector reference axis.
Tracking note (2026-04-25): Continued CADCanvas decomposition by extracting rendering and pen-resolution helpers into `app/canvas_painting.py`; validated with full `pytest` pass.
Tracking note (2026-04-25): Normalized PySide6 enum usage and nullable typing in `app/canvas.py` to clear Pylance errors (for example `Qt.MouseButton`, `Qt.CursorShape`, `Qt.Key`) with canvas tests passing.
Tracking note (2026-04-25): Continued CADCanvas decomposition by extracting cursor/selection/hit-testing interaction rules into `app/canvas_interaction.py`; validated with full `pytest` pass.
Tracking note (2026-04-25): Continued CADCanvas decomposition by extracting command-mode snap/draftmate/input gating flow into `app/canvas_command_flow.py`; validated with full `pytest` pass.
Tracking note (2026-04-25): Continued CADCanvas decomposition by extracting grip-edit lifecycle logic into `app/canvas_grip_flow.py`; validated with full `pytest` pass.

---

## Priority 1 — Complete Existing Stubs

These buttons or commands already exist in the UI or codebase but have no implementation.


### Hatch

- [ ] **HatchEntity.draw()** — render the hatch fill on the canvas (crosshatch, ANSI31, solid fill, etc.) using QPainter clipping paths and tiled line patterns
- [ ] **Draw Hatch command** — pick a closed boundary (or select existing closed entity), choose pattern/scale/angle, create HatchEntity
- [ ] **Pick Hatch command** — click an existing hatch entity to edit its properties in-place
- [ ] **Associative hatches** — re-compute hatch fill when the boundary entity is modified via grips

### Dimension Rendering

- [x] **DimensionEntity.draw()** — render extension lines, dimension line, arrowheads, and the measurement text on the canvas
- [ ] **Dimension styles** — arrowhead type (filled triangle, tick, dot), text height, offset distances, precision (decimal places), units suffix

### Measurements

- [ ] **Measure Angle** — pick vertex point, then two leg points; display angle in dynamic input / status bar

### Export

- [ ] **Export PDF** — render the current document to a PDF using QPrinter or `reportlab`; respect paper size and scale
- [ ] **Export SVG** — convert all entities to SVG primitives via `svgwrite` or Qt's SVG generator

---

## Priority 2 — Core Missing CAD Features

Standard 2D CAD operations that are entirely absent.

### Drawing Commands

- [x] **Spline / Bezier** — pick control points, smooth curve through them; essential for organic geometry
- [x] **Ellipse** — center + two axis points; include elliptical arcs
- [x] **Point / Node** — place a single point entity (useful as construction geometry and for DIVIDE / MEASURE)
- [ ] **Construction Line (Xline / Ray)** — infinite or semi-infinite lines used as guides
- [x] **Offset** — select entity, input offset distance; create a parallel copy at that distance (works for lines, arcs, polylines, circles)
- [x] **Fillet** — round a corner between two edges with a given radius; radius = 0 gives a sharp trim-to-corner
- [x] **Chamfer** — bevel a corner between two edges by specified distances or angle
- [ ] **Divide** — place N evenly spaced point entities along an entity
- [ ] **Measure (along entity)** — place point entities at specified interval along an entity

### Editing

- [ ] **Stretch** — move only the grips that fall inside a crossing selection window; the rest of the entity stays fixed
- [ ] **Break** — pick two points on an entity to remove the segment between them (`BREAK` command)
- [ ] **Join** — merge collinear lines, coaxial arcs, or open polylines into a single entity
- [ ] **Explode** — decompose a complex entity (polyline, rectangle, dimension) into its constituent primitives
- [ ] **Array (Rectangular)** — repeat selected entities in a grid of rows and columns
- [ ] **Array (Polar)** — repeat selected entities radially around a center point
- [ ] **Lengthen / Shorten** — adjust the length of a line or arc by a delta, percent, or to a total value

### Selection Enhancements

- [ ] **Crossing window** (right-to-left drag) vs **enclosing window** (left-to-right) — currently only one mode is active
- [ ] **Select All** (`Ctrl+A`)
- [ ] **Invert Selection** — deselect selected, select everything else
- [ ] **Select by Layer** — select all entities on a specified layer
- [ ] **Select by Property** — filter by color, linetype, line thickness
- [ ] **Quick Select (QSelect)** — dialog to build a selection set from property filters
- [ ] **Selection cycling** — when clicking overlapping entities, cycle through candidates with repeated clicks

### Object Snapping

- [ ] **Intersection snap** — snap to the intersection of any two entities
- [ ] **Apparent Intersection** — snap to the visual intersection of entities that don't share a plane
- [ ] **Quadrant snap** — snap to 0°, 90°, 180°, 270° points on circles and arcs
- [ ] **Tangent snap** — snap to the tangent point from cursor to a circle or arc
- [ ] **Node snap** — snap to point entities
- [ ] **Extension snap** — follow the projected path of a line or arc beyond its endpoints
- [ ] **OSNAP priority / filter settings** — let the user toggle individual snaps on/off

---

## Priority 3 — Properties & Layers

### Properties Panel / Inspector

- [ ] **Properties palette** — a docked sidebar listing the selected entity's properties (layer, color, linetype, coordinates, radius, etc.) with editable fields
- [ ] **Quick Properties** — a small floating tooltip showing key properties on hover or selection
- [ ] **Match Properties** (`MATCHPROP`) — copy properties from one entity to others

### Layer Enhancements

- [ ] **Layer lock** — prevent editing entities on a locked layer while keeping them visible
- [ ] **Layer freeze/thaw** — frozen layers are not rendered at all (performance)
- [ ] **Layer current** indicator — highlight the active layer clearly in the manager
- [ ] **Layer filters** — group layers by name prefix or property for large drawings
- [ ] **Layer states** — save/restore the visibility, lock, and freeze state of all layers by name
- [ ] **Linetype loading** — load standard ISO/ANSI linetype definitions from a `.lin` file; render dashes and dots at the correct world-space scale

### Entity Property Override

- [ ] **ByLayer / ByBlock** — entities inherit color and linetype from their layer (already partially implemented); make this explicit in the UI
- [ ] **Per-entity color, linetype, thickness** — override at the entity level without changing the layer

---

## Priority 4 — Views & Layout

### Viewport & Navigation

- [ ] **Named Views** — save and restore viewport position, zoom level, and UCS by name (`VIEW` command)
- [ ] **Zoom commands** — Zoom Extents, Zoom All, Zoom Previous, Zoom Window
- [ ] **Fit to window** — keyboard shortcut to fit all entities on screen
- [ ] **Rotate view / UCS** — work in a rotated coordinate system
- [ ] **Coordinate system indicator** — display current UCS origin and axes on canvas

### Paper Space / Layouts

- [ ] **Layout tabs** — switch between Model Space and named Paper Space layouts
- [ ] **Viewport entities** (`MVIEW`) — place one or more scaled viewports on a layout sheet
- [ ] **Viewport scale** — set a precise drawing scale (e.g., 1:50) for each viewport
- [ ] **Print/Plot dialog** — configure paper size, scale, pen widths, and print area

---

## Priority 5 — Annotation & Text

- [ ] **Multiline Text (MText)** — rich text block with word wrap, embedded formatting (bold, italic, underline)
- [ ] **Leaders / Multileader** — arrow pointing to an entity with an attached text or block label
- [ ] **Annotation Scales** — scale-aware text and dimension sizes that display consistently across different viewport scales
- [ ] **Table entity** — grid of rows and columns with text cells (for BOMs, title blocks)
- [ ] **Fields** — dynamic text that displays document properties (filename, date, total length, area)

### Dimension Types

- [ ] **Angular dimension** — arc between two line entities showing the included angle
- [ ] **Radial dimension** — radius line with label for circles/arcs
- [ ] **Diameter dimension** — diameter line with Ø prefix for circles
- [ ] **Ordinate dimension** — X or Y coordinate annotation from a datum
- [ ] **Continuous dimension** — chain multiple linear dimensions end-to-end in one command
- [ ] **Baseline dimension** — stack multiple dimensions from a common baseline

---

## Priority 6 — File Formats & Interoperability

- [ ] **DXF import** — read AutoCAD DXF files (via `ezdxf`) and populate the document store; at minimum support R12 entities (LINE, CIRCLE, ARC, TEXT, LWPOLYLINE, INSERT)
- [ ] **DXF export** — write the current document to DXF; enables round-tripping with AutoCAD/LibreCAD/FreeCAD
- [ ] **SVG import** — read basic SVG shapes into the document
- [ ] **Recent files** — remember the last N opened files; display in File menu
- [ ] **Auto-save / backup** — periodically save a recovery copy to a temp location

---

## Priority 7 — UX & Workflow

### Command Experience

- [ ] **Command line / prompt bar** — a text field at the bottom where users can type command names (e.g., `LINE`, `CIRCLE`) and sub-options, mirroring AutoCAD muscle memory
- [ ] **Command aliases** — short aliases (`L` → Line, `C` → Circle, `M` → Move, etc.)
- [ ] **Repeat last command** — pressing `Enter` or `Space` on an empty canvas repeats the previous command
- [ ] **Command history** — scrollable log of recently executed commands and prompts

### Keyboard Shortcuts

- [ ] **F1** — Help
- [ ] **F2** — Toggle command history window
- [ ] **F3** — Toggle OSNAP on/off (currently F8 is Ortho, F10 is Draftmate)
- [ ] **Ctrl+Z / Ctrl+Y** — Undo/Redo (check current binding)
- [ ] **Ctrl+S / Ctrl+Shift+S** — Save / Save As
- [ ] **Ctrl+N / Ctrl+O** — New / Open
- [ ] **Delete key** — delete selected entities
- [ ] **Escape** — cancel in-progress command or clear selection (already implemented; verify both cases)

### Usability

- [ ] **Tooltip previews** — show a small icon or description when hovering over ribbon buttons
- [x] **Ribbon quick colour popup** — clicking the ribbon colour swatch should show a compact palette (common colours + ByLayer) with an option to open the full colour picker
- [ ] **Context menu extensions (right-click on canvas)** — add recent commands and richer entity-specific options (core context menu + command options are already implemented)
- [ ] **Context menu on entity (right-click)** — Properties, Delete, Move, Copy, etc.
- [ ] **Grip editing improvements** — show grip count, support multi-grip drag with relative offset
- [ ] **Cursor crosshair** — replace default cursor with a full-screen crosshair during drawing commands
- [ ] **Transparent commands** — allow zoom/pan during another active command without cancelling it (already partially working; audit edge cases)

---

## Priority 8 — Blocks & Symbols

- [ ] **Block definition** — select a group of entities and save them as a named block
- [ ] **Block insertion (`INSERT`)** — place a block instance with X/Y scale and rotation
- [ ] **Block editing (`BEDIT`)** — in-place editor to modify block geometry
- [ ] **Attributes** — text fields attached to blocks that can be filled in per-insertion (e.g., part number on a symbol)
- [ ] **Symbol library** — a palette of pre-built blocks (electrical, mechanical, architectural symbols) the user can drag-and-drop

---

## Priority 9 — Quality & Robustness

### Testing

- [ ] **Unit tests for all entity types** — draw(), bbox, snap points
- [ ] **Unit tests for all commands** — simulate point input via the queue; check resulting document state
- [ ] **Integration tests** — open a JSON document, run a modification command, re-save, compare
- [ ] **Regression suite** — a set of golden reference drawings to catch rendering regressions

### Performance

- [ ] **Spatial index (R-tree / quadtree)** — accelerate hit testing and OSNAP search on large drawings (thousands of entities)
- [ ] **Partial redraws** — only repaint the dirty region of the canvas rather than the full viewport
- [ ] **Entity caching** — cache QPainterPath per entity and invalidate only on change

### Code Health

- [ ] **Typed entity registry** — replace string-keyed command/entity lookups with a proper registry pattern
- [ ] **Error handling** — graceful recovery when loading a malformed JSON document
- [ ] **Logging** — structured application log with levels (DEBUG, INFO, WARNING) for diagnosing field issues
- [ ] **Settings persistence** — save user preferences (OSNAP toggles, grid visibility, theme) to a config file between sessions

---

## Audit Actions

Issues identified in `AUDIT.md` (2026-04-18). Grouped by priority matching the audit report.

### AA-P0 — Bug Fixes (User-Visible)

- [ ] **`DimensionEntity.crosses_rect()`** — implement window/crossing selection support; currently missing, causing Dimension entities to be silently skipped by all selection operations
- [ ] **`TextEntity.crosses_rect()`** — same gap as DimensionEntity; Text entities cannot be selected via drag window
- [ ] **`HatchEntity.grip_points()` / `move_grip()`** — both methods are absent; hatch entities cannot be grip-edited
- [ ] **`DimensionEntity.nearest_snap()`** — currently returns `None` with a stub comment; implement proper nearest-point projection across the three dimension points
- [ ] **Command tests — draw commands** — add `test_commands.py` covering at minimum: `DrawLineCommand`, `DrawCircleCommand`, `DrawArcCommand`, `DrawRectCommand`; simulate point input via the editor queue and assert resulting document state
- [ ] **Command tests — modify commands** — cover `MoveCommand`, `CopyCommand`, `RotateCommand`, `ScaleCommand`, `MirrorCommand`, `TrimCommand`, `ExtendCommand`, `DeleteCommand`; verify undo/redo round-trip for each

### AA-P1 — Architecture

- [x] **Extract `app/geometry.py`** — consolidated arc/intersection helpers from `modify_trim.py` into `app/geometry.py`; `modify_extend.py` now imports from `app.geometry` instead of the brittle `from app.commands.modify_trim import ...` cross-import; base `_geo_*` helpers re-exported from `app.geometry` for a single import site
- [x] **Refactor `CADCanvas`** — extracted `ViewportTransform` → `app/canvas_viewport.py` (pan/zoom, screen↔world, origin anchor), `GridRenderer` → `app/canvas_grid.py` (adaptive multi-level grid), rendering/pen helpers → `app/canvas_painting.py` (OSNAP marker, Draftmate guides, grips, selection rectangle, vector rubberband, base/overlay pen composition), interaction-rule helpers → `app/canvas_interaction.py` (point resolution, drag thresholding, selection matching, grip/entity hit detection), command-flow helpers → `app/canvas_command_flow.py` (snap/draftmate/input gating), and grip lifecycle helpers → `app/canvas_grip_flow.py` (activate, preview drag, commit/reset); canvas delegates via proxy properties and thin wrapper methods
- [x] **CI pipeline** — added `.github/workflows/ci.yml` running `pytest` (headless via `QT_QPA_PLATFORM=offscreen`) and `pyright` type-check on every push and PR

### AA-P1b — Command API / Plugin Architecture

- [x] **Create a stable command SDK layer** — added `app/sdk/commands` with public `CommandContext`, `CommandSpec`, and registration decorators (`@command`, `@register`) that route through the core registry
- [x] **Adopt metadata-rich command specs** — registry now supports metadata-rich `@command(...)` fields and merges ribbon-derived `CommandSpec` metadata (id/display name/description/category/aliases/icon/source/min API version) into core command specs
- [x] **Enforce command namespacing and collision policy** — command IDs are now canonicalized to namespaced form (`core.*` for legacy core IDs) and registry registration fails fast on command-id/alias collisions
- [x] **Add plugin discovery via Python entry points** — startup now loads built-ins via `app.commands` autodiscovery and external plugins via `autodiscover_entry_points("opendraft.commands")`
- [x] **Implement action resolution + startup validation** — added generic action-source validators and startup ribbon-action validation logging against local handlers plus registered commands
- [x] **Expose high-level command helpers** — added public `EditorTransaction`, `Editor.preview()` / `Editor.highlighted()`, `Editor.push_undo_command()` / `Editor.notify_document()`, and SDK `CommandContext` wrappers; migrated modify commands off direct `editor._undo_stack` usage
- [x] **Support command catalog refresh** — added command-catalog snapshot/version APIs plus non-core unregister + plugin reload refresh flow; `MainWindow.refresh_command_catalog()` now repopulates command pickers from the refreshed catalog
- [x] **Add command-architecture contract tests** — added `tests/test_command_architecture_contract.py` covering cancellation lifecycle reset, start-after-cancel behavior, helper undo/redo guarantees, and alive-thread start guard; validated alongside existing collision/plugin/action suites

### AA-P2 — Technical Debt

- [x] **`Vec2` arithmetic operators** — add `__add__`, `__sub__`, `__mul__` (scalar), `__truediv__` (scalar), and a `distance_to(other)` convenience method; eliminates inline `dx/dy` boilerplate repeated throughout commands and entities
- [x] **Unify modify-command transform logic** — extend `_transform_entity()` in `modify_helpers.py` to accept an optional post-transform hook for arc-angle and radius mutations; update `RotateCommand`, `ScaleCommand`, and `MirrorCommand` to use the shared helper instead of reimplementing entity-type dispatch locally
- [x] **`EditorSettings` dataclass** — centralise all hardcoded tolerances and thresholds (pick tolerance 7 px, grip pick 7 px, OSNAP aperture 15 px, trim/extend tolerance 10–20 px) into a single settings object passed through the constructor chain; expose relevant values to the preferences UI
- [x] **`DynamicInputWidget` strategy pattern** — replace the 7-mode monolith (527 lines) with one `InputMode` strategy subclass per mode (`PointMode`, `IntegerMode`, `FloatMode`, `StringMode`, `ChoiceMode`, `AngleMode`, `LengthMode`); the widget delegates validation, placeholder computation, and rendering to the active strategy
- [x] **Serialisation migration layer** — `DocumentStore.from_dict()` reads the `version` field but takes no action on it; add a `_migrate(d, version)` step so old JSON files with missing or renamed fields are upgraded to the current schema rather than silently producing broken entities

### AA-P3 — Maintainability

- [x] **`RibbonPanel.setup_document()` refactor** — extracted all domain logic into `app/ribbon_bridge.py` (`RibbonDocumentBridge`); ribbon now emits `colorChangeRequested`, `lineStyleChanged`, `lineWeightChanged`, `layerChanged` signals; public methods (`set_swatch_color`, `populate_layers`, etc.) replace direct document access; `RibbonPanel` in `ribbon_panel_widget.py` renamed to `RibbonPanelFrame` to resolve name collision; overflow chevron added via `_OverflowTabContent` for adaptive panel layout
- [x] **`LayerManagerDialog._append_row()` refactor** — reviewed: six genuinely different cell types; `_on_style_change` / `_on_weight_change` are already named methods, not anonymous lambdas; all mutations already route through `Editor.set_layer_property`. A `LayerRowBuilder` extract would increase indirection without reducing coupling. No change warranted.
- [x] **Pyright / mypy configuration** — added `pyrightconfig.json` in standard mode; fixed `snap_candidates()`, `nearest_snap()`, `perp_snaps()`, and `draw()` annotations in `ArcEntity` (bare `List`, `Optional[object]`, untyped params)
- [x] **Structured logging** — replaced `warnings.warn()` in `command_registry.py` and `editor.py` with `logging.getLogger(__name__)`; added `app/logger.py` with rotating file handler wired from `MainWindow`
- [x] **Entity ID index in `DocumentStore`** — added `_entity_by_id: Dict[str, BaseEntity]` maintained via `__post_init__`; `add_entity`, `remove_entity`, `get_entity`, and `clear` all updated for O(1) lookups
- [x] **Fix `ArcEntity.crosses_rect()` import** — removed `__import__('app.entities.base', ...)` hack; `BBox` was already imported at module level
- [x] **Deduplicate Escape handling** — extracted `CADCanvas.handle_escape()` as the single authoritative handler; `MainWindow` Escape shortcut now delegates directly to it
- [x] **Deduplicate Ortho/Draftmate mutual exclusion** — extracted `CADCanvas._set_ortho(on)` / `_set_draftmate(on)` methods; F8/F10 keys and status-bar buttons all call through these; mutual exclusion enforced in one place
- [x] **Ribbon audit — Major issues (§2.1–§2.8)** — consolidated `ButtonSize`/`IconSize` enums into a single `Sizing` NamedTuple; centralised 27+ hardcoded colour values into `COLORS`; stripped ~120 dead QSS rules; added `__all__` exports to all 7 ribbon modules; created 5 missing icon SVGs; wrote 30 ribbon tests covering models, factories, split buttons, and the top-level `RibbonPanel` widget

---

## Nice-to-Have / Long Term

- [ ] **Dark / Light theme toggle** — user-selectable UI theme beyond the current dark ribbon
- [ ] **Plugin / extension API** — allow third-party Python scripts to register new commands and entity types
- [ ] **Macro recorder** — record a sequence of user actions and replay them
- [ ] **Parametric constraints** — constrain entities to be parallel, perpendicular, equal length, concentric, etc.
- [ ] **3D wireframe view** — extend the entity model with Z coordinates and add a 3D orbit viewport
- [ ] **Cloud sync** — autosave documents to a cloud storage backend
- [ ] **Collaboration** — real-time multi-user editing (long-term, requires networking layer)
