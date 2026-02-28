"""
Constants and configuration for the Ribbon UI.

This module centralises all magic numbers, sizes, colours, and styling
constants used throughout the ribbon components for easy maintenance.
"""
from enum import Enum
from typing import NamedTuple


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


class ButtonSize(Enum):
    """Standard button sizes used in the ribbon."""
    LARGE = (60, 64)
    SMALL = (72, 22)  # width x height
    # split-small width now matches a normal small button (total, including arrow)
    SPLIT_SMALL = (72, 22)
    ICON_LARGE = (60, 52)
    ICON_SMALL = (40, 32)
    DROPDOWN_ARROW = (20, 28)
    DROPDOWN_TEXT = (60, 20)
    ICON_LABEL = (84, 28)


class IconSize(Enum):
    """Standard icon sizes."""
    LARGE = 45  # now 45x45 px per user request
    SMALL = 20  # requested 20x20 px
    MENU = 28


# ===== SIZE CONSTANTS =====

class Sizing(NamedTuple):
    """Container for all sizing constants."""
    # Ribbon dimensions
    RIBBON_HEIGHT: int = 140

    # Button dimensions
    LARGE_BUTTON_WIDTH: int = 52
    LARGE_BUTTON_HEIGHT: int = 64
    SMALL_BUTTON_WIDTH: int = 72
    SMALL_BUTTON_HEIGHT: int = 22
    SPLIT_SMALL_WIDTH: int = 72  # same as small button; internal logic splits arrow

    # Icon dimensions
    LARGE_ICON_SIZE: int = 45
    SMALL_ICON_SIZE: int = 20
    LARGE_ICON_BUTTON_HEIGHT: int = 52
    LARGE_ICON_LABEL_SIZE: int = 56

    # Dropdown dimensions
    DROPDOWN_ARROW_WIDTH: int = 20
    DROPDOWN_TEXT_HEIGHT: int = 20

    # Spacing
    PANEL_SPACING: int = 2   # cut panel-to-panel gap down for tighter layout
    TOOL_SPACING: int = 2   # reduced horizontal/vertical space between tools
    STACK_SPACING: int = 2
    SPLIT_BUTTON_SPACING: int = 2


SIZE = Sizing(
    RIBBON_HEIGHT=140,
    LARGE_BUTTON_WIDTH=60,
    LARGE_BUTTON_HEIGHT=64,
    SMALL_BUTTON_WIDTH=72,
    SMALL_BUTTON_HEIGHT=22,
    SPLIT_SMALL_WIDTH=72,
    LARGE_ICON_SIZE=45,
    SMALL_ICON_SIZE=20,
    LARGE_ICON_BUTTON_HEIGHT=52,
    LARGE_ICON_LABEL_SIZE=56,
    DROPDOWN_ARROW_WIDTH=20,
    DROPDOWN_TEXT_HEIGHT=20,
    PANEL_SPACING=1,
    TOOL_SPACING=1,
    STACK_SPACING=1,
    SPLIT_BUTTON_SPACING=2,
)


# ===== COLOR CONSTANTS =====

class Colors(NamedTuple):
    """Container for all colour constants.

    Note
    ----
    * ``_LIGHT`` and ``_DARK`` suffixes indicate the **theme** in which the
      colour is applied, not the brightness of the colour itself.  For example,
      ``HOVER_LIGHT`` is the hover background used when the ribbon is in light
      mode; because the canvas there is white we actually pick a soft grey
      (#E5E7EB) which appears slightly darker than the base.  ``HOVER_DARK`` is
      used on dark-mode ribbons and therefore is a lighter grey that contrasts
      against the dark panel.
    """
    BACKGROUND_DARK: str = "#2D2D2D"
    BACKGROUND_LIGHT: str = "#2D2D2D"
    # hover colours are chosen to be visible against the panel they sit on
    HOVER_DARK: str = "#4A4A4A"   # used when theme is dark
    HOVER_LIGHT: str = "#4A4A4A"  # used when theme is light
    PRESSED_DARK: str = "rgba(255, 255, 255, 0.12)"
    PRESSED_LIGHT: str = "rgba(0, 0, 0, 0.12)"
    TEXT_PRIMARY_DARK: str = "#eeeeee"
    TEXT_PRIMARY_LIGHT: str = "#000000"
    TEXT_SECONDARY_DARK: str = "#aaaaaa"
    TEXT_SECONDARY_LIGHT: str = "#666666"
    TEXT_PLACEHOLDER: str = "#888888"


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
    TEXT_PLACEHOLDER="#888888",
)


# ===== STYLE CONSTANTS =====

class Styles:
    """Style templates for ribbon components."""

    FONT_SIZE_LARGE: int = 8
    FONT_SIZE_SMALL: int = 7
    BORDER_RADIUS_SMALL: int = 3
    BORDER_RADIUS_LARGE: int = 4
    PADDING_SMALL: int = 2
    PADDING_MEDIUM: int = 8
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
                font-size: {Styles.FONT_SIZE_LARGE}pt;
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
            QToolButton {{
                font-size: {Styles.FONT_SIZE_SMALL}pt;
                font-weight: 500;
                {Styles.button_base(dark)}
                /* Remove left padding so icon sits at the left edge; tighten right padding */
                padding: 0 {Styles.PADDING_SMALL}px;
                padding-left: 0px;
                text-align: left;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
            }}
            QToolButton:pressed {{
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
            margin-top: {Styles.PADDING_SMALL}px;
            margin-bottom: 1px;
        """

    @staticmethod
    def combo_style() -> str:
        """QSS for QComboBox widgets used across ribbon panels."""
        return """
            QComboBox {
                background: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 1px 4px;
                font-size: 9pt;
            }
            QComboBox:hover { background: #4a4a4a; }
            QComboBox::drop-down { width: 14px; border: none; }
            QComboBox QAbstractItemView {
                background: #2d2d2d;
                color: #e0e0e0;
                selection-background-color: #3a6ea5;
                border: 1px solid #555;
            }
        """


# ===== MARGIN CONSTANTS =====

class Margins(NamedTuple):
    """Standard margin values."""
    NONE: tuple = (0, 0, 0, 0)
    SMALL: tuple = (1, 1, 1, 1)  # reduced padding around panels
    MEDIUM: tuple = (2, 2, 2, 2)


MARGINS = Margins(
    NONE=(0, 0, 0, 0),
    SMALL=(1, 1, 1, 1),
    MEDIUM=(2, 2, 2, 2),
)


# ===== PATH CONSTANTS =====

class Paths:
    """File path constants."""
    ASSETS_DIR = "assets"
    ICONS_DIR = "assets/icons"
    STYLESHEET_FILE = "assets/themes/ribbon.qss"

    @staticmethod
    def icon_path(icon_name: str, extension: str = "png") -> str:
        """Generate icon path from icon name."""
        return f"{Paths.ICONS_DIR}/{icon_name}.{extension}"
