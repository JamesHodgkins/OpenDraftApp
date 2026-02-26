from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

class RibbonPanel(QFrame):
    def __init__(self, title: str, content_widget, grid_class: str = None, parent=None, dark=False):
        super().__init__(parent)
        self.setObjectName("RibbonPanel")
        self.setProperty("dark", dark)
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        # Content
        layout.addWidget(content_widget)
        # Panel label at the bottom, smaller and less bold
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        title_label.setProperty("ribbonPanelTitle", True)
        title_label.setProperty("dark", dark)
        title_label.setStyleSheet("font-size: 10px; color: #aaa; font-weight: normal; margin-top: 2px; margin-bottom: 1px;")
        layout.addWidget(title_label, alignment=Qt.AlignHCenter | Qt.AlignBottom)
        self.setLayout(layout)
