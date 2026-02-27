"""
Main application window for OpenDraft.

Owns the ribbon configuration data and assembles the top-level layout.
"""
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtCore import Qt

from controls.ribbon import RibbonPanel
from app.canvas import CADCanvas
from app.document import DocumentStore
from app.editor import Editor
from app.entities import Vec2
import app.commands  # registers all @command decorators  # noqa: F401


# ---------------------------------------------------------------------------
# Ribbon configuration
# ---------------------------------------------------------------------------

RIBBON_STRUCTURE = [
    {"name": "Home",   "panels": ["File", "Edit", "Draw", "Annotate", "Modify", "Properties", "System"]},
    {"name": "Create", "panels": ["File", "Draw", "Annotate", "Hatch", "System"]},
    {"name": "Edit",   "panels": ["Edit", "Modify", "System"]},
    {"name": "View",   "panels": ["Properties", "System"]},
    {"name": "Review", "panels": ["Measure", "System"]},
    {"name": "Layout", "panels": ["Layout", "System"]},
    {"name": "Output", "panels": ["Export", "System"]},
]

PANEL_DEFINITIONS = {
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
        {"label": "Layers",         "icon": "util_layers",   "type": "large",        "action": "toggleLayerModal"},
        {"label": "Layer Selection","type": "select",         "source": "documentStore.layers"},
        {"label": "Color",          "type": "color-picker",  "source": "displayColor"},
        {"label": "Line Style",     "type": "select",
         "options": ["Continuous", "Dashed", "Dotted", "DashDot", "DashDotDot", "Center", "Phantom", "Hidden"]},
        {"label": "Thickness",      "type": "select",
         "options": ["0.25 mm", "0.50 mm", "1.00 mm", "2.00 mm", "3.00 mm"]},
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
# Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenDraft 2D CAD App")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        ribbon = RibbonPanel(
            RIBBON_STRUCTURE,
            PANEL_DEFINITIONS,
            dark=False,  # set True for dark mode
        )
        layout.addWidget(ribbon)
        # keep a reference to the canvas so we can connect signals
        canvas = CADCanvas()
        layout.addWidget(canvas)

        # ---- Editor -------------------------------------------------------
        doc = DocumentStore()
        self.editor = Editor(document=doc, parent=self)

        # Canvas left-click → provide world point to the active command
        canvas.pointSelected.connect(
            lambda x, y: self.editor.provide_point(Vec2(x, y))
        )
        # Give the canvas a reference to the active document so it can draw
        canvas._document = doc
        # Give the canvas a reference to the editor for rubberband preview
        canvas._editor = self.editor
        # Escape key on canvas → cancel the active command
        canvas.cancelRequested.connect(self.editor.cancel)

        # Ribbon button → run the corresponding command
        ribbon.actionTriggered.connect(self.editor.run_command)

        # Redraw the canvas whenever the document changes.
        # Use QueuedConnection to ensure canvas.refresh() is called on the GUI
        # thread even though document_changed is emitted from the worker thread.
        self.editor.document_changed.connect(
            canvas.refresh, Qt.ConnectionType.QueuedConnection
        )
        # -------------------------------------------------------------------

        # thin separator that visually separates the central content from the status bar
        sep = QFrame()
        sep.setObjectName("StatusSeparator")
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setLineWidth(0)
        sep.setMidLineWidth(0)
        sep.setFixedHeight(1)
        sep.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(sep)

        central = QWidget()
        central.setLayout(layout)
        central.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)

        # Status bar — command prompt (left) and cursor coordinates (right)
        self.cmd_label = QLabel("")
        self.coord_label = QLabel("X: 0.00 Y: 0.00")
        sb = self.statusBar()
        sb.setObjectName("MainStatusBar")
        # rely on the separator/QSS for the top border; remove forced inline styling
        sb.addWidget(self.cmd_label)              # stretches on the left
        sb.addPermanentWidget(self.coord_label)   # pinned to the right

        # Editor status message → left side of status bar
        self.editor.status_message.connect(self.cmd_label.setText)

        # update status with canvas mouse movement
        try:
            canvas.mouseMoved.connect(self._on_canvas_mouse_moved)
        except Exception:
            pass

    def _on_canvas_mouse_moved(self, x: float, y: float) -> None:
        self.coord_label.setText(f"X: {x:.2f} Y: {y:.2f}")
