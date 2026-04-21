"""
Bridge between the ribbon UI and the application document/editor.

This module keeps ``controls.ribbon`` free of application-specific imports
(``DocumentStore``, ``Editor``, ``Color``, ``ColorPickerDialog``, …).  All
domain logic that was previously inside ``RibbonPanel.setup_document()``
now lives here.

Usage (from ``MainWindow.__init__``)::

    from app.ribbon_bridge import RibbonDocumentBridge

    bridge = RibbonDocumentBridge(ribbon, doc, editor)
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import QPushButton, QComboBox, QDialog

from app.colors.color import Color
from app.ui.color_picker import ColorPickerDialog
from app.ui.quick_color_popup import QuickColorPopup

_LOG = logging.getLogger(__name__)


class RibbonDocumentBridge:
    """Wires ribbon signals to the document model and editor.

    Parameters
    ----------
    ribbon:
        The top-level :class:`~controls.ribbon.ribbon_panel.RibbonPanel`.
    doc:
        The application :class:`~app.document.DocumentStore`.
    editor:
        The application :class:`~app.editor.Editor`.
    """

    def __init__(self, ribbon, doc, editor) -> None:
        self._ribbon = ribbon
        self._doc = doc
        self._editor = editor

        # ── Populate layers on first wire-up ──────────────────────────
        self._refresh_layers()

        # ── Connect ribbon signals → bridge handlers ─────────────────
        ribbon.colorChangeRequested.connect(self._on_color_change_requested)
        ribbon.lineStyleChanged.connect(self._on_line_style_changed)
        ribbon.lineWeightChanged.connect(self._on_line_weight_changed)
        ribbon.layerChanged.connect(self._on_layer_changed)

        # ── Selection awareness ───────────────────────────────────────
        if editor is not None:
            editor.selection.changed.connect(self._refresh_controls_from_selection)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def refresh_layers(self) -> None:
        """Repopulate the layer-select combo from the current document.

        Call this whenever layers are added, removed or renamed.
        """
        self._refresh_layers()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_color_change_requested(self) -> None:
        """Show quick colour popup; allow opening the full picker."""
        doc = self._doc
        editor = self._editor
        ribbon = self._ribbon

        raw = self._current_color_string()

        anchor = None
        if hasattr(ribbon, "color_swatch_anchor"):
            try:
                anchor = ribbon.color_swatch_anchor()
            except Exception:
                anchor = None
        if anchor is None:
            anchor = ribbon.findChild(QPushButton, "colorSwatchBtn")
        if anchor is None:
            # Fallback if we can't find the swatch button for any reason.
            self._open_full_color_picker(raw)
            return

        popup = QuickColorPopup(initial=raw, parent=ribbon.window())
        popup.colorPicked.connect(self._apply_color_string)
        popup.moreRequested.connect(lambda: self._open_full_color_picker(raw))
        popup.popup_below(anchor)

    def _current_color_string(self) -> Optional[str]:
        """Return the current colour override string (selection or active)."""
        doc = self._doc
        editor = self._editor
        if editor and editor.selection:
            first_id = next(iter(editor.selection.ids))
            e = doc.get_entity(first_id)
            return (e.color if e and e.color else None)
        return doc.active_color

    def _open_full_color_picker(self, raw: Optional[str]) -> None:
        """Open the full tabbed colour dialog starting from *raw*."""
        ribbon = self._ribbon
        initial = Color.from_string(raw) if raw is not None else Color(aci=7)
        dlg = ColorPickerDialog(initial=initial, parent=ribbon, title="Override colour")
        if dlg.exec() != QDialog.Accepted:
            return
        chosen = dlg.chosen_color()
        color_str = chosen.to_string() if chosen is not None else None
        self._apply_color_string(color_str)

    def _apply_color_string(self, color_str: Optional[str]) -> None:
        """Apply *color_str* as the active override or selection override."""
        doc = self._doc
        editor = self._editor
        ribbon = self._ribbon

        if editor and editor.selection:
            editor.set_entity_properties(
                list(editor.selection.ids),
                "color",
                color_str,
                description="Change colour",
            )
        else:
            doc.active_color = color_str
            try:
                doc._notify()
            except Exception:
                _LOG.warning("doc._notify() failed after colour change", exc_info=True)

        ribbon.set_swatch_color(color_str)

    def _on_line_style_changed(self, value: str) -> None:
        """Apply line-style change from ribbon combo."""
        val = None if value == "" else value.lower()
        if self._editor and self._editor.selection:
            self._editor.set_entity_properties(
                list(self._editor.selection.ids), "line_style", val,
                description="Change line style",
            )
        else:
            self._doc.active_line_style = val

    def _on_line_weight_changed(self, value: str) -> None:
        """Apply line-weight change from ribbon combo."""
        if value == "":
            val = None
        else:
            try:
                val = float(value.split()[0])
            except (ValueError, IndexError):
                val = None
        if self._editor and self._editor.selection:
            self._editor.set_entity_properties(
                list(self._editor.selection.ids), "line_weight", val,
                description="Change line weight",
            )
        else:
            self._doc.active_thickness = val

    def _on_layer_changed(self, name: str) -> None:
        """Apply layer change from ribbon combo."""
        if self._editor and self._editor.selection:
            self._editor.set_entity_properties(
                list(self._editor.selection.ids), "layer", name,
                description="Change entity layer",
            )
        else:
            if self._editor:
                self._editor.set_active_layer(name)
            else:
                self._doc.active_layer = name

    # ------------------------------------------------------------------
    # Selection-driven control refresh
    # ------------------------------------------------------------------

    def _refresh_controls_from_selection(self) -> None:
        """Update ribbon controls to reflect the current selection state."""
        doc = self._doc
        editor = self._editor
        ribbon = self._ribbon
        if doc is None:
            return

        sel_ids = editor.selection.ids if editor else set()

        # ── layer combo ───────────────────────────────────────────────
        if sel_ids:
            layers = {
                doc.get_entity(eid).layer
                for eid in sel_ids
                if doc.get_entity(eid) is not None
            }
            layer_name = next(iter(layers)) if len(layers) == 1 else None
        else:
            layer_name = doc.active_layer
        ribbon.set_layer_selection(layer_name)

        # ── color swatch ──────────────────────────────────────────────
        if sel_ids:
            colors = {
                getattr(doc.get_entity(eid), "color", None)
                for eid in sel_ids
                if doc.get_entity(eid) is not None
            }
            color = next(iter(colors)) if len(colors) == 1 else None
        else:
            color = doc.active_color
        ribbon.set_swatch_color(color)

        # ── style combo ───────────────────────────────────────────────
        if sel_ids:
            styles = {
                getattr(doc.get_entity(eid), "line_style", None)
                for eid in sel_ids
                if doc.get_entity(eid) is not None
            }
            style_val = next(iter(styles)) if len(styles) == 1 else None
        else:
            style_val = doc.active_line_style
        ribbon.set_line_style_selection(style_val)

        # ── thickness combo ───────────────────────────────────────────
        if sel_ids:
            weights = {
                getattr(doc.get_entity(eid), "line_weight", None)
                for eid in sel_ids
                if doc.get_entity(eid) is not None
            }
            weight_val = next(iter(weights)) if len(weights) == 1 else None
        else:
            weight_val = doc.active_thickness
        ribbon.set_line_weight_selection(weight_val)

    # ------------------------------------------------------------------
    # Layer combo helpers
    # ------------------------------------------------------------------

    def _refresh_layers(self) -> None:
        """Repopulate the layer-select combos in the ribbon."""
        doc = self._doc
        if doc is None:
            return

        layer_names = [layer.name for layer in doc.layers]
        active = doc.active_layer
        self._ribbon.populate_layers(layer_names, active)
