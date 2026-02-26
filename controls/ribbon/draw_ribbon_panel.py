"""
Draw Ribbon Panel.

A pre-built panel that groups the common drawing tools (Line, Rect, Circle,
Arc, Text) using the ribbon primitives.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton

from controls.ribbon.ribbon_panel_widget import RibbonPanel
from controls.ribbon.ribbon_split_button import RibbonSplitButton
from controls.icon_widget import Icon


class DrawRibbonPanel(QWidget):
    """Ready-made ribbon panel for the 'Draw' toolbar group."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        content = QWidget()
        vlayout = QVBoxLayout()
        vlayout.setSpacing(4)
        vlayout.setContentsMargins(0, 0, 0, 0)

        # --- Top row: Line split button ---
        line_items = [
            {"icon": "assets/icons/draw_line.png", "label": "Line",    "action": lambda: print("Line")},
            {"icon": "assets/icons/draw_pline.png", "label": "Polyline", "action": lambda: print("Polyline")},
        ]
        vlayout.addWidget(
            RibbonSplitButton("assets/icons/draw_line.png", "Line", line_items, lambda: print("Line"))
        )

        # --- Middle row: Rect, Circle, Arc (small) ---
        small_group = QHBoxLayout()

        rect_btn = QPushButton()
        rect_btn.setFixedSize(48, 48)
        rect_btn.setIconSize(rect_btn.size())
        rect_btn.setIcon(Icon("draw_rect").pixmap())
        rect_btn.setText("Rect")
        rect_btn.clicked.connect(lambda: print("Rect"))

        circle_btn = QPushButton()
        circle_btn.setFixedSize(48, 48)
        circle_btn.setIconSize(circle_btn.size())
        circle_btn.setIcon(Icon("draw_circle").pixmap())
        circle_btn.setText("Circle")
        circle_btn.clicked.connect(lambda: print("Circle"))

        arc_items = [
            {"icon": "assets/icons/draw_arc.png", "label": "Arc (Center, Start, End)", "action": lambda: print("Arc CSE")},
            {"icon": "assets/icons/draw_arc.png", "label": "Arc (Start, End, Radius)", "action": lambda: print("Arc SER")},
        ]
        arc_split = RibbonSplitButton(
            "assets/icons/draw_arc.png", "Arc", arc_items, lambda: print("Arc"), small=True
        )

        small_group.addWidget(rect_btn)
        small_group.addWidget(circle_btn)
        small_group.addWidget(arc_split)
        small_group.addStretch()
        vlayout.addLayout(small_group)

        # --- Bottom row: Text ---
        text_btn = QPushButton()
        text_btn.setFixedSize(80, 64)
        text_btn.setIconSize(text_btn.size())
        text_btn.setIcon(Icon("draw_text", size=48).pixmap())
        text_btn.setText("Text")
        text_btn.clicked.connect(lambda: print("Text"))
        vlayout.addWidget(text_btn)

        vlayout.addStretch()
        content.setLayout(vlayout)

        panel = RibbonPanel("Draw", content, grid_class="draw-grid")
        main_layout = QVBoxLayout()
        main_layout.addWidget(panel)
        self.setLayout(main_layout)
