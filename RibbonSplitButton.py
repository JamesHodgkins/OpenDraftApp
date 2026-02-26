from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QMenu, QHBoxLayout
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize
import os
from IconWidget import Icon


class RibbonSplitButton(QWidget):
    """
    Large ribbon split button:
      - Top: icon-only QToolButton (triggers main_action)
      - Bottom: text QToolButton with dropdown arrow (opens menu)
    For small=True, a compact single QToolButton with MenuButtonPopup.
    """
    def __init__(self, main_icon, main_label, items, main_action, parent=None, small=False):
        super().__init__(parent)

        # Build shared menu
        menu = QMenu(self)
        for item in items:
            icon_path = item.get("icon", "")
            icon_obj = None
            if icon_path:
                icon_name = os.path.splitext(os.path.basename(icon_path))[0]
                icon_widget = Icon(icon_name, size=24)
                pix = icon_widget.pixmap()
                if pix and not pix.isNull():
                    icon_obj = QIcon(pix)
            action = menu.addAction(icon_obj if icon_obj else QIcon(), item["label"])
            action.triggered.connect(item["action"])

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if small:
            # Two separate buttons: one for icon+label, one for dropdown arrow
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)

            # Icon + Label button
            icon_label_btn = QToolButton(self)
            icon_label_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            if main_icon:
                icon_name = os.path.splitext(os.path.basename(main_icon))[0]
                icon_widget = Icon(icon_name, size=24)
                pix = icon_widget.pixmap()
                if pix and not pix.isNull():
                    icon_label_btn.setIcon(QIcon(pix))
            icon_label_btn.setIconSize(QSize(24, 24))
            icon_label_btn.setText(main_label)
            icon_label_btn.setFixedSize(72, 28)
            icon_label_btn.clicked.connect(main_action)
            icon_label_btn.setStyleSheet(
                "QToolButton { font-size: 9px; font-weight: 500; border: none; background: transparent;"
                "  padding: 0 8px; text-align: left; }"
                "QToolButton:hover { background: rgba(0, 0, 0, 0.06); }"
                "QToolButton:pressed { background: rgba(0, 0, 0, 0.12); }"
            )

            # Dropdown arrow button
            arrow_btn = QToolButton(self)
            arrow_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            arrow_btn.setText("\u25BC")  # Add a single down arrow as text
            arrow_btn.setMenu(menu)
            arrow_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            arrow_btn.setFixedSize(20, 28)
            arrow_btn.setStyleSheet(
                "QToolButton { border: none; background: transparent; padding: 0; }"
                "QToolButton:hover { background: rgba(0,0,0,0.06); border-radius: 3px; }"
                "QToolButton:pressed { background: rgba(0,0,0,0.12); border-radius: 3px; }"
                "QToolButton::menu-indicator { image: url(none); width: 0; height: 0; }"  # Hide default menu indicator
            )

            layout.addWidget(icon_label_btn)
            layout.addWidget(arrow_btn)
            self.setLayout(layout)
            self.setFixedSize(92, 28)

        else:
            # Large 2-part layout: icon-only button on top, text dropdown below (vertical alignment)

            # Top: icon-only action button
            icon_btn = QToolButton(self)
            icon_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            if main_icon:
                icon_name = os.path.splitext(os.path.basename(main_icon))[0]
                icon_widget = Icon(icon_name, size=40)
                pix = icon_widget.pixmap()
                if pix and not pix.isNull():
                    icon_btn.setIcon(QIcon(pix))
            icon_btn.setIconSize(QSize(40, 40))
            icon_btn.setFixedSize(52, 44)
            icon_btn.clicked.connect(main_action)
            icon_btn.setStyleSheet(
                "QToolButton { border: none; background: transparent; padding: 2px; }"
                "QToolButton:hover { background: rgba(0,0,0,0.06); border-radius: 4px; }"
                "QToolButton:pressed { background: rgba(0,0,0,0.12); border-radius: 4px; }"
            )

            # Bottom: text label that opens menu on click (InstantPopup)
            drop_btn = QToolButton(self)
            drop_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            drop_btn.setText(f"{main_label} \u25BC")  # Unicode for down arrow
            drop_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            drop_btn.setMenu(menu)
            drop_btn.setFixedSize(52, 20)
            drop_btn.setStyleSheet(
                "QToolButton { font-size: 10px; font-weight: 500; border: none; background: transparent;"
                "  padding: 0 2px; text-align: center; }"
                "QToolButton:hover { background: rgba(0,0,0,0.06); border-radius: 3px; }"
                "QToolButton:pressed { background: rgba(0,0,0,0.12); border-radius: 3px; }"
                "QToolButton::menu-indicator { image: url(none); width: 0; height: 0; }"
            )

            layout.addWidget(icon_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(drop_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.setLayout(layout)
            self.setFixedSize(52, 64)

