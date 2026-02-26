"""
Panel Factory Module.

This module provides factory functions for creating ribbon panel widgets
from configuration dictionaries.
"""
from typing import Callable, Optional, Dict, Any
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QSize
from RibbonPanelWidget import RibbonPanel as RibbonPanelWidget
from RibbonSplitButton import RibbonSplitButton
from IconWidget import Icon
from ribbon_constants import SIZE, Styles, MARGINS


def create_panel_widget(
    panel_name: str,
    panel_def: Dict[str, Any],
    action_handler: Optional[Callable[[str], None]] = None,
    dark: bool = False
) -> RibbonPanelWidget:
    """
    Factory function to create a panel widget from a panel definition.
    
    Args:
        panel_name: Name of the panel
        panel_def: Dictionary containing panel configuration with 'tools' list
        action_handler: Optional callback function for handling button actions
        dark: Whether to use dark mode styling
        
    Returns:
        RibbonPanelWidget containing all the panel's tools
    """
    content = QWidget()
    content.setProperty("dark", dark)
    layout = QHBoxLayout()
    layout.setSpacing(SIZE.TOOL_SPACING)
    layout.setContentsMargins(*MARGINS.SMALL)

    small_btns = []
    for tool in panel_def.get("tools", []):
        if tool.get("type", "") == "split":
            items = tool.get("items", [])
            split_btn = RibbonSplitButton(
                main_icon=f"assets/icons/{items[0]['icon']}.png" if items and items[0].get('icon') else None,
                main_label=tool["label"],
                items=[{
                    "icon": f"assets/icons/{i['icon']}.png" if i.get('icon') else None,
                    "label": i["label"],
                    "action": (lambda act=i["action"]: (action_handler(act) if action_handler else print(act)))
                } for i in items],
                main_action=(lambda act=tool.get("mainAction", tool.get("action", tool["label"])): (action_handler(act) if action_handler else print(act))),
            )
            layout.addWidget(split_btn)
        elif tool.get("type", "") == "split-small":
            items = tool.get("items", [])
            split_btn = RibbonSplitButton(
                main_icon=f"assets/icons/{items[0]['icon']}.png" if items and items[0].get('icon') else None,
                main_label=tool["label"],
                items=[{
                    "icon": f"assets/icons/{i['icon']}.png" if i.get('icon') else None,
                    "label": i["label"],
                    "action": (lambda act=i["action"]: (action_handler(act) if action_handler else print(act)))
                } for i in items],
                main_action=(lambda act=tool.get("mainAction", tool.get("action", tool["label"])): (action_handler(act) if action_handler else print(act))),
                small=True
            )
            small_btns.append(split_btn)
        elif tool.get("type") == "small":
            btn = QPushButton()
            btn.setText(tool["label"])
            if tool.get("icon"):
                icon = Icon(tool["icon"], size=SIZE.SMALL_ICON_SIZE)
                pix = icon.pixmap()
                if pix and not pix.isNull():
                    btn.setIcon(pix)
                    btn.setIconSize(QSize(28, 20))
            btn.setFixedSize(SIZE.SMALL_BUTTON_WIDTH, SIZE.SMALL_BUTTON_HEIGHT)
            btn.setStyleSheet(Styles.small_button(dark))
            btn.clicked.connect(lambda _, act=tool.get("action", tool["label"]): (action_handler(act) if action_handler else print(act)))
            small_btns.append(btn)
        elif tool.get("type") == "stack" and "columns" in tool:
            # Render columns of small stacked buttons
            stack_widget = QWidget()
            stack_layout = QHBoxLayout()
            stack_layout.setSpacing(SIZE.TOOL_SPACING)
            stack_layout.setContentsMargins(*MARGINS.NONE)
            for col in tool["columns"]:
                col_widget = QWidget()
                col_layout = QVBoxLayout()
                col_layout.setSpacing(SIZE.STACK_SPACING)
                col_layout.setContentsMargins(*MARGINS.NONE)
                for btn_def in col:
                    btn = QPushButton()
                    btn.setText(btn_def["label"])
                    if btn_def.get("icon"):
                        icon = Icon(btn_def["icon"], size=SIZE.SMALL_ICON_SIZE)
                        pix = icon.pixmap()
                        if pix and not pix.isNull():
                            btn.setIcon(pix)
                            btn.setIconSize(QSize(28, 20))
                    btn.setFixedSize(SIZE.SMALL_BUTTON_WIDTH, SIZE.SMALL_BUTTON_HEIGHT)
                    btn.setStyleSheet(Styles.small_button(dark))
                    btn.clicked.connect(lambda _, act=btn_def.get("action", btn_def["label"]): (action_handler(act) if action_handler else print(act)))
                    col_layout.addWidget(btn, alignment=Qt.AlignLeft)
                col_layout.addStretch()
                col_widget.setLayout(col_layout)
                stack_layout.addWidget(col_widget)
            stack_widget.setLayout(stack_layout)
            layout.addWidget(stack_widget)
        else:
            # Large button: icon in square, label beneath
            btn_widget = QWidget()
            vbox = QVBoxLayout()
            vbox.setSpacing(0)
            vbox.setContentsMargins(0, 2, 0, 2)
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setFixedSize(SIZE.LARGE_ICON_LABEL_SIZE, SIZE.LARGE_ICON_LABEL_SIZE)
            if tool.get("icon"):
                icon = Icon(tool["icon"], size=SIZE.LARGE_ICON_SIZE)
                pix = icon.pixmap()
                if pix and not pix.isNull():
                    icon_label.setPixmap(pix)
                else:
                    # fallback: draw a placeholder
                    icon_label.setText('?')
                    icon_label.setStyleSheet('color: #888; font-size: 18px;')
            vbox.addWidget(icon_label, alignment=Qt.AlignHCenter)
            text_label = QLabel(tool["label"])
            text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            text_label.setStyleSheet(
                f"font-size: {Styles.FONT_SIZE_SMALL}px; "
                f"color: #eee; margin-top: 0px; margin-bottom: 0px;"
            )
            vbox.addWidget(text_label, alignment=Qt.AlignHCenter)
            btn_widget.setLayout(vbox)
            btn_widget.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
            btn_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            # Overlay a transparent QPushButton for click
            btn = QPushButton(btn_widget)
            btn.setFlat(True)
            btn.setStyleSheet("QPushButton { background: transparent; border: none; }")
            btn.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
            btn.clicked.connect(lambda _, act=tool.get("action", tool["label"]): (action_handler(act) if action_handler else print(act)))
            btn.raise_()
            layout.addWidget(btn_widget)

    if small_btns:
        small_col = QWidget()
        vbox = QVBoxLayout()
        vbox.setSpacing(SIZE.STACK_SPACING)
        vbox.setContentsMargins(*MARGINS.NONE)
        for b in small_btns:
            vbox.addWidget(b, alignment=Qt.AlignLeft)
        vbox.addStretch()
        small_col.setLayout(vbox)
        layout.addWidget(small_col)

    content.setLayout(layout)
    return RibbonPanelWidget(panel_name, content, dark=dark)
