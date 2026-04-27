# OpenDraft — Development TODO Completed Items

### Priority 7 UX & Workflow Completion (2026-04-27)

- [x] **Repeat last command via empty Enter** — when no command is active and terminal input is empty, pressing Enter now repeats the most recent command
- [x] **PowerShell-style command recall** — terminal Up/Down now walks command input history and restores the in-progress draft when returning past the newest entry
- [x] **Command history panel shortcut** — added `F2` to toggle the top terminal's expandable history/scrollback panel
- [x] **OSNAP shortcut parity** — added global `F3` shortcut to toggle master OSNAP state and keep status-bar state in sync
- [x] **Help shortcut** — added `F1` shortcut that opens a keyboard-shortcuts help dialog
- [x] **Richer canvas/entity context menus** — added `Recent Commands` submenu plus entity-focused actions (`Properties`, `Copy`, `Move`, `Rotate`, `Scale`, `Delete`)
- [x] **Ribbon tooltip previews** — ribbon buttons now expose hover tooltips using tool label/status metadata
- [x] **Ribbon tooltip startup hotfix** — replaced tuple-based `findChildren((QToolButton, QPushButton))` with separate PySide-compatible `findChildren(QToolButton)` / `findChildren(QPushButton)` scans to prevent startup `TypeError`
- [x] **Terminal history exact-match selection fix** — when recalling command IDs from history (for example `core.line`), terminal suggestions now prioritize exact command-id/alias matches so the intended command remains highlighted

### ODX Thumbnail Save Regression Fix (2026-04-27)

- [x] **PySide6 `QImage.save` format fix** — updated `CADCanvas.export_thumbnail_png()` to call `image.save(buffer, "PNG")`; passing `b"PNG"` raised `ValueError` at runtime on current PySide6 builds
- [x] **Canvas thumbnail regression coverage** — added `tests/test_canvas.py` coverage to assert exported thumbnail bytes are valid PNG data

### Linux Thumbnailer Scaffolding (2026-04-27)

- [x] **Extractor script** — added `scripts/linux_odx_thumbnailer.py` to extract `assets/thumbnail.png` from `.odx` files for freedesktop thumbnailer calls
- [x] **Per-user install/uninstall helpers** — added `scripts/install_linux_thumbnailer.py` and `scripts/uninstall_linux_thumbnailer.py` to register/remove MIME + thumbnailer files under `~/.local/share`
- [x] **Developer docs + tests** — documented no-installer Linux thumbnail setup in `README.md` and added extraction coverage in `tests/test_linux_odx_thumbnailer.py`
- [x] **Platform guard hardening** — installer helpers now bail out on non-Linux platforms to avoid fake success output on Windows/macOS

### Embedded ODX Thumbnails (2026-04-27)

- [x] **Save-time thumbnail embedding** — `MainWindow` now captures a canvas thumbnail on save and `DocumentStore.save_odx()` stores it as `assets/thumbnail.png` inside the `.odx` ZIP container
- [x] **Thumbnail API support** — added `DocumentStore.load_thumbnail_png()` helper for reading embedded preview bytes from `.odx` files
- [x] **Format docs + tests updated** — documented optional `assets/thumbnail.png` in native format docs and added container thumbnail coverage in `tests/test_document.py`

### Native Extension Rename (2026-04-27)

- [x] **Native extension switched to `.odx`** — updated file dialogs/default names, native save/load API naming (`save_odx()`/`load_odx()`), tests, and format docs to use `.odx` instead of `.odf`

### App Icon Update (2026-04-27)

- [x] **Dedicated ODX icon activated** — updated Qt startup icon paths in `main.py` and `app/main_window.py` to use `assets/icons/odx_icon.svg`

### File Save/Open Workflow (2026-04-27)

- [x] **Ribbon file actions wired locally** — `newDocument`, `openDocumentFromFile`, and `saveDocumentToFile` are now handled by `MainWindow` instead of being forwarded to the command registry
- [x] **End-to-end New/Open/Save/Save As flow** — added file dialogs for `.odx`/`.json` with extension normalization and persisted active document path tracking
- [x] **Unsaved-change protection** — added Save/Discard/Cancel prompts for New/Open and a close-event confirmation gate when the document is dirty
- [x] **Dirty-state title + shortcuts** — added generation-based dirty tracking (window title `*`) and keyboard shortcuts: `Ctrl+N`, `Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+S`
- [x] **Document swap/reset primitives** — added `DocumentStore.generation`, `replace_with(...)`, and `reset_to_default(...)` with regression coverage in `tests/test_document.py`

### Compressed Native Container (2026-04-26)

- [x] **ZIP-container native format direction** — updated the v1 file spec to define `.odx` as a ZIP package with required `document.json` payload and optional reserved `meta.json` / `assets/` entries
- [x] **Compatibility policy and error model** — documented `.odx` native + raw `.json` debug compatibility and container-specific errors (`invalid_zip`, `missing_document_json`, `invalid_document_json`)
- [x] **DocumentStore ODX I/O support** — added `save_odx()` / `load_odx()` and extension-dispatching `save()` / `load()` helpers in `app/document.py`
- [x] **ODX coverage tests** — added serialization and error-path tests in `tests/test_document.py` including payload presence, invalid ZIP handling, invalid JSON handling, extension dispatch, and size comparison vs pretty JSON
- [x] **Container examples guidance** — added `Docs/file-format/examples/odx-package-layout.md` and updated spec references

### Native File Specification (2026-04-26)

- [x] **OpenDraft 2D file spec v1 (documentation)** — added normative specification at `Docs/file-format/opendraft-2d-v1.md` defining canonical document/entity contracts, versioning, unknown-field policy, and validation behavior
- [x] **JSON Schema companion artifact** — added `Docs/file-format/opendraft-2d-v1.schema.json` covering all currently supported entity types and top-level document/layer contracts
- [x] **Reference example files** — added `Docs/file-format/examples/minimal-line.json` and `Docs/file-format/examples/comprehensive-sample.json` for minimal and full-shape payload guidance

### Modify Commands (ribbon buttons wired, no command class)

- [x] **Delete** — remove selected entities from the document; responds to `Delete` key and ribbon button
- [x] **Move** — select entities, pick base point, pick destination; translates all selected entities with live preview
- [x] **Copy** — same as Move but leaves originals; supports multiple paste placements before Esc
- [x] **Rotate** — select entities, pick rotation center, input angle (degrees); live preview while typing
- [x] **Scale** — select entities, pick base point, input scale factor; uniform scaling with live preview
- [x] **Mirror** — select entities, pick two axis points; prompts to keep (1) or delete (0) originals
- [x] **Extend** — pick a boundary entity, then click near line/arc endpoints to extend them to it

### Ribbon Audit Critical Fixes

- [x] **§1.1 Class name collision** — renamed `RibbonPanel` in `ribbon_panel_widget.py` to `RibbonPanelFrame`; updated all imports
- [x] **§1.2 Document coupling** — extracted domain logic from `RibbonPanel.setup_document()` into `app/ribbon_bridge.py` (`RibbonDocumentBridge`); ribbon no longer imports app-layer modules
- [x] **§1.3 Signal architecture** — added `colorChangeRequested`, `lineStyleChanged`, `lineWeightChanged`, `layerChanged` signals to `RibbonPanel`; added public setter methods (`set_swatch_color`, `populate_layers`, etc.)
- [x] **§1.4 Static layout / overflow** — added `_OverflowTabContent` widget with `resizeEvent`-based reflow; panels that don't fit are hidden and accessible via a `>>` chevron popup

### Ribbon Audit Major Fixes

- [x] **§2.1 Sizing constants** — removed `ButtonSize`/`IconSize` enums; consolidated all values into a single `Sizing` NamedTuple with no defaults
- [x] **§2.2+§2.3 Theming cleanup** — committed to dark-only; stripped ~120 lines of dead QSS rules overridden by inline `setStyleSheet()`/`paintEvent()`
- [x] **§2.4 Hardcoded colours** — added 11 semantic colour constants to `COLORS`; replaced 27+ hardcoded hex values across `ribbon_factory.py`, `ribbon_split_button.py`, and `ribbon_panel.py`
- [x] **§2.5 `__all__` exports** — added `__all__` to all 7 ribbon modules (`__init__`, constants, models, factory, panel, panel_widget, split_button)
- [x] **§2.6 Ribbon tests** — added `tests/test_ribbon.py` with 30 tests covering model parsing/dispatch, `ButtonFactory`, `PanelFactory`, `RibbonSplitButton`, `RibbonPanel` signals, and constants
- [x] **§2.7 Deferred imports** — confirmed zero `from app.*` imports in ribbon package; removed last deferred `from PySide6.QtWidgets import QLabel`
- [x] **§2.8 Missing icons** — created 5 SVGs: `draw_spline.svg`, `draw_ellipse.svg`, `draw_point.svg`, `mod_fillet.svg`, `mod_chamfer.svg`

### UX

- [x] **Ribbon quick colour popup** — ribbon colour swatch now opens a compact common-colours panel (incl. ByLayer) with a "More…" affordance for the full colour picker
- [x] **Canvas context menu** — added right-click context menu on the canvas (Undo/Redo/Delete/Modify→Rotate) with right-click-to-select behaviour and command-safe selection handling
- [x] **Command options in context menu** — when a command is running in "choice" mode, right-click shows a "Command options" submenu that injects choices back into the active command; Rotate now supports base/destination vector input via these options
- [x] **Top command terminal** — added `TopTerminalWidget` (800px wide, top-center) as the single consolidated input + output surface with expandable output scrollback; removed the floating command palette and cursor-following dynamic input overlay
- [x] **Command aliases** — added short aliases for core commands (`l`, `c`, `cp`, `m`, `mv`) and extended the top terminal’s suggestions to match on `CommandSpec.aliases`

### Entities / Geometry

- [x] **Rotated rectangles (no polyline conversion)** — `RectangleEntity` now stores `center/width/height/rotation` and implements draw/bbox/hit-test/crossing selection in the rotated frame; Rotate/Scale modify commands update rectangle orientation and size correctly.

### Command Input Pipeline Hardening (2026-04-24)

- [x] **Non-overlapping command lifecycle** — `Editor.run_command()` now refuses to start a new command while a previous worker thread is still alive after cancellation timeout
- [x] **Typed command-option events** — replaced magic-string option payload handling with `CommandOptionSelection` typed results flowing through the editor input queue
- [x] **Rotate command migration** — `RotateCommand` now consumes typed command-option selections and validates zero-length base/destination vectors before computing reference-vector rotation
- [x] **Dynamic input update fix** — canvas dynamic input now updates in point mode even when OSNAP is disabled/suppressed; suppressed mode clears any visible dynamic widget
- [x] **Regression test updates** — added editor tests for command-option event flow and updated canvas viewport tests to use `update_offset_for_size` instead of removed private helpers

### Undo Regression Fixes (2026-04-24)

- [x] **`RemoveEntitiesUndoCommand.undo()` index sync** — restoring removed entities now updates `DocumentStore._entity_by_id` alongside `entities` list insertion, fixing `doc.get_entity(...)` returning `None` after undo
- [x] **Undo validation** — `tests/test_undo.py` and full `pytest` suite now pass after the index-sync fix

### Command SDK Foundation (2026-04-24)

- [x] **Stable command SDK layer** — added `app/sdk/commands` with `CommandContext`, `CommandSpec`, and public registration decorators (`@command`, `@register`) for third-party command authors
- [x] **Registry integration for SDK commands** — added `register_sdk_command`, command spec storage, and alias resolution in `app/editor/command_registry.py` while preserving legacy `@command("...")` command classes
- [x] **Metadata-aware palette wiring** — command palette now accepts command spec mappings and uses `display_name` labels when available
- [x] **SDK contract tests** — added `tests/test_command_sdk.py` covering function-based and class-based SDK registration and execution through the legacy runtime adapter

### Metadata-Rich Command Specs (2026-04-24)

- [x] **Rich `@command` metadata support** — legacy decorator now accepts metadata fields (`display_name`, `description`, `category`, `aliases`, `icon`, `source`, `min_api_version`) while staying backward-compatible with `@command("name")`
- [x] **Ribbon metadata adoption** — added `command_specs_from_ribbon()` in `app/config/ribbon_config.py` and applied it at startup via `apply_command_specs(...)` so core commands expose rich metadata in the registry
- [x] **Metadata merge API** — added `apply_command_specs(specs, only_registered=True)` in `app/editor/command_registry.py` to merge/normalize metadata and alias mappings safely
- [x] **Metadata tests** — added `tests/test_command_metadata.py` covering ribbon metadata extraction and enrichment of registered core command specs

### Command Namespacing & Collision Policy (2026-04-24)

- [x] **Namespaced command IDs enforced** — non-core SDK/plugin command IDs must be namespaced (for example `vendor.tool`); legacy core IDs are canonicalized to `core.<slug>` and preserved as aliases for ribbon/action compatibility
- [x] **Fail-fast command ID collisions** — duplicate registration of an existing command id now raises `ValueError` instead of silently overwriting
- [x] **Fail-fast alias collisions** — alias re-assignment across different command ids now raises `ValueError` instead of warning/rebinding
- [x] **Policy regression tests** — added `tests/test_command_registry_policy.py` for legacy-core aliasing, non-namespaced plugin rejection, and duplicate id/alias collision guards

### Plugin Entry-Point Discovery (2026-04-24)

- [x] **Entry-point plugin discovery** — added `autodiscover_entry_points(group="opendraft.commands")` in `app/editor/command_registry.py` using `importlib.metadata.entry_points(...)` with backward-compatible fallback handling
- [x] **Startup wiring for plugins** — `MainWindow` startup now loads built-ins via `autodiscover("app.commands")` and plugin packages via `autodiscover_entry_points("opendraft.commands")`
- [x] **Resilient plugin loading** — discovery isolates plugin failures (logs and continues) so one bad plugin does not prevent other plugins or core startup
- [x] **Plugin discovery tests** — added `tests/test_command_plugin_discovery.py` covering successful callable entry-point registration and mixed failure/success loading behavior

### Action Resolution & Startup Validation (2026-04-24)

- [x] **Generic action validation API** — added `ActionValidationReport`, `validate_actions(...)`, and `validate_action_sources(...)` in `app/editor/command_registry.py` to classify local, command-backed, and unresolved actions
- [x] **Ribbon action extraction helper** — added `ribbon_action_names(...)` in `app/config/ribbon_config.py` to collect actionable IDs from plain, split, and stacked ribbon tool definitions
- [x] **Startup action validation reporting** — `app/main_window.py` now validates ribbon actions at import/startup against local handlers + command registry and logs unresolved actions
- [x] **Settings action routing fix** — `toggleSettingsModal` ribbon action now routes to `_open_draftmate_settings()` instead of being silently ignored
- [x] **Validation tests** — added `tests/test_action_validation.py` covering action classification, multi-source reporting, and ribbon action extraction

### High-Level Command Helpers (2026-04-24)

- [x] **Public command helper APIs** — added `EditorTransaction` batching plus public `Editor.push_undo_command()`, `Editor.notify_document()`, `Editor.preview()`, and `Editor.highlighted()` helpers
- [x] **SDK helper surface** — extended `app/sdk/commands/context.py` with `push_undo()`, `transaction()`, `notify_document()`, and preview/highlight scope wrappers for plugin command authors
- [x] **Modify-command migration** — updated modify command execution paths to use public editor helper APIs instead of direct `editor._undo_stack` access
- [x] **Helper regression tests** — expanded `tests/test_editor.py` and `tests/test_command_sdk.py` to cover preview/highlight lifecycle scopes and transaction grouping semantics

### Command Catalog Refresh (2026-04-24)

- [x] **Refreshable catalog APIs** — added `command_catalog()`, `command_catalog_version()`, `unregister_command()`, `unregister_commands_by_source()`, and `refresh_command_catalog()` in `app/editor/command_registry.py`
- [x] **Refresh result model** — added `CommandCatalogRefreshResult` to report removed command IDs, loaded plugin entry points, total command count, and catalog version
- [x] **Picker repopulation hook** — added `MainWindow.refresh_command_catalog()` plus `_refresh_command_pickers()` so command palette repopulates from refreshed catalog snapshots
- [x] **Catalog refresh tests** — added `tests/test_command_catalog_refresh.py` covering catalog snapshot safety, source-based unregister, and plugin reload refresh behavior

### Command Architecture Contract Tests (2026-04-24)

- [x] **Lifecycle contract coverage** — added `tests/test_command_architecture_contract.py` to verify cancellation lifecycle reset and safe start-after-cancel behavior
- [x] **Helper undo contract coverage** — added contract tests for `Editor.transaction(...)` and `Editor.push_undo_command(...)` undo/redo guarantees
- [x] **Alive-thread start guard coverage** — added a guard test ensuring `Editor.run_command()` refuses to start a new command while a prior worker thread remains alive
- [x] **AA-P1b architecture validation pass** — validated command architecture suites (`test_command_architecture_contract`, `test_command_catalog_refresh`, `test_command_plugin_discovery`, `test_command_registry_policy`, `test_command_sdk`, `test_action_validation`) and full `pytest` run (262 passed)

### Move/Copy Vector Input (2026-04-24)

- [x] **Move command vector displacement input** — second Move pick now uses the base point as `editor.snap_from_point`, so Ortho and dynamic dX/dY input are anchored to the base-point vector
- [x] **Copy command vector displacement input** — repeated Copy placements now keep the base point as `editor.snap_from_point`, preserving Ortho and typed vector behavior across each placement
- [x] **Regression tests for vector-origin behavior** — added editor tests covering Move/Copy base-point vector-origin setup while awaiting destination/displacement input
- [x] **Editor `get_vector` helpers** — added `Editor.get_vector(p1_message, p2_message)` and `Editor.get_vector_from(base, p2_message)` and refactored Move/Copy/Rotate to use the shared vector-picking flow (centralizes `snap_from_point` scoping and removes duplicated two-`get_point()` blocks)

### Canvas Vector Rubberband Feedback (2026-04-24)

- [x] **Fallback vector rubberband overlay** — canvas now draws a dashed base→cursor guide when commands are in point input mode with `snap_from_point` set and no command-specific dynamic preview entities are provided
- [x] **Preview-compatible visibility** — vector rubberband now remains visible even when command-specific dynamic preview entities are present (for example Move/Copy transform previews)
- [x] **Cursor-state lifecycle handling** — canvas now tracks the resolved world cursor used for the fallback guide and clears it when input mode returns to `none`
- [x] **Canvas regression tests** — added tests for rubberband visibility preconditions and cursor-state reset behavior in `tests/test_canvas.py`

### Rotate/Scale Vector Input (2026-04-24)

- [x] **Editor point-input option support** — `Editor.get_point(...)` now supports optional command-option events (`allow_command_options=True`) so point/vector workflows can keep right-click options active
- [x] **Rotate primary vector flow** — `RotateCommand` now uses point/vector input for the main rotation angle pick (center -> vector tip), while preserving options for entering numeric angle and base/destination vector workflows
- [x] **Rotate base-vector zero-axis reference** — when a base vector is set, Rotate now interprets subsequent standard rotation-vector picks relative to that base vector (for example, an upward base vector makes upward picks zero rotation)
- [x] **Rotate relative-reference UX prompts** — Rotate command options/prompts now explicitly indicate when angle/vector input is interpreted relative to the active base vector
- [x] **Scale primary vector flow** — `ScaleCommand` now uses point/vector input for reference-length picking (base -> vector tip), while preserving numeric factor entry via command option
- [x] **Regression coverage** — added editor tests for point-input command-option delivery and Rotate/Scale vector-input execution paths

### CADCanvas Rendering Decomposition (2026-04-25)

- [x] **Extracted render-only helpers** — added `app/canvas_painting.py` to host OSNAP marker, Draftmate guide, grip square, selection rectangle, and vector-rubberband drawing routines
- [x] **Consolidated pen composition** — added shared base-pen and overlay-pen helper functions and wired both entity-cache rendering and canvas test helper APIs to use the same composition path
- [x] **Preserved `CADCanvas` API stability** — retained `CADCanvas` helper method names as thin delegates so existing tests and call sites remain intact while reducing class responsibility
- [x] **Regression validation** — full headless test suite passes after extraction (`272 passed`)

### CADCanvas Qt Enum / Type Cleanup (2026-04-25)

- [x] **PySide6 enum normalization** — replaced legacy enum access in `app/canvas.py` with scoped PySide6 enums (`Qt.MouseButton.*`, `Qt.CursorShape.*`, `Qt.KeyboardModifier.*`, `Qt.Key.*`) to satisfy current stubs and remove editor diagnostics
- [x] **Nullable-state narrowing** — added local editor/document guards in event and selection paths so static analysis can prove non-None accesses
- [x] **Dynamic input typing hardening** — narrowed submitted dynamic-input values before forwarding integer/float/angle/length inputs to editor providers
- [x] **Validation pass** — `get_errors` reports no issues in `app/canvas.py`; `tests/test_canvas.py` passes (`17 passed`)

### CADCanvas Interaction Decomposition (2026-04-25)

- [x] **Extracted interaction-rule helpers** — added `app/canvas_interaction.py` for point-resolution precedence (Draftmate/OSNAP/Ortho), selection drag threshold checks, rectangle normalization, window/crossing mode detection, and grip/entity hit-selection helpers
- [x] **Reduced in-method event complexity** — `CADCanvas.mouseMoveEvent`, `CADCanvas._finish_selection`, and canvas right-click hit testing now delegate interaction rules to helper functions while keeping canvas as the UI orchestrator
- [x] **Regression validation** — static diagnostics clear for `app/canvas.py` and `app/canvas_interaction.py`; full headless test suite passes (`272 passed`)

### CADCanvas Command-Flow Decomposition (2026-04-25)

- [x] **Extracted command-mode flow helpers** — added `app/canvas_command_flow.py` for snap-active detection, snap/draftmate update sequencing, and dynamic-input update gating
- [x] **Reduced command path complexity** — `CADCanvas.mouseMoveEvent` now delegates snap/draftmate state evolution and dynamic-input condition logic to helper functions while preserving existing cursor/display behavior
- [x] **Regression validation** — static diagnostics clear for `app/canvas.py` and `app/canvas_command_flow.py`; full headless test suite passes (`272 passed`)

### CADCanvas Grip Lifecycle Decomposition (2026-04-25)

- [x] **Extracted grip lifecycle helpers** — added `app/canvas_grip_flow.py` for hot-grip activation snapshots, active-grip drag preview updates (including snap exclusion of edited entity), final grip placement resolution, commit/undo wiring, and canonical reset state
- [x] **Reduced event-handler complexity** — grip-specific branches in `CADCanvas.mousePressEvent`, `CADCanvas.mouseMoveEvent`, and `CADCanvas.handle_escape` now delegate to helper functions while keeping canvas as orchestration layer
- [x] **Regression validation** — static diagnostics clear for `app/canvas.py` and `app/canvas_grip_flow.py`; full headless test suite passes (`272 passed`)

### Grip Editing Linked Coincident Grips (2026-04-25)

- [x] **Linked coincident grips** — when dragging a grip, any coincident grips on other *selected* entities are moved together during preview and commit, with a single grouped undo step

### CI Workflow YAML Syntax Fix (2026-04-25)

- [x] **Fixed invalid multiline `run` syntax** — replaced broken quoted multi-line `python -c` block in `.github/workflows/ci.yml` with a valid YAML block scalar (`run: |`)
- [x] **Preserved Pyright error surfacing** — kept JSON post-processing behavior by writing `pyright --outputjson` to a file and parsing it in an inline heredoc Python script
- [x] **Push/PR workflow compatibility restored** — workflow file now conforms to GitHub Actions YAML parsing rules, preventing pre-run "Invalid workflow file" failures

### CI Node24 + Headless Stability Update (2026-04-25)

- [x] **Node 24 deprecation mitigation** — added workflow-level `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` and upgraded GitHub actions to current major versions (`actions/checkout@v5`, `actions/setup-python@v6`)
- [x] **Headless Qt test hardening** — switched pytest execution to `xvfb-run -a pytest` and set up a dedicated `XDG_RUNTIME_DIR` in CI to reduce Qt platform aborts (exit code `134`)
- [x] **Forward compatibility improved** — workflow now proactively aligns with GitHub’s Node 20 deprecation timeline while preserving existing pytest + pyright checks

### CI Exit 134 Follow-up Hardening (2026-04-25)

- [x] **Qt backend stabilization** — changed CI test runtime to `QT_QPA_PLATFORM=minimal` with software rendering (`QT_OPENGL=software`, `LIBGL_ALWAYS_SOFTWARE=1`) to reduce native Qt aborts in headless Linux execution
- [x] **Crash diagnostics enabled** — enabled `PYTHONFAULTHANDLER=1` and `PYTHONUNBUFFERED=1` for better crash traces and immediate log flushing in CI
- [x] **Actionable pytest output** — updated pytest command to `pytest -ra -vv --maxfail=1` for clearer first-failure context when CI aborts recur

### CI qtbot Fixture Resolution (2026-04-25)

- [x] **Root cause identified** — CI installed ad-hoc packages (`PySide6 pyright pytest`) and skipped `requirements.txt`, so `pytest-qt` was not installed and `qtbot` fixture was unavailable
- [x] **Dependency install corrected** — workflow install step now uses `python -m pip install -r requirements.txt pyright`, ensuring test plugin dependencies are consistent with the repository
- [x] **Test collection restored** — pytest can now discover `qtbot` fixture from `pytest-qt` during CI test setup

### CI Pyright Diagnostics Visibility Fix (2026-04-25)

- [x] **Removed early shell-exit trap** — updated CI to run `pyright --outputjson > pyright-report.json || true` so the diagnostics parsing script still executes when Pyright returns non-zero
- [x] **Added report guards** — Pyright post-processing now checks for missing `pyright-report.json` and emits a clear failure message when output is absent
- [x] **Improved parse failure clarity** — JSON decode failures now print raw Pyright output before raising, making malformed output/debugging issues observable in workflow logs

### Ribbon Split Button AlignmentFlag Cleanup (2026-04-25)

- [x] **Alignment API modernization** — updated `_SmallSplitMainButton.paintEvent()` in `controls/ribbon/ribbon_split_button.py` to use `Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter` for the `QPainter.drawText(...)` alignment argument
- [x] **Typing/tooling compatibility** — replaced legacy `Qt.AlignLeft | Qt.AlignVCenter` usage to align with current PySide6 enum-scoped typing recommendations

### Ribbon Split Button QIcon Enum Fix (2026-04-25)

- [x] **Pyright enum compatibility** — replaced legacy `QIcon.Normal/Disabled` with `QIcon.Mode.Normal/Disabled` and `QIcon.On/Off` with `QIcon.State.On/Off` in `_SmallSplitMainButton.paintEvent()`
- [x] **No behavioral change** — retained identical icon mode/state selection logic for enabled/disabled and pressed/unpressed rendering paths

### Ribbon Pyright Enum & Import Cleanup (2026-04-25)

- [x] **Unused import diagnostics fixed** — removed unused `Icon` imports from `controls/ribbon/ribbon_split_button.py` and `controls/ribbon/ribbon_factory.py`
- [x] **`AlignTop` diagnostics fixed** — replaced legacy `Qt.AlignTop` and related `Qt.Align*` combinations with `Qt.AlignmentFlag.*` across `controls/ribbon/ribbon_factory.py` and `controls/ribbon/ribbon_panel_widget.py`
- [x] **`QStyle` control-element typing fixed** — updated split-button bevel draw call to `QStyle.ControlElement.CE_PushButtonBevel` for PySide6 stub compatibility
- [x] **Additional enum modernization** — updated `RibbonLargeButton` icon state/mode usage to `QIcon.State.*` and `QIcon.Mode.*`; replaced `Qt.TextWordWrap` with `Qt.TextFlag.TextWordWrap` in custom large-button text drawing

### Ribbon Panel Widget Layout Typing Fix (2026-04-25)

- [x] **Optional layout narrowing** — updated `natural_width()`, `minimumSizeHint()`, and `_reflow_tools()` in `controls/ribbon/ribbon_panel_widget.py` to store `self.layout()` in a local variable and narrow before calling `contentsMargins()`
- [x] **addWidget overload compatibility** — changed `_restore_tools()` to use positional `addWidget(tool, 0, Qt.AlignmentFlag.AlignTop)` so Pyright resolves the supported overload without keyword-argument mismatch
- [x] **Behavior preserved** — kept runtime layout margin defaults and restored-tool top alignment semantics unchanged

