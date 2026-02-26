"""
Panel Factory Module.

Factory function for building a complete RibbonPanel widget from a plain-dict
panel definition (the format used in main_window.py).
"""
from typing import Callable, Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize

from controls.ribbon.ribbon_panel_widget import RibbonPanel as RibbonPanelWidget
from controls.ribbon.ribbon_split_button import RibbonSplitButton
from controls.icon_widget import Icon
from controls.ribbon.ribbon_constants import SIZE, Styles, MARGINS


def create_panel_widget(
    panel_name: str,
    panel_def: Dict[str, Any],
    action_handler: Optional[Callable[[str], None]] = None,
    dark: bool = False,
) -> RibbonPanelWidget:
    """
    Build a :class:`RibbonPanelWidget` from a panel definition dictionary.

    Args:
        panel_name: Display name for the panel.
        panel_def: Dict with a ``'tools'`` list describing each tool.
        action_handler: Optional callback invoked with the action-name string
                        when a button is clicked.  Defaults to ``print``.
        dark: Whether to apply dark-mode styling.

    Returns:
        A fully populated :class:`RibbonPanelWidget`.
    """
    content = QWidget()
    content.setProperty("dark", dark)
    layout = QHBoxLayout()
    layout.setSpacing(SIZE.TOOL_SPACING)
    layout.setContentsMargins(*MARGINS.SMALL)

    small_btns = []

    for tool in panel_def.get("tools", []):
        tool_type = tool.get("type", "")

        if tool_type == "split":
            # Flush any accumulated small buttons first
            if small_btns:
                layout.addWidget(_small_column(small_btns))
                small_btns = []
            items = tool.get("items", [])
            split_btn = RibbonSplitButton(
                main_icon=f"assets/icons/{items[0]['icon']}.png"
                if items and items[0].get("icon")
                else None,
                main_label=tool["label"],
                items=[
                    {
                        "icon": f"assets/icons/{i['icon']}.png" if i.get("icon") else None,
                        "label": i["label"],
                        "action": _make_callback(i["action"], action_handler),
                    }
                    for i in items
                ],
                main_action=_make_callback(
                    tool.get("mainAction", tool.get("action", tool["label"])),
                    action_handler,
                ),
            )
            layout.addWidget(split_btn)

        elif tool_type == "split-small":
            items = tool.get("items", [])
            split_btn = RibbonSplitButton(
                main_icon=f"assets/icons/{items[0]['icon']}.png"
                if items and items[0].get("icon")
                else None,
                main_label=tool["label"],
                items=[
                    {
                        "icon": f"assets/icons/{i['icon']}.png" if i.get("icon") else None,
                        "label": i["label"],
                        "action": _make_callback(i["action"], action_handler),
                    }
                    for i in items
                ],
                main_action=_make_callback(
                    tool.get("mainAction", tool.get("action", tool["label"])),
                    action_handler,
                ),
                small=True,
            )
            small_btns.append(split_btn)

        elif tool_type == "small":
            btn = QPushButton()
            btn.setText(tool["label"])
            if tool.get("icon"):
                pix = Icon(tool["icon"], size=SIZE.SMALL_ICON_SIZE).pixmap()
                if pix and not pix.isNull():
                    btn.setIcon(pix)
                    btn.setIconSize(QSize(28, 20))
            btn.setFixedSize(SIZE.SMALL_BUTTON_WIDTH, SIZE.SMALL_BUTTON_HEIGHT)
            btn.setStyleSheet(Styles.small_button(dark))
            btn.clicked.connect(
                _make_callback(tool.get("action", tool["label"]), action_handler)
            )
            small_btns.append(btn)

        elif tool_type == "stack" and "columns" in tool:
            if small_btns:
                layout.addWidget(_small_column(small_btns))
                small_btns = []
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
                    b = QPushButton()
                    b.setText(btn_def["label"])
                    if btn_def.get("icon"):
                        pix = Icon(btn_def["icon"], size=SIZE.SMALL_ICON_SIZE).pixmap()
                        if pix and not pix.isNull():
                            b.setIcon(pix)
                            b.setIconSize(QSize(28, 20))
                    b.setFixedSize(SIZE.SMALL_BUTTON_WIDTH, SIZE.SMALL_BUTTON_HEIGHT)
                    b.setStyleSheet(Styles.small_button(dark))
                    b.clicked.connect(
                        _make_callback(btn_def.get("action", btn_def["label"]), action_handler)
                    )
                    col_layout.addWidget(b, alignment=Qt.AlignLeft)
                col_layout.addStretch()
                col_widget.setLayout(col_layout)
                stack_layout.addWidget(col_widget)
            stack_widget.setLayout(stack_layout)
            layout.addWidget(stack_widget)

        else:
            # Large button: icon square + label beneath
            if small_btns:
                layout.addWidget(_small_column(small_btns))
                small_btns = []
            btn_widget = QWidget()
            vbox = QVBoxLayout()
            vbox.setSpacing(0)
            vbox.setContentsMargins(0, 2, 0, 2)
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setFixedSize(SIZE.LARGE_ICON_LABEL_SIZE, SIZE.LARGE_ICON_LABEL_SIZE)
            if tool.get("icon"):
                pix = Icon(tool["icon"], size=SIZE.LARGE_ICON_SIZE).pixmap()
                if pix and not pix.isNull():
                    icon_label.setPixmap(pix)
                else:
                    icon_label.setText("?")
                    icon_label.setStyleSheet("color: #888; font-size: 18px;")
            vbox.addWidget(icon_label, alignment=Qt.AlignHCenter)
            text_label = QLabel(tool["label"])
            text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            text_label.setStyleSheet(
                f"font-size: {Styles.FONT_SIZE_SMALL}px; "
                "color: #eee; margin-top: 0px; margin-bottom: 0px;"
            )
            vbox.addWidget(text_label, alignment=Qt.AlignHCenter)
            btn_widget.setLayout(vbox)
            btn_widget.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
            btn_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            # Transparent overlay button for click events
            btn = QPushButton(btn_widget)
            btn.setFlat(True)
            btn.setStyleSheet("QPushButton { background: transparent; border: none; }")
            btn.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
            btn.clicked.connect(
                _make_callback(tool.get("action", tool["label"]), action_handler)
            )
            btn.raise_()
            layout.addWidget(btn_widget)

    if small_btns:
        layout.addWidget(_small_column(small_btns))

    content.setLayout(layout)
    return RibbonPanelWidget(panel_name, content, dark=dark)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_callback(action: str, handler: Optional[Callable[[str], None]]) -> Callable:
    """Return a zero-argument callable that fires *handler* with *action*."""
    return lambda: (handler(action) if handler else print(action))


def _small_column(buttons: list) -> QWidget:
    """Stack a list of small buttons into a vertical column widget."""
    col = QWidget()
    vbox = QVBoxLayout()
    vbox.setSpacing(SIZE.STACK_SPACING)
    vbox.setContentsMargins(*MARGINS.NONE)
    for b in buttons:
        vbox.addWidget(b, alignment=Qt.AlignLeft)
    vbox.addStretch()
    col.setLayout(vbox)
    return col
