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

from app.sdk.commands.spec import CommandSpec
from controls.ribbon.ribbon_models import RibbonConfiguration

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------

RIBBON_STRUCTURE: List[Dict[str, Any]] = [
    {"name": "Home",   "panels": ["File", "Edit", "Draw", "Annotate", "Modify", "Properties", "System"]},
    {"name": "Create", "panels": ["File", "Draw", "Annotate", "Hatch"]},
    {"name": "Edit",   "panels": ["Edit", "Modify"]},
    {"name": "View",   "panels": ["Properties"]},
    {"name": "Review", "panels": ["Measure"]},
    {"name": "Layout", "panels": ["Layout"]},
    {"name": "Output", "panels": ["Export"]},
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
            {"label": "Arc (3 Points)",           "icon": "draw_arc", "action": "arc3PointCommand"},
            {"label": "Arc (Center, Start, End)", "icon": "draw_arc", "action": "arcCenterStartEndCommand"},
            {"label": "Arc (Start, End, Radius)", "icon": "draw_arc", "action": "arcStartEndRadiusCommand"},
        ]},
        {"label": "Text",    "icon": "draw_text",    "type": "large",  "action": "textCommand"},
        {"label": "Spline",  "icon": "draw_spline",  "type": "small",  "action": "splineCommand"},
        {"label": "Ellipse", "icon": "draw_ellipse", "type": "small",  "action": "ellipseCommand"},
        {"label": "Point",   "icon": "draw_point",   "type": "small",  "action": "pointCommand"},
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
                {"label": "Rotate",  "icon": "mod_rotate",  "type": "small", "action": "rotateCommand"},
                {"label": "Scale",   "icon": "mod_scale",   "type": "small", "action": "scaleCommand"},
                {"label": "Mirror",  "icon": "mod_mirror",  "type": "small", "action": "mirrorCommand"},
            ],
            [
                {"label": "Trim",    "icon": "mod_trim",    "type": "small", "action": "trimCommand"},
                {"label": "Extend",  "icon": "mod_extend",  "type": "small", "action": "extendCommand"},
                {"label": "Delete",  "icon": "icon-cancel", "type": "small", "action": "deleteCommand"},
            ],
            [
                {"label": "Fillet",  "icon": "mod_fillet",  "type": "small", "action": "filletCommand"},
                {"label": "Chamfer", "icon": "mod_chamfer", "type": "small", "action": "chamferCommand"},
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


def _append_command_spec(
    specs: Dict[str, CommandSpec],
    *,
    command_id: str,
    label: str | None,
    category: str,
    icon: str | None,
    source: str,
    min_api_version: str,
) -> None:
    existing = specs.get(command_id)
    if existing is None:
        specs[command_id] = CommandSpec(
            id=command_id,
            display_name=label,
            category=category,
            icon=icon,
            source=source,
            min_api_version=min_api_version,
        )
        return

    # Keep first non-empty values while allowing later entries to fill gaps.
    specs[command_id] = CommandSpec(
        id=command_id,
        display_name=existing.display_name or label,
        description=existing.description,
        category=existing.category if existing.category != "General" else category,
        aliases=existing.aliases,
        icon=existing.icon or icon,
        source=existing.source or source,
        min_api_version=existing.min_api_version or min_api_version,
    )


def _walk_panel_tools(
    panel_name: str,
    tools: List[Dict[str, Any]],
    specs: Dict[str, CommandSpec],
    *,
    source: str,
    min_api_version: str,
) -> None:
    for tool in tools:
        tool_type = str(tool.get("type", ""))

        if tool_type in ("split", "split-small"):
            main_action = tool.get("mainAction")
            if isinstance(main_action, str) and main_action:
                _append_command_spec(
                    specs,
                    command_id=main_action,
                    label=tool.get("label"),
                    category=panel_name,
                    icon=tool.get("icon"),
                    source=source,
                    min_api_version=min_api_version,
                )
            for item in tool.get("items", []):
                action = item.get("action")
                if isinstance(action, str) and action:
                    _append_command_spec(
                        specs,
                        command_id=action,
                        label=item.get("label"),
                        category=panel_name,
                        icon=item.get("icon"),
                        source=source,
                        min_api_version=min_api_version,
                    )
            continue

        if tool_type == "stack":
            for column in tool.get("columns", []):
                if isinstance(column, list):
                    _walk_panel_tools(
                        panel_name,
                        column,
                        specs,
                        source=source,
                        min_api_version=min_api_version,
                    )
            continue

        action = tool.get("action")
        if isinstance(action, str) and action:
            _append_command_spec(
                specs,
                command_id=action,
                label=tool.get("label"),
                category=panel_name,
                icon=tool.get("icon"),
                source=source,
                min_api_version=min_api_version,
            )


def _collect_actions_from_tools(tools: List[Dict[str, Any]], actions: set[str]) -> None:
    for tool in tools:
        tool_type = str(tool.get("type", ""))

        if tool_type in ("split", "split-small"):
            main_action = tool.get("mainAction")
            if isinstance(main_action, str) and main_action:
                actions.add(main_action)
            for item in tool.get("items", []):
                action = item.get("action")
                if isinstance(action, str) and action:
                    actions.add(action)
            continue

        if tool_type == "stack":
            for column in tool.get("columns", []):
                if isinstance(column, list):
                    _collect_actions_from_tools(column, actions)
            continue

        action = tool.get("action")
        if isinstance(action, str) and action:
            actions.add(action)


def command_specs_from_ribbon(
    panel_definitions: Dict[str, Dict[str, Any]] | None = None,
    *,
    source: str = "core",
    min_api_version: str = "1.0",
) -> Dict[str, CommandSpec]:
    """Build command metadata specs from ribbon panel definitions."""
    defs = panel_definitions if panel_definitions is not None else PANEL_DEFINITIONS
    specs: Dict[str, CommandSpec] = {}
    for panel_name, panel_def in defs.items():
        tools = panel_def.get("tools", [])
        if isinstance(tools, list):
            _walk_panel_tools(
                panel_name,
                tools,
                specs,
                source=source,
                min_api_version=min_api_version,
            )
    return specs


def ribbon_action_names(
    panel_definitions: Dict[str, Dict[str, Any]] | None = None,
) -> set[str]:
    """Return all ribbon action IDs referenced by panel definitions."""
    defs = panel_definitions if panel_definitions is not None else PANEL_DEFINITIONS
    actions: set[str] = set()
    for panel_def in defs.values():
        tools = panel_def.get("tools", [])
        if isinstance(tools, list):
            _collect_actions_from_tools(tools, actions)
    return actions

# ---------------------------------------------------------------------------
# Typed configuration (preferred over the raw-dict constants above)
# ---------------------------------------------------------------------------
# Built once at import time so every consumer shares the same object graph.
# ``RIBBON_STRUCTURE`` and ``PANEL_DEFINITIONS`` are kept for reference and
# to support any legacy code that still reads them directly.

RIBBON_CONFIG: RibbonConfiguration = RibbonConfiguration.from_dict(
    RIBBON_STRUCTURE, PANEL_DEFINITIONS
)
