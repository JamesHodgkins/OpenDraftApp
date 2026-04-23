# OpenDraft — Development TODO Completed Items

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

