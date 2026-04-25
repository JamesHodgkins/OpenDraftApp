"""Painting helpers used by CADCanvas.

This module keeps rendering-specific code separate from event/input orchestration
in app.canvas, making it easier to reason about and test each concern.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF

from app.editor.draftmate import AlignmentLine, DraftmateResult
from app.editor.osnap_engine import SnapResult, SnapType
from app.entities import Vec2
from app.entities.base import GripPoint


def build_entity_base_pen(
    entity,
    document,
    *,
    resolve_color: Callable[[str], QColor],
    line_style_to_qt: Callable[[str], Qt.PenStyle],
) -> QPen:
    """Resolve the effective base pen for an entity.

    Layer defaults are applied first, then entity-level overrides.
    """
    layer = document.get_layer(entity.layer) if document is not None else None
    if layer is not None:
        color = resolve_color(layer.color)
        thickness = layer.thickness
        style = line_style_to_qt(layer.line_style)
    else:
        color = QColor(220, 220, 220)
        thickness = 1.0
        style = Qt.PenStyle.SolidLine

    ew = getattr(entity, "line_weight", None)
    if ew is not None:
        thickness = ew
    ec = getattr(entity, "color", None)
    if ec is not None:
        color = resolve_color(ec)
    es = getattr(entity, "line_style", None)
    if es is not None:
        style = line_style_to_qt(es)

    pen = QPen(color, thickness)
    pen.setStyle(style)
    return pen


def build_overlay_pen(base_pen: QPen, *, is_selected: bool, is_hovered: bool) -> Optional[QPen]:
    """Return hover/selection overlay pen, or None when no overlay is needed."""
    if not (is_selected or is_hovered):
        return None

    if is_hovered and is_selected:
        overlay_color = QColor(80, 180, 255, 90)
    elif is_hovered:
        overlay_color = QColor(255, 200, 0, 90)
    else:
        overlay_color = QColor(0, 150, 255, 90)

    overlay_thickness = max(base_pen.widthF() + 4.0, 6.0)
    overlay_pen = QPen(overlay_color, overlay_thickness)
    overlay_pen.setStyle(base_pen.style())
    return overlay_pen


def draw_hover_overlay(
    painter: QPainter,
    *,
    document,
    hover_id: str,
    selected_ids: set[str],
    draw_entity: Callable[[QPainter, object], None],
    line_style_to_qt: Callable[[str], Qt.PenStyle],
) -> None:
    """Draw a single hover overlay for the hovered entity id."""
    entity = document.get_entity(hover_id)
    if entity is None:
        return

    layer = document.get_layer(entity.layer)
    if layer is not None and not layer.visible:
        return

    if layer is not None:
        thickness = layer.thickness
        style = line_style_to_qt(layer.line_style)
    else:
        thickness = 1.0
        style = Qt.PenStyle.SolidLine

    ew = getattr(entity, "line_weight", None)
    if ew is not None:
        thickness = ew
    es = getattr(entity, "line_style", None)
    if es is not None:
        style = line_style_to_qt(es)

    is_selected = entity.id in selected_ids
    overlay_color = QColor(80, 180, 255, 90) if is_selected else QColor(255, 200, 0, 90)

    overlay_thickness = max(thickness + 4.0, 6.0)
    overlay_pen = QPen(overlay_color, overlay_thickness)
    overlay_pen.setStyle(style)
    painter.setPen(overlay_pen)
    draw_entity(painter, entity)


def draw_snap_marker(
    painter: QPainter,
    *,
    world_to_screen: Callable[[QPointF], QPointF],
    snap: SnapResult,
) -> None:
    """Draw OSNAP marker in screen coordinates."""
    sp = world_to_screen(QPointF(snap.point.x, snap.point.y))
    sx, sy = sp.x(), sp.y()
    size = 6

    orange = QColor(0xF9, 0x73, 0x16)

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(orange, 2)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    snap_type = snap.snap_type

    if snap_type == SnapType.ENDPOINT:
        painter.drawRect(int(sx - size), int(sy - size), size * 2, size * 2)
    elif snap_type == SnapType.MIDPOINT:
        triangle = QPolygonF(
            [
                QPointF(sx, sy - size),
                QPointF(sx - size, sy + size),
                QPointF(sx + size, sy + size),
            ]
        )
        painter.drawPolygon(triangle)
    elif snap_type == SnapType.CENTER:
        painter.drawEllipse(QPointF(sx, sy), size, size)
    elif snap_type == SnapType.QUADRANT:
        diamond = QPolygonF(
            [
                QPointF(sx, sy - size),
                QPointF(sx + size, sy),
                QPointF(sx, sy + size),
                QPointF(sx - size, sy),
            ]
        )
        painter.drawPolygon(diamond)
    elif snap_type == SnapType.INTERSECTION:
        painter.drawLine(QPointF(sx - size, sy - size), QPointF(sx + size, sy + size))
        painter.drawLine(QPointF(sx + size, sy - size), QPointF(sx - size, sy + size))
    elif snap_type == SnapType.PERPENDICULAR:
        painter.drawLine(QPointF(sx, sy + size), QPointF(sx + size, sy + size))
        painter.drawLine(QPointF(sx + size, sy + size), QPointF(sx + size, sy))
        painter.drawLine(QPointF(sx, sy - size), QPointF(sx - size, sy - size))
        painter.drawLine(QPointF(sx - size, sy - size), QPointF(sx - size, sy))
    elif snap_type == SnapType.NEAREST:
        painter.drawLine(QPointF(sx - size, sy - size), QPointF(sx + size, sy + size))
        painter.drawLine(QPointF(sx + size, sy - size), QPointF(sx - size, sy + size))
        painter.drawLine(QPointF(sx - size, sy - size), QPointF(sx + size, sy - size))
        painter.drawLine(QPointF(sx - size, sy + size), QPointF(sx + size, sy + size))

    painter.restore()


def draw_draftmate(
    painter: QPainter,
    *,
    world_to_screen: Callable[[QPointF], QPointF],
    result: DraftmateResult,
) -> None:
    """Draw tracked points, alignment guides, and snapped-point indicator."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)

    green = QColor(0x22, 0xC5, 0x5E)

    cross_half = 6
    pen_cross = QPen(green, 1.5)
    pen_cross.setCosmetic(True)
    painter.setPen(pen_cross)
    painter.setBrush(Qt.NoBrush)

    for tracked in result.tracked_points:
        sp = world_to_screen(QPointF(tracked.point.x, tracked.point.y))
        sx, sy = sp.x(), sp.y()
        painter.drawLine(QPointF(sx - cross_half, sy), QPointF(sx + cross_half, sy))
        painter.drawLine(QPointF(sx, sy - cross_half), QPointF(sx, sy + cross_half))

    pen_guide = QPen(green, 1)
    pen_guide.setStyle(Qt.DashLine)
    pen_guide.setCosmetic(True)
    painter.setPen(pen_guide)

    for line in result.alignment_lines:
        _draw_infinite_line(painter, line, world_to_screen)

    if result.snapped_point is not None:
        sp = world_to_screen(QPointF(result.snapped_point.x, result.snapped_point.y))
        painter.setPen(QPen(green, 1.5))
        painter.setBrush(QBrush(green))
        painter.drawEllipse(sp, 3.0, 3.0)

    painter.restore()


def _draw_infinite_line(
    painter: QPainter,
    line: AlignmentLine,
    world_to_screen: Callable[[QPointF], QPointF],
) -> None:
    """Draw an effectively infinite alignment line across the viewport."""
    t_value = 1e7
    p1w = QPointF(
        line.origin.x - t_value * line.direction.x,
        line.origin.y - t_value * line.direction.y,
    )
    p2w = QPointF(
        line.origin.x + t_value * line.direction.x,
        line.origin.y + t_value * line.direction.y,
    )
    p1s = world_to_screen(p1w)
    p2s = world_to_screen(p2w)
    painter.drawLine(p1s, p2s)


def draw_grips(
    painter: QPainter,
    *,
    document,
    selected_ids: set[str],
    world_to_screen: Callable[[QPointF], QPointF],
    grip_half_size: int,
    hot_grip: Optional[GripPoint],
    active_grip: Optional[GripPoint],
    active_entity_snapshot,
) -> None:
    """Draw CAD grip squares for selected entities."""
    size = grip_half_size

    cold_fill = QColor(0, 100, 255)
    cold_border = QColor(0, 60, 180)
    hot_fill = QColor(255, 40, 40)
    hot_border = QColor(180, 0, 0)

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, False)

    for entity in (document or []):
        if entity.id not in selected_ids:
            continue

        draw_entity = entity
        if (
            active_grip is not None
            and active_entity_snapshot is not None
            and entity.id == active_grip.entity_id
        ):
            draw_entity = active_entity_snapshot

        for grip in draw_entity.grip_points():
            sp = world_to_screen(QPointF(grip.position.x, grip.position.y))
            sx, sy = sp.x(), sp.y()

            is_hot = (
                hot_grip is not None
                and hot_grip.entity_id == grip.entity_id
                and hot_grip.index == grip.index
            )
            is_active = (
                active_grip is not None
                and active_grip.entity_id == grip.entity_id
                and active_grip.index == grip.index
            )

            if is_hot or is_active:
                painter.setPen(QPen(hot_border, 1))
                painter.setBrush(QBrush(hot_fill))
            else:
                painter.setPen(QPen(cold_border, 1))
                painter.setBrush(QBrush(cold_fill))

            painter.drawRect(int(sx - size), int(sy - size), size * 2, size * 2)

    painter.restore()


def draw_selection_rect(
    painter: QPainter,
    *,
    origin_screen: QPointF,
    current_screen: QPointF,
) -> None:
    """Draw AutoCAD-style window/crossing selection rectangle."""
    ox, oy = origin_screen.x(), origin_screen.y()
    cx, cy = current_screen.x(), current_screen.y()

    is_window = cx >= ox

    left = min(ox, cx)
    top = min(oy, cy)
    width = abs(cx - ox)
    height = abs(cy - oy)

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, False)

    if is_window:
        border_color = QColor(0, 120, 215)
        fill_color = QColor(0, 120, 215, 40)
        pen = QPen(border_color, 1, Qt.SolidLine)
    else:
        border_color = QColor(0, 200, 80)
        fill_color = QColor(0, 200, 80, 40)
        pen = QPen(border_color, 1, Qt.DashLine)

    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(QBrush(fill_color))
    painter.drawRect(QRectF(left, top, width, height))
    painter.restore()


def draw_vector_rubberband(
    painter: QPainter,
    *,
    world_to_screen: Callable[[QPointF], QPointF],
    base: Vec2,
    tip: Vec2,
) -> None:
    """Draw a dashed guide line from base point to current tip."""
    p1 = world_to_screen(QPointF(base.x, base.y))
    p2 = world_to_screen(QPointF(tip.x, tip.y))

    painter.save()
    pen = QPen(QColor(255, 200, 0, 190), 1)
    pen.setStyle(Qt.DashLine)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawLine(p1, p2)
    painter.restore()
