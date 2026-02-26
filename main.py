from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from RibbonPanel import RibbonPanel
from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import Qt
import sys

class CADCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 600)

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)
        # Example: Draw a simple line
        painter.drawLine(100, 100, 300, 300)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenDraft 2D CAD App")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # Ribbon structure and panel definitions (from your JSON)
        ribbon_structure = [
            {"name": "Home", "panels": ["File", "Edit", "Draw", "Annotate", "Modify", "Properties", "System"]},
            {"name": "Create", "panels": ["File", "Draw", "Annotate", "Hatch", "System"]},
            {"name": "Edit", "panels": ["Edit", "Modify", "System"]},
            {"name": "View", "panels": ["Properties", "System"]},
            {"name": "Review", "panels": ["Measure", "System"]},
            {"name": "Layout", "panels": ["Layout", "System"]},
            {"name": "Output", "panels": ["Export", "System"]},
        ]
        panel_definitions = {
            "File": {"tools": [
                {"label": "New", "icon": "file_new", "type": "large", "action": "newDocument"},
                {"label": "Save", "icon": "file_save", "type": "small", "action": "saveDocumentToFile"},
                {"label": "Open", "icon": "file_open", "type": "small", "action": "openDocumentFromFile"}
            ]},
            "Edit": {"tools": [
                {"label": "Undo", "icon": "edit_undo", "type": "large", "action": "undo"},
                {"label": "Redo", "icon": "edit_redo", "type": "large", "action": "redo"}
            ]},
            "Draw": {"tools": [
                {"label": "Line", "type": "split", "mainAction": "lineCommand", "items": [
                    {"label": "Line", "icon": "draw_line", "action": "lineCommand"},
                    {"label": "Polyline", "icon": "draw_pline", "action": "polylineCommand"}
                ]},
                {"label": "Rect", "icon": "draw_rect", "type": "small", "action": "rectCommand"},
                {"label": "Circle", "icon": "draw_circle", "type": "small", "action": "circleCommand"},
                {"label": "Arc", "type": "split-small", "mainAction": "arc3PointCommand", "items": [
                    {"label": "Arc (Center, Start, End)", "icon": "draw_arc", "action": "arcCenterStartEndCommand"},
                    {"label": "Arc (Start, End, Radius)", "icon": "draw_arc", "action": "arcStartEndRadiusCommand"}
                ]},
                {"label": "Text", "icon": "draw_text", "type": "large", "action": "textCommand"}
            ]},
            "Annotate": {"tools": [
                {"label": "Dimension", "type": "split", "mainAction": "linearDimensionCommand", "items": [
                    {"label": "Linear Dimension", "icon": "util_lin_dim", "action": "linearDimensionCommand"},
                    {"label": "Aligned Dimension", "icon": "util_aln_dim", "action": "alignedDimensionCommand"}
                ]}
            ]},
            "Modify": {"tools": [
                {"label": "Move", "icon": "mod_move", "type": "large", "action": "moveCommand"},
                {"label": "Copy", "icon": "mod_copy", "type": "large", "action": "copyCommand"},
                {"type": "stack", "columns": [
                    [
                        {"label": "Rotate", "icon": "mod_rotate", "type": "small", "action": "rotateCommand"},
                        {"label": "Scale", "icon": "mod_scale", "type": "small", "action": "scaleCommand"},
                        {"label": "Mirror", "icon": "mod_mirror", "type": "small", "action": "mirrorCommand"}
                    ],
                    [
                        {"label": "Trim", "icon": "mod_trim", "type": "small", "action": "trimCommand"},
                        {"label": "Extend", "icon": "mod_extend", "type": "small", "action": "extendCommand"},
                        {"label": "Delete", "icon": "icon-cancel", "type": "small", "action": "deleteCommand"}
                    ]
                ]}
            ]},
            "Properties": {"tools": [
                {"label": "Layers", "icon": "util_layers", "type": "large", "action": "toggleLayerModal"},
                {"label": "Layer Selection", "type": "select", "source": "documentStore.layers"},
                {"label": "Color", "type": "color-picker", "source": "displayColor"},
                {"label": "Line Style", "type": "select", "options": ["Continuous", "Dashed", "Dotted", "DashDot", "DashDotDot", "Center", "Phantom", "Hidden"]},
                {"label": "Thickness", "type": "select", "options": ["0.25 mm", "0.50 mm", "1.00 mm", "2.00 mm", "3.00 mm"]}
            ]},
            "System": {"tools": [
                {"label": "Properties", "icon": "util_props", "type": "large", "action": "togglePropertiesPanel"},
                {"label": "Settings", "icon": "util_settings", "type": "large", "action": "toggleSettingsModal"},
                {"label": "Cancel", "icon": "icon-cancel", "type": "large", "action": "cancelCommand"}
            ]},
            "Hatch": {"tools": [
                {"label": "Draw Hatch", "icon": "draw_hatch_draw", "type": "large", "status": "placeholder"},
                {"label": "Pick Hatch", "icon": "draw_hatch_pick", "type": "large", "status": "placeholder"},
                {"label": "Shape Hatch", "icon": "draw_hatch_shape", "type": "large", "action": "shapeHatchCommand"}
            ]},
            "Measure": {"tools": [
                {"label": "Distance", "icon": "util_meas_length", "type": "large", "action": "measureDistanceCommand"},
                {"label": "Angle", "icon": "util_meas_angle", "type": "large", "status": "placeholder"},
                {"label": "Area", "icon": "util_meas_area", "type": "large", "action": "measureAreaCommand"}
            ]},
            "Layout": {"tools": [
                {"label": "Viewport", "icon": "util_props", "type": "large", "action": "placeViewportCommand"},
                {"label": "Paper Size", "type": "select", "options": ["A4 Landscape", "A4 Portrait", "A3 Landscape", "A3 Portrait", "A2 Landscape", "A2 Portrait", "Letter", "Tabloid"]}
            ]},
            "Export": {"tools": [
                {"label": "Export PDF", "icon": "utils_exp_pdf", "type": "large", "status": "placeholder"},
                {"label": "Export SVG", "icon": "utils_exp_svg", "type": "large", "status": "placeholder"}
            ]}
        }
        # Add RibbonPanel at the top
        # Set dark mode here if desired
        dark_mode = False  # Set to True for dark mode
        ribbon_panel = RibbonPanel(ribbon_structure, panel_definitions, dark=dark_mode)
        layout.addWidget(ribbon_panel)
        layout.addWidget(CADCanvas())
        central = QWidget()
        central.setLayout(layout)
        central.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Load RibbonPanel stylesheet
    try:
        with open("ribbon.qss", "r") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"Could not load ribbon.qss: {e}")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
