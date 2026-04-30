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
Tracking note (2026-04-25): Fixed GitHub Actions YAML syntax in `.github/workflows/ci.yml` by converting the Pyright post-processing step to a block `run: |` script with heredoc Python parsing.
Tracking note (2026-04-25): Updated CI workflow to force Node 24 for JavaScript actions, bumped `actions/checkout` and `actions/setup-python` to current major versions, and switched pytest execution to `xvfb-run` with an explicit `XDG_RUNTIME_DIR` to reduce Qt headless aborts (exit code 134).
Tracking note (2026-04-25): Further hardened CI Qt test execution for exit code 134 by using `QT_QPA_PLATFORM=minimal`, software OpenGL (`QT_OPENGL=software`, `LIBGL_ALWAYS_SOFTWARE=1`), Python fault-handler output, and verbose pytest diagnostics.
Tracking note (2026-04-25): Fixed CI `qtbot` fixture failure by installing Python dependencies from `requirements.txt` (which includes `pytest-qt`) instead of ad-hoc package installation in `.github/workflows/ci.yml`.
Tracking note (2026-04-25): Fixed Pyright CI log visibility by allowing `pyright --outputjson` to continue (`|| true`) and adding robust JSON/missing-report handling so parsed type errors are printed before failing the workflow.
Tracking note (2026-04-25): Updated `_SmallSplitMainButton.paintEvent()` in `controls/ribbon/ribbon_split_button.py` to use `Qt.AlignmentFlag` for text alignment (`AlignLeft | AlignVCenter`) in `painter.drawText(...)`, matching current PySide6 typing expectations.
Tracking note (2026-04-25): Fixed Pyright errors in `controls/ribbon/ribbon_split_button.py` by replacing `QIcon.On/Off` and `QIcon.Normal/Disabled` with scoped enum members `QIcon.State.*` and `QIcon.Mode.*` in custom split-button painting.
Tracking note (2026-04-25): Applied ribbon-wide Pyright enum cleanup by replacing legacy `Qt.Align*` usage with `Qt.AlignmentFlag.*`, switching split-button bevel drawing to `QStyle.ControlElement.CE_PushButtonBevel`, modernizing `RibbonLargeButton` icon mode/state enums, and removing unused `Icon` imports in ribbon controls.
Tracking note (2026-04-25): Fixed Pyright diagnostics in `controls/ribbon/ribbon_panel_widget.py` by switching to scoped Qt/PySide enums (`Qt.WindowType.*`, `Qt.WidgetAttribute.*`, `QFrame.Shape.*`, `QSizePolicy.Policy.*`), making layout item unwrapping explicit, and using `addWidget(tool)` + `setAlignment(...)` for stub-compatible alignment.
Tracking note (2026-04-25): Added a “run CI locally” setup: `scripts/ci.ps1` (Windows) and `nox -s ci` (`noxfile.py`) to run pytest + pyright the same way as GitHub Actions, to avoid CI back-and-forth.
Tracking note (2026-04-25): Added `Editor.get_vector()` / `Editor.get_vector_from()` helpers and refactored Move/Copy/Rotate vector-picking flows to use them (removes duplicated two-`get_point()` logic while preserving snap-from-base behavior).
Tracking note (2026-04-26): Simplified top-of-viewport terminal (`TopTerminalWidget`) panel to output-only (removed History/Output tabs) and added a dedicated suggestions list that appears while typing.
Tracking note (2026-04-26): Replaced the dropdown suggestions list with inline match buttons to the right of the terminal input (click to run).
Tracking note (2026-04-26): Fixed broken rectangle rotation by promoting `RectangleEntity` to a true rotated-rectangle model (center/width/height/rotation) and wiring Rotate/Scale transforms + drawing/hit-testing to respect rotation.
Tracking note (2026-04-26): Added OpenDraft native 2D file specification v1 deliverables under `Docs/file-format/` (normative spec markdown, JSON Schema, and minimal/comprehensive example files).
Tracking note (2026-04-26): Revised native format direction to ZIP-container `.odx` with required `document.json` payload, plus `DocumentStore` ODX save/load support and container error handling (`invalid_zip`, `missing_document_json`, `invalid_document_json`).
Tracking note (2026-04-27): Implemented file workflow in `MainWindow` (New/Open/Save/Save As, unsaved-change prompts, close confirmation, dirty-title tracking, and Ctrl+N/Ctrl+O/Ctrl+S/Ctrl+Shift+S shortcuts) backed by in-place `DocumentStore` replace/reset helpers.
Tracking note (2026-04-27): Switched active Qt app/window icon assets to `assets/icons/odx_icon.svg` so the running app uses the dedicated ODX glyph.
Tracking note (2026-04-27): Renamed native OpenDraft extension from `.odf` to `.odx` to avoid conflict with existing OpenDocument associations; updated file dialogs, defaults, specs, and tests.
Tracking note (2026-04-27): Added save-time embedded thumbnails in `.odx` containers (`assets/thumbnail.png`) using canvas-rendered PNG previews to support future shell/file-manager thumbnail integration.
Tracking note (2026-04-27): Added Linux pre-installer thumbnailer scaffolding (`scripts/linux_odx_thumbnailer.py` + install/uninstall helpers) so `.odx` embedded previews can be surfaced in Linux file managers.
Tracking note (2026-04-27): Hardened Linux thumbnailer install/uninstall helpers with explicit Linux platform guards so running them on Windows/macOS exits cleanly without creating misleading `~/.local` artifacts.
Tracking note (2026-04-27): Fixed `.odx` save regression in thumbnail export by switching `QImage.save(QBuffer, ...)` format argument from bytes to string (`"PNG"`) and added canvas regression coverage.
Tracking note (2026-04-27): Completed Priority 7 command/shortcut UX pass with terminal empty-Enter repeat-last-command, shell-style Up/Down input history recall (with draft restoration), F1/F2/F3 shortcuts, richer right-click canvas/entity context menu (recent commands + Properties/Copy), and ribbon hover tooltip previews.
Tracking note (2026-04-27): Fixed startup crash in ribbon tooltip propagation by replacing tuple-based `findChildren((QToolButton, QPushButton))` call with separate PySide-compatible `findChildren(QToolButton)` / `findChildren(QPushButton)` passes.
Tracking note (2026-04-27): Fixed terminal history/suggestion mismatch where recalled `core.line` could highlight the Dimension command; command filtering now prioritizes exact command-id matches and includes regression coverage.
Tracking note (2026-04-28): Fixed `Editor.run_command()` thread-lifecycle race by snapshotting thread references before `join()/is_alive()` checks and added contract regression coverage for the clear-during-join timing window.
Tracking note (2026-04-28): Added token-based terminal command-option input (`a`, `:a`, `/a`, `[a]`, `opt:a`) with inline payload chaining (`a 45`) and regression coverage in `tests/test_top_terminal.py`.
Tracking note (2026-04-28): Updated terminal token UX to parse command-option tokens live while typing (reversible via backspace/delete), keep option match clicks as staged input only, and use Enter as the explicit commit action.
Tracking note (2026-04-28): Added Space-key commit behavior for terminal command acceptance and non-string prompt submission (`l` + Space launches `core.line`; `0,0` + Space commits first line point and enables rubberband from that base point).
Tracking note (2026-04-28): Refined Space-key commit UX to preserve terminal text after commit (for example keep `core.line` and `0,0` visible) while Enter retains the existing clear-on-commit behavior.
Tracking note (2026-04-28): Added committed-prefix token-chain submission so retained text can stay visible as `core.line 0,0 ...` while active prompt commits only the latest fragment token.
Tracking note (2026-04-28): Hardened terminal token-chain editing so when retained prefix text is changed manually, submission falls back to the latest token fragment instead of mis-parsing the full line.
Tracking note (2026-04-28): Updated command repeat UX so empty Enter/Space repeats now populate terminal input with the repeated command token (plus separator) for immediate chained input.
Tracking note (2026-04-28): Canvas now recomputes dynamic preview entities on editor input-mode transitions and refresh calls so rubberband/preview can appear after terminal commits without requiring immediate mouse movement.
Tracking note (2026-04-28): Reworked terminal command execution to true Enter-only commit semantics (full command lines stay live/editable until Enter), limited Space to non-committing separator/autocomplete behavior, and added Enter-line token queue feeding for prompt-by-prompt command inputs.
Tracking note (2026-04-28): Fixed Enter-line token startup race in `TopTerminalWidget` so queued arguments (for example `core.line 0,0`) survive delayed command-start ticks and correctly arm first-point rubberband previews.
Tracking note (2026-04-28): Added canvas cursor-world seeding fallback from global cursor position during preview refresh/input-mode transitions so line rubberband previews can appear immediately even before the first explicit canvas mouse-move event.
Tracking note (2026-04-28): Added strict inline Enter command-line compilation checks so partial lines (for example `core.line 0,0`) now fail with an explicit incomplete-command error and auto-cancel instead of leaving commands half-running.
Tracking note (2026-04-28): Hardened preview cursor seeding so when the OS/global cursor is outside the canvas, the seed falls back to canvas center instead of an off-viewport world coordinate that can make rubberband previews appear missing.
Tracking note (2026-04-28): Fixed terminal startup input race where typed submissions entered while a command thread was running but still in temporary `input_mode="none"` could be misrouted/lost; submissions are now queued and delivered when the next prompt mode becomes ready.
Tracking note (2026-04-28): Added runtime terminal trace lines for Enter/point-submission state and a best-effort parent-canvas refresh trigger after terminal point delivery to help diagnose and reduce preview update timing misses.
Tracking note (2026-04-28): Added terminal post-point preview sync loop that repeatedly nudges canvas refresh until point-mode preview state is ready (or emits timeout debug), to harden against asynchronous state-transition misses.

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

- [x] **Basic native file workflow** — wire ribbon + shortcut New/Open/Save/Save As to `.odx`/`.json` dialogs with unsaved-change prompts and dirty-state title updates
- [ ] **DXF import** — read AutoCAD DXF files (via `ezdxf`) and populate the document store; at minimum support R12 entities (LINE, CIRCLE, ARC, TEXT, LWPOLYLINE, INSERT)
- [ ] **DXF export** — write the current document to DXF; enables round-tripping with AutoCAD/LibreCAD/FreeCAD
- [ ] **SVG import** — read basic SVG shapes into the document
- [ ] **Recent files** — remember the last N opened files; display in File menu
- [ ] **Auto-save / backup** — periodically save a recovery copy to a temp location

---

## Priority 7 — UX & Workflow

### Command Experience

- [x] **Command line / prompt bar** — implemented as a top-of-viewport terminal (800px wide) consolidating command input and output scrollback; replaces the old command palette and dynamic input overlay
- [x] **Command aliases** — short aliases (`l` → Line, `c` → Circle, `cp` → Copy, `m`/`mv` → Move) and terminal suggestions match on aliases
- [x] **Repeat last command** — pressing `Enter` or `Space` on an empty canvas repeats the previous command
- [x] **Command history** — scrollable log of recently executed commands and prompts

### Keyboard Shortcuts

- [x] **F1** — Help
- [x] **F2** — Toggle command history window
- [x] **F3** — Toggle OSNAP on/off (currently F8 is Ortho, F10 is Draftmate)
- [x] **Ctrl+Z / Ctrl+Y** — Undo/Redo (check current binding)
- [x] **Ctrl+S / Ctrl+Shift+S** — Save / Save As
- [x] **Ctrl+N / Ctrl+O** — New / Open
- [x] **Delete key** — delete selected entities
- [x] **Escape** — cancel in-progress command or clear selection (already implemented; verify both cases)

### Usability

- [x] **Tooltip previews** — show a small icon or description when hovering over ribbon buttons
- [x] **Ribbon quick colour popup** — clicking the ribbon colour swatch should show a compact palette (common colours + ByLayer) with an option to open the full colour picker
- [x] **Context menu extensions (right-click on canvas)** — add recent commands and richer entity-specific options (core context menu + command options are already implemented)
- [x] **Context menu on entity (right-click)** — Properties, Delete, Move, Copy, etc.
- [ ] **Grip editing improvements** — show grip count, support multi-grip drag with relative offset
- [x] **Grip editing: linked coincident grips** — when dragging a grip, move any coincident grips on other *selected* entities at the same time (single undo step)
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

---

## Nice-to-Have / Long Term

- [ ] **Dark / Light theme toggle** — user-selectable UI theme beyond the current dark ribbon
- [ ] **Plugin / extension API** — allow third-party Python scripts to register new commands and entity types
- [ ] **Macro recorder** — record a sequence of user actions and replay them
- [ ] **Parametric constraints** — constrain entities to be parallel, perpendicular, equal length, concentric, etc.
- [ ] **3D wireframe view** — extend the entity model with Z coordinates and add a 3D orbit viewport
- [ ] **Cloud sync** — autosave documents to a cloud storage backend
- [ ] **Collaboration** — real-time multi-user editing (long-term, requires networking layer)
