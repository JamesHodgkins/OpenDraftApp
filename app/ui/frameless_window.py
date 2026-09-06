"""Frameless-window support: keeps native resize/drag/Aero-Snap behaviour
while we draw our own title bar instead of the OS one.

Qt's ``Qt.FramelessWindowHint`` alone drops the title bar *and* all of the
OS-provided resize borders / Aero Snap / shake-to-minimize handling. Rather
than hand-roll ``WM_NCHITTEST`` interception (fragile across DPI scales and
input-injection paths), we use Qt's own ``QWindow.startSystemMove()`` /
``startSystemResize()`` — introduced for exactly this frameless-custom-chrome
case — from real mouse-press events on the title bar and window edges. Qt
forwards these straight into the OS's native move/resize loop, so edge
previews and DPI handling keep working for free.

Snap-to-maximize does not: dragging a frameless window's caption to the top
of the screen is a Windows *non-client-area* affordance, and our title bar
is client-area content as far as the OS drag loop is concerned, so it never
fires. We approximate it ourselves - flag a title-bar-initiated move, and on
mouse release check whether the cursor ended up at the screen's top edge.
"""
from PySide6.QtCore import QEvent, Qt, QPoint, QObject
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

__all__ = ["FramelessWindowMixin", "RESIZE_BORDER"]

RESIZE_BORDER = 8  # px hit-test margin (logical px) for resize handles
SNAP_MAXIMIZE_MARGIN = 4  # px from the screen top (logical px) that triggers snap-to-maximize
DRAG_START_THRESHOLD = 4  # px of cursor movement before a maximized-titlebar press counts as a drag

_CURSOR_FOR_EDGES = {
    Qt.Edges(): Qt.ArrowCursor,
    Qt.Edge.LeftEdge: Qt.SizeHorCursor,
    Qt.Edge.RightEdge: Qt.SizeHorCursor,
    Qt.Edge.TopEdge: Qt.SizeVerCursor,
    Qt.Edge.BottomEdge: Qt.SizeVerCursor,
    Qt.Edge.LeftEdge | Qt.Edge.TopEdge: Qt.SizeFDiagCursor,
    Qt.Edge.RightEdge | Qt.Edge.BottomEdge: Qt.SizeFDiagCursor,
    Qt.Edge.RightEdge | Qt.Edge.TopEdge: Qt.SizeBDiagCursor,
    Qt.Edge.LeftEdge | Qt.Edge.BottomEdge: Qt.SizeBDiagCursor,
}


class FramelessWindowMixin:
    """Mix into a QMainWindow/QWidget top-level to get a frameless-but-native window.

    The host widget must expose a ``title_bar`` attribute (a QWidget); it is
    looked up lazily on each event, so it may be set any time after calling
    :meth:`init_frameless`. A press inside the title bar starts a native
    window move, except on an actual ``QAbstractButton`` (min/max/close),
    which behaves as a normal clickable control. A press within
    ``RESIZE_BORDER`` px of any window edge starts a native resize.

    Child widgets (the title bar, the ribbon, ...) swallow mouse events
    before they'd ever reach the window's own mousePressEvent, and Qt event
    filters installed on a parent do *not* see events delivered to its
    children (unlike Win32 message hooks) — only a filter installed on
    ``QApplication`` itself observes every widget's events. Hence this
    installs one application-wide filter scoped to just this window (and
    its descendants) via an identity check.
    """

    _dragging_title_bar = False
    _pending_restore_drag_origin: QPoint | None = None

    def init_frameless(self) -> None:
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMouseTracking(True)
        self._frameless_filter = _FramelessEventFilter(self)
        QApplication.instance().installEventFilter(self._frameless_filter)

    def _frameless_edge_at(self, pos: QPoint) -> Qt.Edges:
        w, h = self.width(), self.height()
        b = RESIZE_BORDER
        edges = Qt.Edges()
        if pos.x() < b:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= w - b:
            edges |= Qt.Edge.RightEdge
        if pos.y() < b:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= h - b:
            edges |= Qt.Edge.BottomEdge
        return edges


def _restore_and_start_move(window, global_pos: QPoint) -> None:
    """Restore a maximized *window* and immediately hand off to a native
    move, re-centering the restored title bar under the cursor so the drag
    picks up right where the maximized one left off.

    ``normalGeometry()`` is read *before* ``showNormal()`` because Qt/the OS
    applies the un-maximize asynchronously - by the time ``showNormal()``
    returns, ``geometry()`` can still report the (stale) maximized size, so
    centering off a post-restore read is unreliable.
    """
    normal_size = window.normalGeometry().size()

    new_x = round(global_pos.x() - normal_size.width() / 2)
    new_y = global_pos.y() - RESIZE_BORDER

    window.showNormal()
    window.move(new_x, new_y)

    handle = window.windowHandle()
    if handle is not None:
        handle.startSystemMove()


class _FramelessEventFilter(QObject):
    """Application-wide filter that watches mouse events for one window.

    Only a filter installed on ``QApplication`` sees events delivered to
    *any* widget (Qt filters installed on a parent do not see events meant
    for its children). This filter ignores everything outside ``window``'s
    own widget tree so it stays a no-op for the rest of the application.
    """

    def __init__(self, window):
        super().__init__(window)
        self._window = window

    def eventFilter(self, watched, event):  # noqa: N802
        window = self._window
        etype = event.type()

        if etype == QEvent.Type.MouseButtonRelease:
            window._pending_restore_drag_origin = None
            if window._dragging_title_bar:
                window._dragging_title_bar = False
                if isinstance(event, QMouseEvent) and event.button() == Qt.LeftButton:
                    if QCursor.pos().y() <= SNAP_MAXIMIZE_MARGIN:
                        window.showMaximized()
                        window.unsetCursor()

        if etype not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove):
            return False
        if not isinstance(event, QMouseEvent) or not isinstance(watched, QWidget):
            return False
        if watched is not window and not window.isAncestorOf(watched):
            return False

        pos_in_window = watched.mapTo(window, event.position().toPoint()) \
            if watched is not window else event.position().toPoint()

        if etype == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.LeftButton:
                return False

            if window.isMaximized():
                title_bar = getattr(window, "title_bar", None)
                if title_bar is not None and title_bar.geometry().contains(pos_in_window) \
                        and not isinstance(watched, QAbstractButton):
                    # Don't restore yet - a plain click (press+release with no
                    # movement) on a maximized title bar should do nothing,
                    # matching native Windows behaviour. Only remember where
                    # the press happened; the restore-and-move only fires
                    # once MouseMove reports real dragging past a threshold.
                    window._pending_restore_drag_origin = event.globalPosition().toPoint()
                    return True
                return False

            edges = window._frameless_edge_at(pos_in_window)
            if edges:
                handle = window.windowHandle()
                if handle is not None:
                    handle.startSystemResize(edges)
                    return True

            title_bar = getattr(window, "title_bar", None)
            if title_bar is not None and title_bar.geometry().contains(pos_in_window):
                if not isinstance(watched, QAbstractButton):
                    handle = window.windowHandle()
                    if handle is not None:
                        handle.startSystemMove()
                        window._dragging_title_bar = True
                        return True

        elif etype == QEvent.Type.MouseMove:
            if window._pending_restore_drag_origin is not None:
                global_pos = event.globalPosition().toPoint()
                delta = global_pos - window._pending_restore_drag_origin
                if abs(delta.x()) >= DRAG_START_THRESHOLD or abs(delta.y()) >= DRAG_START_THRESHOLD:
                    window._pending_restore_drag_origin = None
                    _restore_and_start_move(window, global_pos)
                    window._dragging_title_bar = True
                return True
            if not window.isMaximized():
                edges = window._frameless_edge_at(pos_in_window)
                window.setCursor(_CURSOR_FOR_EDGES.get(edges, Qt.ArrowCursor))

        return False
