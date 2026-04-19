"""
Constants and configuration for the Ribbon UI.

This module centralises all magic numbers, sizes, colours, and styling
constants used throughout the ribbon components for easy maintenance.
"""
from enum import Enum
from typing import NamedTuple

__all__ = ["ButtonType", "SIZE", "COLORS", "Styles", "MARGINS"]

__all__ = ["ButtonType", "SIZE", "COLORS", "Styles", "MARGINS"]


# ===== ENUMS =====

class ButtonType(Enum):
    """Enum representing different types of ribbon buttons."""
    LARGE = "large"
    SMALL = "small"
    SPLIT = "split"
    SPLIT_SMALL = "split-small"
    STACK = "stack"
    SELECT = "select"
    COLOR_PICKER = "color-picker"
    LAYER_SELECT = "layer-select"
    PROP_STACK = "prop-stack"


# ===== SIZE CONSTANTS =====

class Sizing(NamedTuple):
    """Container for all sizing constants.

    All fields are required — no defaults — so that a typo in the ``SIZE``
    instantiation is caught immediately rather than silently falling back
    to a stale value.
    """
    # Ribbon dimensions
    RIBBON_HEIGHT: int

    # Large button
    LARGE_BUTTON_WIDTH: int
    LARGE_BUTTON_HEIGHT: int
    LARGE_ICON_SIZE: int

    # Small / icon-label button
    SMALL_BUTTON_WIDTH: int
    SMALL_BUTTON_HEIGHT: int
    SMALL_ICON_SIZE: int

    # Split-button sub-parts
    ICON_LARGE_WIDTH: int     # was ButtonSize.ICON_LARGE (w)
    ICON_LARGE_HEIGHT: int    # was ButtonSize.ICON_LARGE (h)
    DROPDOWN_ARROW_WIDTH: int # was ButtonSize.DROPDOWN_ARROW (w)
    ICON_LABEL_WIDTH: int     # was ButtonSize.ICON_LABEL (w)

    # Dropdown dimensions
    DROPDOWN_TEXT_HEIGHT: int

    # Menu icon size
    MENU_ICON_SIZE: int

    # Spacing
    PANEL_SPACING: int
    TOOL_SPACING: int
    STACK_SPACING: int
    SPLIT_BUTTON_SPACING: int


SIZE = Sizing(
    RIBBON_HEIGHT=126,
    LARGE_BUTTON_WIDTH=60,
    LARGE_BUTTON_HEIGHT=72,
    LARGE_ICON_SIZE=45,
    SMALL_BUTTON_WIDTH=72,
    SMALL_BUTTON_HEIGHT=22,
    SMALL_ICON_SIZE=20,
    ICON_LARGE_WIDTH=60,
    ICON_LARGE_HEIGHT=52,
    DROPDOWN_ARROW_WIDTH=20,
    ICON_LABEL_WIDTH=84,
    DROPDOWN_TEXT_HEIGHT=20,
    MENU_ICON_SIZE=28,
    PANEL_SPACING=1,
    TOOL_SPACING=1,
    STACK_SPACING=3,
    SPLIT_BUTTON_SPACING=2,
)


# ===== COLOR CONSTANTS =====

class Colors(NamedTuple):
    """Container for all colour constants.

    Naming convention:
    * ``_DARK`` / ``_LIGHT`` suffixes indicate the **theme** variant.
    * Semantic names (e.g. ``CONTROL_BG``) describe role, not brightness.
    """
    # Panel / tab backgrounds
    BACKGROUND_DARK: str
    BACKGROUND_LIGHT: str

    # Hover / pressed overlays
    HOVER_DARK: str
    HOVER_LIGHT: str
    PRESSED_DARK: str
    PRESSED_LIGHT: str

    # Text
    TEXT_PRIMARY_DARK: str
    TEXT_PRIMARY_LIGHT: str
    TEXT_SECONDARY_DARK: str
    TEXT_SECONDARY_LIGHT: str

    # Inline controls (combos, swatch button, menus)
    CONTROL_BG: str          # input field / swatch background
    CONTROL_TEXT: str         # input field text
    CONTROL_BORDER: str      # input field border
    CONTROL_SELECTION_BG: str  # combo dropdown selected-item highlight

    # Miscellaneous UI
    MUTED_TEXT: str           # placeholder / secondary labels (#999)
    SWATCH_OUTLINE: str      # colour-circle pen (#888888)
    SEPARATOR: str           # panel separator rule
    MENU_BORDER: str         # popup menu border
    TAB_HOVER_DARK: str      # tab hover overlay (dark) — rgba string
    TAB_HOVER_LIGHT: str     # tab hover overlay (light) — rgba string
    TAB_TEXT_ACTIVE: str     # active tab text
    TAB_TEXT_INACTIVE_DARK: str
    TAB_TEXT_INACTIVE_LIGHT: str


COLORS = Colors(
    BACKGROUND_DARK="#2D2D2D",
    BACKGROUND_LIGHT="#2D2D2D",
    HOVER_DARK="#4A4A4A",
    HOVER_LIGHT="#4A4A4A",
    PRESSED_DARK="rgba(255, 255, 255, 0.12)",
    PRESSED_LIGHT="rgba(0, 0, 0, 0.12)",
    TEXT_PRIMARY_DARK="#eeeeee",
    TEXT_PRIMARY_LIGHT="#000000",
    TEXT_SECONDARY_DARK="#aaaaaa",
    TEXT_SECONDARY_LIGHT="#666666",
    CONTROL_BG="#3a3a3a",
    CONTROL_TEXT="#e0e0e0",
    CONTROL_BORDER="#555555",
    CONTROL_SELECTION_BG="#3a6ea5",
    MUTED_TEXT="#999999",
    SWATCH_OUTLINE="#888888",
    SEPARATOR="#464646",
    MENU_BORDER="#3f3f3f",
    TAB_HOVER_DARK="rgba(255, 255, 255, 0.07)",
    TAB_HOVER_LIGHT="rgba(17, 24, 39, 0.05)",
    TAB_TEXT_ACTIVE="#f3f4f6",
    TAB_TEXT_INACTIVE_DARK="#9ca3af",
    TAB_TEXT_INACTIVE_LIGHT="#6b7280",
)


# ===== STYLE CONSTANTS =====

class Styles:
    """Style templates for ribbon components."""

    FONT_SIZE_LARGE: int = 8
    FONT_SIZE_SMALL: int = 8
    BORDER_RADIUS_SMALL: int = 3
    BORDER_RADIUS_LARGE: int = 4
    PADDING_SMALL: int = 2
    ARROW_DOWN: str = "\u25BC"

    @staticmethod
    def button_base(dark: bool = False) -> str:
        return "border: none; background: transparent;"

    @staticmethod
    def button_hover(dark: bool = False) -> str:
        color = COLORS.HOVER_DARK if dark else COLORS.HOVER_LIGHT
        return f"background: {color};"

    @staticmethod
    def button_pressed(dark: bool = False) -> str:
        color = COLORS.PRESSED_DARK if dark else COLORS.PRESSED_LIGHT
        return f"background: {color};"

    @staticmethod
    def large_button(dark: bool = False) -> str:
        """Full large ribbon button: icon stacked above label."""
        text_color = COLORS.TEXT_PRIMARY_DARK  # ribbon content area is always dark
        return f"""
            QToolButton {{
                {Styles.button_base(dark)}
                font-size: {Styles.FONT_SIZE_SMALL}pt;
                color: {text_color};
                padding: {Styles.PADDING_SMALL}px;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
                border-radius: {Styles.BORDER_RADIUS_LARGE}px;
            }}
            QToolButton:pressed {{
                {Styles.button_pressed(dark)}
                border-radius: {Styles.BORDER_RADIUS_LARGE}px;
            }}
        """

    @staticmethod
    def large_icon_button(dark: bool = False) -> str:
        return f"""
            QToolButton {{
                {Styles.button_base(dark)}
                padding: {Styles.PADDING_SMALL}px;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
                border-radius: {Styles.BORDER_RADIUS_LARGE}px;
            }}
            QToolButton:pressed {{
                {Styles.button_pressed(dark)}
                border-radius: {Styles.BORDER_RADIUS_LARGE}px;
            }}
        """

    @staticmethod
    def dropdown_text_button(dark: bool = False) -> str:
        return f"""
            QToolButton {{
                font-size: {Styles.FONT_SIZE_SMALL}pt;
                font-weight: 500;
                color: {COLORS.TEXT_PRIMARY_DARK};
                {Styles.button_base(dark)}
                padding: 0 {Styles.PADDING_SMALL}px;
                text-align: center;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
                color: {COLORS.TEXT_PRIMARY_DARK};
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QToolButton:pressed {{
                {Styles.button_pressed(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QToolButton::menu-indicator {{
                image: url(none);
                width: 0;
                height: 0;
            }}
        """

    @staticmethod
    def small_icon_label_button(dark: bool = False) -> str:
        return f"""
            QToolButton, QPushButton {{
                font-size: {Styles.FONT_SIZE_SMALL}pt;
                font-weight: 500;
                {Styles.button_base(dark)}
                padding: 0px;
                padding-left: 0px;
                text-align: left;
            }}
            QToolButton:hover, QPushButton:hover {{
                {Styles.button_hover(dark)}
            }}
            QToolButton:pressed, QPushButton:pressed {{
                {Styles.button_pressed(dark)}
            }}
        """

    @staticmethod
    def dropdown_arrow_button(dark: bool = False) -> str:
        return f"""
            QToolButton {{
                {Styles.button_base(dark)}
                padding: 0;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QToolButton:pressed {{
                {Styles.button_pressed(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QToolButton::menu-indicator {{
                image: url(none);
                width: 0;
                height: 0;
            }}
        """

    @staticmethod
    def small_button(dark: bool = False) -> str:
        # small text buttons previously had left padding; remove it to pack
        # buttons edge‑to‑edge.  width is already fixed by the SIZE constants.
        return f"""
            QPushButton {{
                {Styles.button_base(dark)}
                font-size: {Styles.FONT_SIZE_SMALL}pt;
                white-space: nowrap;
                text-align: left;
                padding: 0px;
                min-width: {SIZE.SMALL_BUTTON_WIDTH}px;
                max-width: {SIZE.SMALL_BUTTON_WIDTH}px;
                min-height: {SIZE.SMALL_BUTTON_HEIGHT}px;
                max-height: {SIZE.SMALL_BUTTON_HEIGHT}px;
            }}
            QPushButton:hover {{
                {Styles.button_hover(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QPushButton:pressed {{
                {Styles.button_pressed(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
        """

    @staticmethod
    def panel_title(dark: bool = False) -> str:
        color = COLORS.TEXT_SECONDARY_DARK if dark else COLORS.TEXT_SECONDARY_LIGHT
        return f"""
            font-size: {Styles.FONT_SIZE_LARGE}pt;
            color: {color};
            font-weight: normal;
            margin-top: 0px;
            margin-bottom: 0px;
            padding: 0px;
        """

    @staticmethod
    def combo_style(dark: bool = True) -> str:
        """QSS for QComboBox widgets used across ribbon panels."""
        return f"""
            QComboBox {{
                background: {COLORS.CONTROL_BG};
                color: {COLORS.CONTROL_TEXT};
                border: 1px solid {COLORS.CONTROL_BORDER};
                border-radius: 3px;
                padding: 0px 4px;
                font-size: 9pt;
            }}
            QComboBox:hover {{ background: {COLORS.HOVER_DARK}; }}
            QComboBox::drop-down {{ width: 14px; border: none; }}
            QComboBox QAbstractItemView {{
                background: {COLORS.BACKGROUND_DARK};
                color: {COLORS.CONTROL_TEXT};
                selection-background-color: {COLORS.CONTROL_SELECTION_BG};
                border: 1px solid {COLORS.CONTROL_BORDER};
            }}
        """


# ===== MARGIN CONSTANTS =====

class Margins(NamedTuple):
    """Standard margin values."""
    NONE: tuple = (0, 0, 0, 0)
    SMALL: tuple = (1, 1, 1, 1)  # reduced padding around panels


MARGINS = Margins(
    NONE=(0, 0, 0, 0),
    SMALL=(1, 1, 1, 1),
)
