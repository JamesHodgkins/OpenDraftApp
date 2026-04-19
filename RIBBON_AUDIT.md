# Ribbon Framework Audit

**Date:** 2026-04-19  
**Scope:** `controls/ribbon/`, `controls/icon_widget.py`, `app/config/ribbon_config.py`, `assets/themes/ribbon.qss`  
**Total:** ~2,219 lines across 10 files

---

## Executive Summary

The ribbon framework is functional and well-structured for an in-development app. It has a clean separation between data models, factories, and widgets. However, there are **architectural issues, naming collisions, dead theming code, hardcoded values, missing tests, a completely static layout system with no overflow handling, and accessibility gaps** that would need to be resolved before it could stand as a production-quality standalone component.

**Critical issues:** 4 &bull; **Major issues:** 8 &bull; **Minor issues:** 9 &bull; **Suggestions:** 6

---

## 1. CRITICAL ISSUES

### 1.1 ~~Class Name Collision: Two `RibbonPanel` Classes~~ ✅ RESOLVED

**Files:** `ribbon_panel.py`, `ribbon_panel_widget.py`

Both modules export a class called `RibbonPanel`. The top-level tab container and the individual panel widget share the same name. Inside `ribbon_panel.py`, the widget class is aliased as `RibbonPanelWidget` to avoid a local collision:

```python
from controls.ribbon.ribbon_panel_widget import RibbonPanel as RibbonPanelWidget
```

This is fragile and confusing. Anyone importing from the package will get the top-level class, but anyone importing from the widget module directly gets a different class with the same name.

**Recommendation:** Rename the widget class to `RibbonPanelFrame` or `RibbonPanelContainer` at the definition site. Eliminate the aliased import entirely.

---

### 1.2 ~~`setup_document()` Couples the Ribbon to Application Domain Logic~~ ✅ RESOLVED

**File:** `ribbon_panel.py` lines 175–296

The top-level `RibbonPanel` widget directly imports and instantiates application-specific classes (`ColorPickerDialog`, `Color`, `DocumentStore` internals) inside its methods. It knows about:

- `doc.active_color`, `doc.active_line_style`, `doc.active_thickness`, `doc.active_layer`
- `editor.selection`, `editor.set_entity_properties`, `editor.set_active_layer`
- `Color.from_string()`, `ColorPickerDialog`

This means the ribbon framework **cannot be reused independently**. It is tightly bound to the OpenDraft document model.

**Recommendation:** Extract all document-wiring into a separate bridge/adapter class (e.g., `RibbonDocumentBridge`) that lives in `app/`, not in `controls/`. The ribbon itself should only emit signals; the bridge listens and calls into the document/editor.

---

### 1.3 ~~No Signal-Based Architecture for Property Controls~~ ✅ RESOLVED

Color swatch, line-style combo, thickness combo, and layer combo all have their change handlers defined as closures **inside** `setup_document()`. These closures capture `self._document` and `self._editor` by closure, bypassing Qt's signal/slot mechanism.

This makes it impossible to:
- Connect external consumers to property changes
- Test property change behaviour without a full document stack
- Swap document instances at runtime

**Recommendation:** Each property control should emit a typed signal (e.g., `colorChanged(str)`, `lineStyleChanged(str)`, `layerChanged(str)`). The application bridge connects those signals to document/editor methods.

---

### 1.4 ~~Completely Static Layout — No Overflow, No Adaptive Sizing~~ ✅ RESOLVED (Phase 1)

**Files:** `ribbon_factory.py` (`PanelFactory`), `ribbon_panel.py` (`_create_tab_widget`), `ribbon_panel_widget.py`

The ribbon layout is entirely rigid. Every button has `setFixedSize()`, every panel is an `QHBoxLayout` of fixed-size children, and the tab content is a horizontal row of panels ending with `addStretch()`. There is **no mechanism** to handle panels that exceed the available window width.

**What happens today:** When the window is narrower than the sum of all panel widths, buttons silently get clipped by the widget boundary. They are still there (consuming space and receiving clicks) but are partially or fully invisible. This is the "squashed buttons" problem — Qt's `QHBoxLayout` with fixed-size children has no choice but to compress or clip them.

**Estimated tab widths vs. typical window sizes:**

| Tab | Estimated Width | Panels |
|-----|-----------------|--------|
| **Home** | **~1,451 px** | 7 (File, Edit, Draw, Annotate, Modify, Properties, System) |
| Create | ~682 px | 4 |
| Edit | ~408 px | 2 |
| View | ~361 px | 1 |
| Review | ~192 px | 1 |

The **Home tab at ~1,451 px** will overflow on any display under ~1,500 px wide. On a 1920×1080 monitor it fits, but resizing the window smaller immediately causes clipping. On a 1366×768 laptop display it is broken by default.

**Root causes:**

1. **No `resizeEvent` override** — the ribbon never re-evaluates its layout when the window resizes.
2. **No `sizeHint()` / `minimumSizeHint()`** — panels don't report meaningful preferred/minimum sizes, so Qt's layout engine cannot make informed decisions.
3. **`setUsesScrollButtons(False)`** on the tab bar — even the tab bar has explicitly disabled overflow scrolling.
4. **All widgets use `setFixedSize()`** — nothing is flexible. There is no size policy set on any button or panel (no `QSizePolicy.Preferred`, `Minimum`, or `Expanding`).
5. **Small buttons are batched into columns of 3** by `_create_small_button_column()`, but this is a fixed layout decision at construction time, not an adaptive response to available space.
6. **No concept of button priority** — there is no metadata saying which buttons are essential (always visible) vs. which can be demoted or hidden.

**What a production ribbon should do:**

Office, AutoCAD, and other professional ribbons handle overflow with an escalating strategy:

| Priority | Adaptation | Description |
|----------|-----------|-------------|
| 1 | **Demote large → small** | When space is tight, large buttons with only an icon can become small icon+label buttons in a vertical stack |
| 2 | **Collapse panel → single dropdown** | An entire panel's content is replaced by a single button with the panel name and a dropdown arrow. Clicking it shows the full panel in a popup |
| 3 | **Overflow chevron** | Panels that cannot fit at all are hidden behind a `>>` chevron button at the right edge. Clicking shows a popup with the hidden panels |

Currently the ribbon implements **none** of these.

**Recommendation (phased):**

**Phase 1 — Overflow chevron (minimal viable fix):**
- Override `resizeEvent()` on the tab content widget.
- After layout, check if the total panel width exceeds available width.
- Hide panels from the right edge until they fit, collecting hidden panels into a list.
- Show a `>>` overflow `QToolButton` at the right edge. Clicking it opens a popup/menu containing the hidden panels.
- This requires panels to know their natural width (implement `sizeHint()`) and support being shown in a detached popup.

**Phase 2 — Panel collapse:**
- Add a `collapsedWidget()` method to `RibbonPanelFrame` that returns a single dropdown button representing the full panel.
- During `resizeEvent()`, replace the rightmost visible panels with their collapsed widgets before resorting to the overflow chevron.
- Each `PanelDefinition` should declare a `collapse_priority: int` (lower = collapse first).

**Phase 3 — Adaptive button demotion:**
- Allow `ToolDefinition` to declare `compact_type` (e.g., a large button that can become small).
- During resize, iterate panels and demote buttons before collapsing the panel entirely.
- This is the most complex level and may not be needed if Phase 1+2 are sufficient.

---

## 2. MAJOR ISSUES ✅ ALL RESOLVED

### 2.1 Duplicate/Conflicting Sizing Systems

**File:** `ribbon_constants.py`

There are **three** overlapping sizing systems:

| System | Example | Used by |
|--------|---------|---------|
| `ButtonSize` enum | `LARGE = (60, 64)` | `ribbon_split_button.py` |
| `IconSize` enum | `LARGE = 45` | `ribbon_split_button.py`, `ribbon_factory.py` |
| `SIZE` (Sizing tuple) | `LARGE_BUTTON_WIDTH = 60` | `ribbon_factory.py`, `ribbon_panel.py` |

Additionally, the `Sizing` NamedTuple has **default values that differ from the actual `SIZE` instance**:

| Field | Default | Actual | 
|-------|---------|--------|
| `RIBBON_HEIGHT` | 140 | 126 |
| `LARGE_BUTTON_WIDTH` | 52 | 60 |
| `SMALL_BUTTON_HEIGHT` | 23 | 22 |
| `DROPDOWN_TEXT_HEIGHT` | 10 | 20 |
| `PANEL_SPACING` | 2 | 1 |
| `TOOL_SPACING` | 2 | 1 |
| `STACK_SPACING` | 2 | 3 |

The defaults are misleading dead code. Anyone calling `Sizing()` without arguments gets wrong values.

**Recommendation:** Remove the default values from the `Sizing` NamedTuple (or remove the NamedTuple defaults entirely). Consolidate `ButtonSize` and `IconSize` enums into the single `SIZE` constant, or make `SIZE` reference the enum values rather than duplicating them.

---

### 2.2 Light Theme is Dead Code

**File:** `ribbon_constants.py`

Light and dark background/hover colours are **identical**:

```
BACKGROUND_DARK  = "#2D2D2D"  ==  BACKGROUND_LIGHT = "#2D2D2D"
HOVER_DARK       = "#4A4A4A"  ==  HOVER_LIGHT      = "#4A4A4A"
```

The `dark` parameter flows through every factory and widget but **has no practical effect** on backgrounds or hover states. The only differentiated values are `TEXT_PRIMARY` and `TEXT_SECONDARY` — but the ribbon content area always uses the dark-mode text colours because `Styles.large_button()` hardcodes `COLORS.TEXT_PRIMARY_DARK` regardless of the `dark` flag.

Meanwhile, `ribbon.qss` defines distinct light/dark tab and button styles that **conflict** with the inline stylesheets.

**Recommendation:** Either commit to dark-only and remove the `dark` parameter everywhere, or implement genuine light-mode colours. Choose **one** styling strategy: QSS file OR inline `setStyleSheet()` — not both.

---

### 2.3 Stylesheet Layering Conflict (QSS vs Inline)

**Files:** `ribbon.qss`, `ribbon_factory.py`, `ribbon_panel.py`, `ribbon_split_button.py`

Styles are applied at three levels simultaneously:
1. **QSS file** (`ribbon.qss`) — loaded at app level
2. **Inline `setStyleSheet()`** — set on individual widgets by `Styles.*()` methods
3. **Direct `QPainter` drawing** — in `RibbonLargeButton`, `_RibbonTabBar`, `_SmallSplitMainButton`, `ColorSwatchButton`

Inline stylesheets **override** the QSS file's rules due to Qt's specificity model. This means edits to `ribbon.qss` may have no visible effect on many widgets, leading to confusion.

**Recommendation:** Standardise on one approach. For a standalone component, QSS-only (via `setStyleSheet` on the top-level ribbon) with class/objectName selectors is cleanest. Reserve `QPainter` overrides only for truly custom-painted widgets.

---

### 2.4 Hardcoded Colours Outside Constants Module

**Files:** `ribbon_factory.py`, `ribbon_panel.py`, `ribbon_split_button.py`

27+ hardcoded colour values (`#3a3a3a`, `#e0e0e0`, `#555`, `#888888`, `#f3f4f6`, `#9ca3af`, `#111827`, `#6b7280`, etc.) are scattered across the codebase, bypassing the `COLORS` constant.

Examples:
- `ColorSwatchButton.__init__()`: 4 hardcoded colours
- `_RibbonTabBar._tab_fill()`: 3 hardcoded colours  
- `_RibbonTabBar._tab_text_color()`: 4 hardcoded colours
- `RibbonSplitButton._build_menu()`: 4 hardcoded colours
- `_PROP_LABEL_STYLE`: hardcoded `#999`

**Recommendation:** Move all colours into `COLORS` (add new fields as needed). Reference `COLORS.*` everywhere.

---

### 2.5 No `__all__` Exports — Polluted Public API

**All ribbon modules**

No module defines `__all__`. This means `from controls.ribbon.ribbon_factory import *` exports 41 names including re-exported Qt classes (`QWidget`, `QPainter`, `QColor`, etc.). Consumers cannot tell what is public API vs implementation detail.

**Recommendation:** Define `__all__` in every module listing only the intentionally public classes/constants.

---

### 2.6 Zero Test Coverage

**Directory:** `tests/`

There are no tests for any ribbon component. No unit tests for:
- Model `from_dict()` parsing
- Button factory dispatch
- Panel construction
- Split button layout modes
- Configuration validation

**Recommendation:** Add tests for at minimum: `RibbonConfiguration.from_dict()`, `ButtonFactory.create_button()` dispatch, `PanelFactory.create_panel_content()` layout, and `RibbonSplitButton` in both small/large modes.

---

### 2.7 Deferred Imports Inside Method Bodies (8 instances)

**File:** `ribbon_panel.py`

Eight `from ... import` statements appear inside methods at >8 levels of indentation:

```
ribbon_panel.py:199: from PySide6.QtWidgets import QPushButton, QDialog
ribbon_panel.py:200: from app.colors.color import Color as _Color
ribbon_panel.py:201: from app.ui.color_picker import ColorPickerDialog as _ColorPickerDialog
ribbon_panel.py:245: from PySide6.QtWidgets import QComboBox as _QComboBox
ribbon_panel.py:338: from PySide6.QtWidgets import QPushButton as _QPushButton
ribbon_panel.py:339: from PySide6.QtWidgets import QComboBox as _QComboBox
ribbon_panel.py:401: from controls.ribbon.ribbon_factory import ColorSwatchButton
ribbon_panel.py:405: from app.colors.color import Color as _Color
```

Some are duplicated (e.g., `QComboBox` imported twice). The `_Color` import appears in two different methods. These are used to avoid circular imports caused by the tight coupling described in §1.2.

**Recommendation:** Resolving §1.2 (extracting the bridge) eliminates the circular dependency and allows all imports to move to module level.

---

### 2.8 Missing 5 Icon Assets

**Directory:** `assets/icons/`

Five icons referenced in `ribbon_config.py` do not exist on disk:

| Panel | Button | Missing Icon |
|-------|--------|-------------|
| Draw | Spline | `draw_spline` |
| Draw | Ellipse | `draw_ellipse` |
| Draw | Point | `draw_point` |
| Modify | Fillet | `mod_fillet` |
| Modify | Chamfer | `mod_chamfer` |

These buttons will silently display with no icon (no error, no placeholder — the `load_pixmap()` function returns `None` and the icon is simply not set).

**Recommendation:** Add the missing SVG/PNG assets, or display an explicit placeholder icon when an asset is missing (the `Icon` widget does this with "?" but `load_pixmap()` does not).

---

## 3. MINOR ISSUES

### 3.1 `RibbonAction` Model is Unused

**File:** `ribbon_models.py`

The `RibbonAction` dataclass is defined but never instantiated anywhere in the codebase. It has a `handler: Optional[Callable]` field and an `execute()` method that falls back to `print()`.

**Recommendation:** Remove it, or integrate it into the action dispatch pipeline.

---

### 3.2 `_PanelSeparator` Hardcodes Colour

**File:** `ribbon_panel.py` line 36

```python
self._color = QColor(70, 70, 70)
```

This should reference `COLORS` and respect the `dark` parameter.

---

### 3.3 `_layer_slot` Stored as Widget Attribute

**File:** `ribbon_panel.py` line 484

```python
combo._layer_slot = _slot
```

Storing a Python attribute on a `QComboBox` instance is fragile. If the combo is replaced (e.g., on tab rebuild), the attribute and connection are silently lost. A proper pattern is to track connections in a list on the ribbon itself, or use `QObject` property storage.

---

### 3.4 `combo_style()` Does Not Accept `dark` Parameter

**File:** `ribbon_constants.py`

Every other `Styles` method takes a `dark: bool` parameter. `combo_style()` is the exception — it always returns a dark-mode stylesheet. This is inconsistent.

---

### 3.5 Broad `except Exception:` Swallowing (4 instances)

**File:** `ribbon_panel.py` lines 235, 263, 291, 408

```python
try:
    doc._notify()
except Exception:
    pass
```

Exceptions are silently swallowed. At minimum, these should log a warning.

---

### 3.6 `MenuItem.to_dict()` is Never Called

**File:** `ribbon_models.py`

`MenuItem` has a `to_dict()` method but the serialisation direction is always `from_dict()`. The method is dead code.

---

### 3.7 `ToolDefinition.type` is `str`, Not `ButtonType` Enum

**File:** `ribbon_models.py`

All `type` comparisons throughout the factory use string literals like `ButtonType.LARGE.value` instead of comparing against the enum directly. The model stores `type: str` which defeats the purpose of having an enum.

**Recommendation:** Store `type: ButtonType` and compare enum-to-enum. Keep `from_dict()` as the string→enum boundary.

---

### 3.8 No Keyboard Navigation Support

**All ribbon modules**

- Tab bar has `setFocusPolicy(Qt.NoFocus)` — cannot be reached by keyboard
- No `QShortcut` or `&` mnemonic characters on any tab or button label
- No arrow-key navigation within panels

This is a significant accessibility gap for a production-level control.

---

### 3.9 No Status Bar Integration for Button Hover

**File:** `ribbon_factory.py`

The `status` field on `ToolDefinition` is defined but never used by the factory. Some config entries have `"status": "placeholder"`, but no tooltip or status-bar message is displayed when hovering over those buttons.

---

## 4. SUGGESTIONS (Non-Blocking)

### 4.1 Consider a `RibbonTheme` Dataclass

Replace the scattered `COLORS`, `SIZE`, `MARGINS`, and `Styles` singletons with a single `RibbonTheme` dataclass passed to the top-level `RibbonPanel`. This makes theming explicit and swappable at runtime.

### 4.2 Add a `RibbonBuilder` Fluent API

For programmatic construction (vs. config-dict-driven), a builder pattern would be more readable:

```python
ribbon = (RibbonBuilder()
    .tab("Home")
        .panel("File")
            .large_button("New", icon="file_new", action="newDocument")
            .small_button("Save", icon="file_save", action="saveDocument")
        .end_panel()
    .end_tab()
    .build())
```

### 4.3 Support Icon Fallback Chain

`load_pixmap()` should try: themed SVG → default SVG → themed PNG → default PNG → generated placeholder. Currently it silently returns `None`.

### 4.4 Signal Consolidation

Instead of individual `colorChanged`, `layerChanged`, etc. signals, consider a single `propertyChanged(str, object)` signal where the first arg is the property name. This scales to new property types without adding signals.

### 4.5 Add `setEnabled()`/`setVisible()` API per Action Name

A production ribbon should support disabling or hiding buttons by action name at runtime (e.g., disable "Undo" when the undo stack is empty). Currently there is no way to look up a button by its action string after construction.

### 4.6 Consider Ribbon Minimisation (Collapse/Expand)

Office-style ribbons support double-clicking a tab to collapse the panel area. This is a highly expected UX feature.

---

## 5. FILE-BY-FILE SUMMARY

| File | Lines | Role | Issues |
|------|-------|------|--------|
| `ribbon_constants.py` | 330 | Sizing, colours, style templates | §2.1 duplicate sizing, §2.2 dead light theme, §2.4 incomplete centralisation |
| `ribbon_models.py` | 231 | Dataclasses for config | §1.4 no collapse/overflow metadata, §3.1 dead `RibbonAction`, §3.6 dead `to_dict()`, §3.7 `type` as str |
| `ribbon_factory.py` | 374 | Widget construction | §1.4 all fixed sizes / no adaptive layout, §2.4 hardcoded colours, §2.3 inline styles, §3.9 unused `status` |
| `ribbon_panel.py` | 532 | Top-level widget + doc wiring | §1.2–1.3 coupling, §1.4 no resizeEvent / overflow, §2.7 deferred imports, §3.3–3.5 fragile patterns |
| `ribbon_panel_widget.py` | 56 | Panel frame | §1.1 name collision, §1.4 no sizeHint |
| `ribbon_split_button.py` | 257 | Split button variant | §2.4 hardcoded colours |
| `icon_widget.py` | 71 | Icon loading | §4.3 no fallback chain |
| `ribbon_config.py` | 137 | Config data | §1.4 no collapse_priority, §2.8 missing icons |
| `ribbon.qss` | 222 | Global QSS | §2.3 conflicts with inline styles |

---

## 6. RECOMMENDED PRIORITY ORDER

1. **§1.4** Implement overflow chevron (Phase 1) — fixes the immediate squashed-buttons UX problem
2. **§1.1** Fix class name collision (5 min, zero risk)
3. **§2.1** Consolidate sizing constants (30 min, medium risk)
4. **§2.4** Centralise all hardcoded colours (30 min, low risk)
5. **§2.8** Add missing icon assets (10 min, zero risk)
6. **§2.2 + §2.3** Decide theming strategy: dark-only or real dual-theme; QSS or inline (1–2 hrs, medium risk)
7. **§1.2 + §1.3** Extract document bridge out of ribbon (2–3 hrs, high reward)
8. **§1.4** Panel collapse (Phase 2) — after bridge extraction, panels need `collapsedWidget()` support
9. **§2.5** Add `__all__` to all modules (10 min)
10. **§2.6** Write foundational tests (1–2 hrs)
11. **§3.7 + §3.8** Enum-based types + keyboard nav (1 hr each)
12. **§1.4** Adaptive button demotion (Phase 3) — optional, only if Phase 1+2 are insufficient
