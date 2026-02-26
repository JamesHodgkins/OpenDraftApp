from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from RibbonPanelWidget import RibbonPanel
from RibbonSplitButton import RibbonSplitButton
from IconWidget import Icon

class DrawRibbonPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        content = QWidget()
        vlayout = QVBoxLayout()
        vlayout.setSpacing(4)
        vlayout.setContentsMargins(0, 0, 0, 0)

        # Top row: Line split button
        line_items = [
            {'icon': 'assets/icons/draw_line.png', 'label': 'Line', 'action': lambda: print('Line')},
            {'icon': 'assets/icons/draw_pline.png', 'label': 'Polyline', 'action': lambda: print('Polyline')},
        ]
        line_split = RibbonSplitButton('assets/icons/draw_line.png', 'Line', line_items, lambda: print('Line'))
        vlayout.addWidget(line_split)

        # Middle row: small buttons group
        small_group = QHBoxLayout()
        rect_btn = QPushButton()
        rect_btn.setFixedSize(48, 48)
        rect_btn.setIconSize(rect_btn.size())
        rect_btn.setIcon(Icon('draw_rect').pixmap())
        rect_btn.setText('Rect')
        rect_btn.clicked.connect(lambda: print('Rect'))

        circle_btn = QPushButton()
        circle_btn.setFixedSize(48, 48)
        circle_btn.setIconSize(circle_btn.size())
        circle_btn.setIcon(Icon('draw_circle').pixmap())
        circle_btn.setText('Circle')
        circle_btn.clicked.connect(lambda: print('Circle'))

        arc_items = [
            {'icon': 'assets/icons/draw_arc.png', 'label': 'Arc (Center, Start, End)', 'action': lambda: print('Arc Center Start End')},
            {'icon': 'assets/icons/draw_arc.png', 'label': 'Arc (Start, End, Radius)', 'action': lambda: print('Arc Start End Radius')},
        ]
        arc_split = RibbonSplitButton('assets/icons/draw_arc.png', 'Arc', arc_items, lambda: print('Arc'), small=True)

        small_group.addWidget(rect_btn)
        small_group.addWidget(circle_btn)
        small_group.addWidget(arc_split)
        small_group.addStretch()
        vlayout.addLayout(small_group)

        # Bottom row: Large text button
        text_btn = QPushButton()
        text_btn.setFixedSize(80, 64)
        text_btn.setIconSize(text_btn.size())
        text_btn.setIcon(Icon('draw_text', size=48).pixmap())
        text_btn.setText('Text')
        text_btn.clicked.connect(lambda: print('Text'))
        vlayout.addWidget(text_btn)

        vlayout.addStretch()
        content.setLayout(vlayout)
        # Wrap in RibbonPanel
        panel = RibbonPanel('Draw', content, grid_class='draw-grid')
        main_layout = QVBoxLayout()
        main_layout.addWidget(panel)
        self.setLayout(main_layout)
