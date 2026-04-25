"""
Ribbon Panel Widget Component.

Provides a labelled container for a single ribbon panel's tool content.
Tool overflow is driven externally by the tab-level layout via
``constrain_width()`` / ``unconstrain()``.
"""
from typing import Optional, List

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QToolButton, QSizePolicy,
)
from PySide6.QtCore import Qt, QPoint, QTimer, QSize
from PySide6.QtGui import QResizeEvent

from controls.ribbon.ribbon_constants import Styles, MARGINS, COLORS, SIZE

__all__ = ["RibbonPanelFrame"]


class _ToolOverflowPopup(QFrame):
    """Popup displaying overflow tools from a ribbon panel."""

    def __init__(
        self,
        tools: List[QWidget],
        panel: "RibbonPanelFrame",
        dark: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("RibbonToolOverflow")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._tools = tools
        self._panel = panel

        bg = COLORS.BACKGROUND_DARK if dark else COLORS.BACKGROUND_LIGHT
        self.setStyleSheet(
            f"QFrame#RibbonToolOverflow {{ background: {bg}; "
            f"border: 1px solid {COLORS.MENU_BORDER}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(SIZE.TOOL_SPACING)
        for tool in tools:
            tool.setParent(self)
            tool.show()
            layout.addWidget(tool, alignment=Qt.AlignmentFlag.AlignTop)

    def closeEvent(self, event) -> None:  # noqa: N802
        for tool in self._tools:
            tool.setParent(self._panel._content)
            tool.hide()
        self._panel._active_popup = None
        super().closeEvent(event)
        QTimer.singleShot(0, self._panel._restore_tools)


class RibbonPanelFrame(QFrame):
    """
    A panel container for the ribbon interface.

    Displays a set of tools with a title label at the bottom.
    Overflow is driven externally: the parent tab content calls
    ``constrain_width(w)`` to squeeze the panel and ``unconstrain()``
    to restore full size.  The panel never reflows on its own resize.

    Args:
        title: Panel title displayed at the bottom.
        content_widget: Widget containing the panel's tools.
        grid_class: Optional CSS class for grid layout (kept for compatibility).
        parent: Optional parent widget.
        dark: Whether to use dark-mode styling.
    """

    _CHEVRON_WIDTH = 16

    def __init__(
        self,
        title: str,
        content_widget: QWidget,
        grid_class: Optional[str] = None,
        parent: Optional[QWidget] = None,
        dark: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("RibbonPanel")
        self.setFrameShape(QFrame.NoFrame)
        self.setProperty("dark", dark)
        self._content = content_widget
        self._dark = dark
        self._hidden_tools: List[QWidget] = []
        self._tool_items: Optional[List[QWidget]] = None
        self._active_popup: Optional[_ToolOverflowPopup] = None
        self._constrained = False

        # Fixed size policy — the tab-level layout must not compress us.
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        layout = QVBoxLayout()
        layout.setContentsMargins(*MARGINS.SMALL)
        layout.setSpacing(0)

        # Content row: tools + overflow chevron
        content_row = QWidget()
        row_layout = QHBoxLayout(content_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addWidget(content_widget)

        self._chevron = QToolButton()
        self._chevron.setText("\u25b8")  # ▸
        self._chevron.setFixedWidth(self._CHEVRON_WIDTH)
        self._chevron.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._chevron.setStyleSheet(
            f"QToolButton {{ border: none; font-size: 10px; "
            f"color: {COLORS.TAB_TEXT_INACTIVE_DARK}; }}"
            f"QToolButton:hover {{ color: {COLORS.TAB_TEXT_ACTIVE}; "
            f"background: {COLORS.TAB_HOVER_DARK}; }}"
        )
        self._chevron.clicked.connect(self._show_overflow_popup)
        self._chevron.hide()
        row_layout.addWidget(self._chevron, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addWidget(content_row, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)

        title_label = QLabel(title)
        title_label.setFixedHeight(14)
        title_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        title_label.setProperty("ribbonPanelTitle", True)
        title_label.setProperty("dark", dark)
        title_label.setStyleSheet(Styles.panel_title(dark))
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Size hints
    # ------------------------------------------------------------------

    def _ensure_tools(self) -> List[QWidget]:
        if self._tool_items is not None:
            return self._tool_items
        cl = self._content.layout()
        self._tool_items = []
        if cl:
            for i in range(cl.count()):
                w = cl.itemAt(i).widget()
                if w:
                    self._tool_items.append(w)
        return self._tool_items

    def natural_width(self) -> int:
        """Full width with all tools visible (no chevron)."""
        tools = self._ensure_tools()
        if not tools:
            return super().sizeHint().width()
        content_layout = self._content.layout()
        spacing = content_layout.spacing() if content_layout else 0
        cm = content_layout.contentsMargins() if content_layout else None
        content_lr = (cm.left() + cm.right()) if cm else 0
        pm = self.layout().contentsMargins() if self.layout() else None
        panel_lr = (pm.left() + pm.right()) if pm else 4
        total = content_lr + panel_lr
        for i, tool in enumerate(tools):
            hint = tool.sizeHint()
            w = hint.width() if hint.isValid() else 40
            if i > 0:
                w += spacing
            total += w
        return total

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.natural_width(), super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        tools = self._ensure_tools()
        base = super().minimumSizeHint()
        if not tools:
            return base
        first_hint = tools[0].sizeHint()
        first_w = first_hint.width() if first_hint.isValid() else 40
        pm = self.layout().contentsMargins() if self.layout() else None
        extra = (pm.left() + pm.right()) if pm else 4
        return QSize(first_w + self._CHEVRON_WIDTH + extra, base.height())

    # ------------------------------------------------------------------
    # External width control (called by _OverflowTabContent)
    # ------------------------------------------------------------------

    def constrain_width(self, width: int) -> None:
        """Squeeze the panel to *width* px, hiding overflowing tools."""
        if self._active_popup:
            self._active_popup.close()
        self._constrained = True
        self.setFixedWidth(width)
        self._reflow_tools()

    def unconstrain(self) -> None:
        """Restore the panel to its full natural width, showing all tools."""
        if self._active_popup:
            self._active_popup.close()
        self._constrained = False
        nat = self.natural_width()
        self.setFixedWidth(nat)
        tools = self._ensure_tools()
        for tool in tools:
            tool.show()
        self._hidden_tools = []
        self._chevron.hide()

    # ------------------------------------------------------------------
    # Tool overflow (only runs when constrained)
    # ------------------------------------------------------------------

    def _reflow_tools(self) -> None:
        tools = self._ensure_tools()
        if not tools or self.width() <= 0:
            return

        content_layout = self._content.layout()
        spacing = content_layout.spacing() if content_layout else 0
        cm = content_layout.contentsMargins() if content_layout else None
        content_lr = (cm.left() + cm.right()) if cm else 0
        pm = self.layout().contentsMargins() if self.layout() else None
        panel_lr = (pm.left() + pm.right()) if pm else 0

        available = self.width() - panel_lr - content_lr

        # Check if all tools fit at natural width (no chevron needed)
        total_natural = 0
        for i, tool in enumerate(tools):
            hint = tool.sizeHint()
            w = hint.width() if hint.isValid() else 40
            if w <= 0:
                w = tool.width()
            if i > 0:
                w += spacing
            total_natural += w

        if total_natural <= available:
            for tool in tools:
                tool.show()
            self._hidden_tools = []
            self._chevron.hide()
            return

        # Need overflow — reserve chevron space
        available -= self._CHEVRON_WIDTH
        used = 0
        hidden: List[QWidget] = []
        for i, tool in enumerate(tools):
            hint = tool.sizeHint()
            w = hint.width() if hint.isValid() else 40
            if w <= 0:
                w = tool.width()
            if i > 0 and not hidden:
                w += spacing
            if not hidden and (used + w) <= available:
                tool.show()
                used += w
            else:
                tool.hide()
                hidden.append(tool)

        self._hidden_tools = hidden
        if hidden:
            self._chevron.show()
        else:
            self._chevron.hide()

    def _show_overflow_popup(self) -> None:
        if not self._hidden_tools:
            return
        if self._active_popup:
            self._active_popup.close()

        popup = _ToolOverflowPopup(
            list(self._hidden_tools), self, self._dark, self.window()
        )
        popup.adjustSize()

        pos = self._chevron.mapToGlobal(QPoint(0, self._chevron.height()))
        screen = self.screen()
        if screen:
            sr = screen.availableGeometry()
            if pos.x() + popup.width() > sr.right():
                pos.setX(sr.right() - popup.width())
            if pos.y() + popup.height() > sr.bottom():
                pos = self._chevron.mapToGlobal(QPoint(0, -popup.height()))
        popup.move(pos)
        popup.show()
        self._active_popup = popup

    def _restore_tools(self) -> None:
        content_layout = self._content.layout()
        if not content_layout or self._tool_items is None:
            return
        while content_layout.count() > 0:
            content_layout.takeAt(0)
        for tool in self._tool_items:
            content_layout.addWidget(tool, alignment=Qt.AlignmentFlag.AlignTop)
        if self._constrained:
            self._reflow_tools()
        else:
            self.unconstrain()
