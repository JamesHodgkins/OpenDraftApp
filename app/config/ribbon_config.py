"""
Ribbon layout configuration for OpenDraft.

Separating the ribbon data from the window code means:
- Adding a new tab, panel, or button requires editing only this file.
- MainWindow stays focused on wiring — not on data.

``RIBBON_STRUCTURE`` lists the ribbon tabs in display order.  Each entry
maps a tab name to the ordered list of panel names shown in that tab.

``PANEL_DEFINITIONS`` maps panel names to their tool lists.  Each tool
definition is a plain dict; the ribbon factory coerces it to the
appropriate typed model when building the widget.
"""
from __future__ import annotations

from typing import Any, Dict, List

from controls.ribbon.ribbon_models import RibbonConfiguration

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------

RIBBON_STRUCTURE: List[Dict[str, Any]] = [
    {"name": "Home",   "panels": ["File", "Edit", "Draw", "Annotate", "Modify", "Properties", "System"]},
    {"name": "Create", "panels": ["File", "Draw", "Annotate", "Hatch", "System"]},
    {"name": "Edit",   "panels": ["Edit", "Modify", "System"]},
    {"name": "View",   "panels": ["Properties", "System"]},
    {"name": "Review", "panels": ["Measure", "System"]},
    {"name": "Layout", "panels": ["Layout", "System"]},
    {"name": "Output", "panels": ["Export", "System"]},
]

# ---------------------------------------------------------------------------
# Panel definitions
# ---------------------------------------------------------------------------

PANEL_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "File": {"tools": [
        {"label": "New",  "icon": "file_new",  "type": "large", "action": "newDocument"},
        {"label": "Save", "icon": "file_save", "type": "small", "action": "saveDocumentToFile"},
        {"label": "Open", "icon": "file_open", "type": "small", "action": "openDocumentFromFile"},
    ]},
    "Edit": {"tools": [
        {"label": "Undo", "icon": "edit_undo", "type": "large", "action": "undo"},
        {"label": "Redo", "icon": "edit_redo", "type": "large", "action": "redo"},
    ]},
    "Draw": {"tools": [
        {"label": "Line", "type": "split", "mainAction": "lineCommand", "items": [
            {"label": "Line",     "icon": "draw_line",  "action": "lineCommand"},
            {"label": "Polyline", "icon": "draw_pline", "action": "polylineCommand"},
        ]},
        {"label": "Rect",   "icon": "draw_rect",   "type": "small", "action": "rectCommand"},
        {"label": "Circle", "icon": "draw_circle", "type": "small", "action": "circleCommand"},
        {"label": "Arc", "type": "split-small", "mainAction": "arc3PointCommand", "items": [
            {"label": "Arc (Center, Start, End)", "icon": "draw_arc", "action": "arcCenterStartEndCommand"},
            {"label": "Arc (Start, End, Radius)", "icon": "draw_arc", "action": "arcStartEndRadiusCommand"},
        ]},
        {"label": "Text", "icon": "draw_text", "type": "large", "action": "textCommand"},
    ]},
    "Annotate": {"tools": [
        {"label": "Dimension", "type": "split", "mainAction": "linearDimensionCommand", "items": [
            {"label": "Linear Dimension",  "icon": "util_lin_dim", "action": "linearDimensionCommand"},
            {"label": "Aligned Dimension", "icon": "util_aln_dim", "action": "alignedDimensionCommand"},
        ]},
    ]},
    "Modify": {"tools": [
        {"label": "Move", "icon": "mod_move", "type": "large", "action": "moveCommand"},
        {"label": "Copy", "icon": "mod_copy", "type": "large", "action": "copyCommand"},
        {"type": "stack", "columns": [
            [
                {"label": "Rotate", "icon": "mod_rotate", "type": "small", "action": "rotateCommand"},
                {"label": "Scale",  "icon": "mod_scale",  "type": "small", "action": "scaleCommand"},
                {"label": "Mirror", "icon": "mod_mirror", "type": "small", "action": "mirrorCommand"},
            ],
            [
                {"label": "Trim",   "icon": "mod_trim",   "type": "small", "action": "trimCommand"},
                {"label": "Extend", "icon": "mod_extend", "type": "small", "action": "extendCommand"},
                {"label": "Delete", "icon": "icon-cancel", "type": "small", "action": "deleteCommand"},
            ],
        ]},
    ]},
    "Properties": {"tools": [
        {"label": "Layers",  "icon": "util_layers",  "type": "large",         "action": "toggleLayerModal"},
        {"label": "Layer",   "type": "layer-select"},
        {"type": "prop-stack", "rows": [
            {"label": "Color",  "type": "color-swatch"},
            {"label": "Style",  "type": "select",
             "options": ["Continuous", "Dashed", "Dotted", "DashDot", "DashDotDot", "Center", "Phantom", "Hidden"]},
            {"label": "Weight", "type": "select",
             "options": ["0.25 mm", "0.50 mm", "1.00 mm", "2.00 mm", "3.00 mm"]},
        ]},
    ]},
    "System": {"tools": [
        {"label": "Properties", "icon": "util_props",     "type": "large", "action": "togglePropertiesPanel"},
        {"label": "Settings",   "icon": "util_settings",  "type": "large", "action": "toggleSettingsModal"},
        {"label": "Cancel",     "icon": "icon-cancel",    "type": "large", "action": "cancelCommand"},
    ]},
    "Hatch": {"tools": [
        {"label": "Draw Hatch",  "icon": "draw_hatch_draw",  "type": "large", "status": "placeholder"},
        {"label": "Pick Hatch",  "icon": "draw_hatch_pick",  "type": "large", "status": "placeholder"},
        {"label": "Shape Hatch", "icon": "draw_hatch_shape", "type": "large", "action": "shapeHatchCommand"},
    ]},
    "Measure": {"tools": [
        {"label": "Distance", "icon": "util_meas_length", "type": "large", "action": "measureDistanceCommand"},
        {"label": "Angle",    "icon": "util_meas_angle",  "type": "large", "status": "placeholder"},
        {"label": "Area",     "icon": "util_meas_area",   "type": "large", "action": "measureAreaCommand"},
    ]},
    "Layout": {"tools": [
        {"label": "Viewport",   "icon": "util_props", "type": "large", "action": "placeViewportCommand"},
        {"label": "Paper Size", "type": "select",
         "options": ["A4 Landscape", "A4 Portrait", "A3 Landscape", "A3 Portrait",
                     "A2 Landscape", "A2 Portrait", "Letter", "Tabloid"]},
    ]},
    "Export": {"tools": [
        {"label": "Export PDF", "icon": "utils_exp_pdf", "type": "large", "status": "placeholder"},
        {"label": "Export SVG", "icon": "utils_exp_svg", "type": "large", "status": "placeholder"},
    ]},
}

# ---------------------------------------------------------------------------
# Typed configuration (preferred over the raw-dict constants above)
# ---------------------------------------------------------------------------
# Built once at import time so every consumer shares the same object graph.
# ``RIBBON_STRUCTURE`` and ``PANEL_DEFINITIONS`` are kept for reference and
# to support any legacy code that still reads them directly.

RIBBON_CONFIG: RibbonConfiguration = RibbonConfiguration.from_dict(
    RIBBON_STRUCTURE, PANEL_DEFINITIONS
)
