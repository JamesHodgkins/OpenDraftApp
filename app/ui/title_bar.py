"""Custom title bar replacing the native Windows frame.

Provides a centered window title and custom minimize / maximize / close
buttons, matching the look of the dark ribbon below it. Combined with
frameless-window hit-testing in :mod:`app.ui.frameless_window`, this gives
Aero Snap, drag-to-move, and resize-border behaviour while looking fully
custom (AutoCAD / Office style).
"""
import os

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QToolButton, QSizePolicy

from controls.icon_widget import load_pixmap
from controls.ribbon.ribbon_constants import COLORS

__all__ = ["TitleBar", "AppFileButton", "TITLE_BAR_HEIGHT", "TAB_ROW_HEIGHT"]

TITLE_BAR_HEIGHT = 32
TAB_ROW_HEIGHT = 24  # matches the ribbon tab bar's min-height (see ribbon.qss)
_SYSTEM_BUTTON_WIDTH = 46
_SYSTEM_ICON_SIZE = 14
_LOGO_SIZE = 28
_LOGO_MARGIN = 8

TITLEBAR_BACKGROUND = COLORS.SURFACE_DARKEST
TITLEBAR_HOVER = COLORS.HOVER_DARK
TITLEBAR_CLOSE_HOVER = "#e81123"
TITLEBAR_TEXT = COLORS.TEXT_PRIMARY_DARK

_LOGO_CANDIDATES = ("badge_logo_dark.svg", "odx_icon.svg")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ICONS_DIR = os.path.join(_PROJECT_ROOT, "assets", "icons")
_SVG_DIR = os.path.join(_PROJECT_ROOT, "assets", "svg")


def _load_logo_pixmap(size: int) -> QPixmap | None:
    for filename in _LOGO_CANDIDATES:
        for directory in (_ICONS_DIR, _SVG_DIR):
            path = os.path.join(directory, filename)
            if os.path.exists(path):
                pixmap = QIcon(path).pixmap(QSize(size, size))
                if not pixmap.isNull():
                    return pixmap
    return None


class AppFileButton(QToolButton):
    """Square "File" button merged with the app icon.

    Floats as a full-height left-hand column in front of both the title bar
    and the ribbon's tab row — not inside either widget's own layout, since
    that's the only way one button can visually span two stacked sibling
    widgets. `MainWindow` parents this to the container that holds the
    title bar + ribbon, sizes it to a square via `set_height`
    (`TITLE_BAR_HEIGHT + TAB_ROW_HEIGHT`), and keeps it raised/positioned at
    the top-left corner. Clicking it opens the Backstage-style file menu.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("AppFileButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip("File")

        logo_pixmap = _load_logo_pixmap(_LOGO_SIZE)
        if logo_pixmap is not None:
            self.setIcon(QIcon(logo_pixmap))
            self.setIconSize(QSize(_LOGO_SIZE, _LOGO_SIZE))

        # Flat and dark to match the ribbon/title bar it sits in front of -
        # the app logo icon is the only accent here, not a colored fill
        # (previously borrowed CONTROL_SELECTION_BG, a combo-box highlight
        # blue with no relation to this button, which stood out as a stray
        # accent square instead of reading as part of the chrome).
        self.setStyleSheet(f"""
            QToolButton#AppFileButton {{
                border: none;
                background: {TITLEBAR_BACKGROUND};
            }}
            QToolButton#AppFileButton:hover {{
                background: {TITLEBAR_HOVER};
            }}
        """)
        self._suppress_next_click = False

    def suppress_next_click(self) -> None:
        """Swallow the next complete click gesture on this button."""
        self._suppress_next_click = True

    def set_height(self, height: int) -> None:
        """Size the button to a `height` x `height` square (full column height)."""
        self.setFixedSize(height, height)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # A Qt.Popup menu (the Backstage file menu) grabs the mouse and
        # closes itself on any press outside its own bounds - including
        # this very press on the button that opened it, since the popup
        # doesn't treat its anchor as "inside". That closes the menu before
        # this press even finishes, so the matching release would otherwise
        # emit a normal `clicked` and reopen it immediately, making the
        # button look like it can never close its own menu. Detect that a
        # popup was still open at the start of this press and swallow the
        # click it's about to produce, so the same click that closes the
        # menu doesn't also reopen it.
        self._suppress_next_click = self._suppress_next_click or QApplication.activePopupWidget() is not None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._suppress_next_click:
            self._suppress_next_click = False
            self.setDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _tint_pixmap(pixmap: QPixmap, color: str) -> QPixmap:
    """Return a copy of *pixmap* with all opaque pixels recolored to *color*.

    Used for the close icon's hover state: a static SVG asset has no
    ``:hover`` variant of its own, so we recolor its alpha shape in code
    instead of shipping a second white icon file.
    """
    tinted = QPixmap(pixmap.size())
    tinted.setDevicePixelRatio(pixmap.devicePixelRatio())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), color)
    painter.end()
    return tinted


class _CloseButton(QToolButton):
    """Close button whose icon turns white while the red hover background shows."""

    def __init__(self, normal_icon: QPixmap, hover_icon: QPixmap, parent: QWidget | None = None):
        super().__init__(parent)
        self._normal_icon = QIcon(normal_icon)
        self._hover_icon = QIcon(hover_icon)
        self.setIcon(self._normal_icon)

    def enterEvent(self, event) -> None:  # noqa: N802
        self.setIcon(self._hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.setIcon(self._normal_icon)
        super().leaveEvent(event)


class TitleBar(QWidget):
    """Custom title bar strip drawn above the ribbon."""

    minimizeClicked = Signal()
    maximizeClicked = Signal()
    closeClicked = Signal()

    def __init__(self, title: str, file_column_width: int = _LOGO_SIZE + _LOGO_MARGIN * 2, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#TitleBar {{ background: {TITLEBAR_BACKGROUND}; }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Reserves the horizontal column the merged file/logo button occupies,
        # but stays empty and unpainted: that button is a separate widget
        # floating in front of the title bar *and* the ribbon tab row below
        # it (see `MainWindow.file_button`), sized as a square spanning both
        # rows' combined height, so it needs a same-width gap here too. This
        # spacer just keeps the rest of the title bar's row (title label,
        # window controls) laid out as if that column were still occupied.
        self.logo_spacer = QWidget(self)
        self.logo_spacer.setFixedSize(file_column_width, TITLE_BAR_HEIGHT)
        layout.addWidget(self.logo_spacer)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("TitleBarLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(f"color: {TITLEBAR_TEXT}; font-size: 9pt;")
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.title_label, 1)

        self.minimize_button = self._make_system_button(self.minimizeClicked, icon_name="window_minimize")
        self.maximize_button = self._make_system_button(self.maximizeClicked, icon_name="window_maximize")
        self.close_button = self._make_close_button(self.closeClicked)

        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    # ------------------------------------------------------------------
    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_maximized(self, maximized: bool) -> None:
        icon_name = "window_restore" if maximized else "window_maximize"
        pix = load_pixmap(icon_name, _SYSTEM_ICON_SIZE)
        if pix is not None:
            self.maximize_button.setIcon(QIcon(pix))
        self.maximize_button.setToolTip("Restore Down" if maximized else "Maximize")

    # ------------------------------------------------------------------
    def _make_system_button(
        self,
        signal: Signal,
        icon_name: str,
        hover: str = TITLEBAR_HOVER,
        width: int = _SYSTEM_BUTTON_WIDTH,
        icon_size: int = _SYSTEM_ICON_SIZE,
    ) -> QToolButton:
        btn = QToolButton(self)
        pix = load_pixmap(icon_name, icon_size)
        if pix is not None:
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(icon_size, icon_size))
        btn.setFixedSize(width, TITLE_BAR_HEIGHT)
        btn.setCursor(Qt.ArrowCursor)
        btn.setStyleSheet(self._flat_button_style(hover=hover))
        btn.clicked.connect(signal.emit)
        return btn

    def _make_close_button(self, signal: Signal) -> QToolButton:
        pix = load_pixmap("window_close", _SYSTEM_ICON_SIZE)
        if pix is None:
            return self._make_system_button(signal, icon_name="window_close", hover=TITLEBAR_CLOSE_HOVER)

        btn = _CloseButton(pix, _tint_pixmap(pix, "#ffffff"), self)
        btn.setIconSize(QSize(_SYSTEM_ICON_SIZE, _SYSTEM_ICON_SIZE))
        btn.setFixedSize(_SYSTEM_BUTTON_WIDTH, TITLE_BAR_HEIGHT)
        btn.setCursor(Qt.ArrowCursor)
        btn.setStyleSheet(self._flat_button_style(hover=TITLEBAR_CLOSE_HOVER))
        btn.clicked.connect(signal.emit)
        return btn

    @staticmethod
    def _flat_button_style(hover: str) -> str:
        return f"""
            QToolButton {{
                border: none;
                background: transparent;
            }}
            QToolButton:hover {{ background: {hover}; }}
            QToolButton::menu-indicator {{ image: none; width: 0; }}
        """
