"""Dimension entities — linear and aligned annotations."""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, ClassVar, Dict, List, Literal, Optional

from app.entities.base import BaseEntity, BBox, Vec2, _geo_pt_seg_dist

DimType = Literal["linear", "aligned"]
MarkType = Literal["arrow", "mark", "none"]
TextPosition = Literal["above", "inline", "below"]


def _dim_geometry(
    p1: Vec2, p2: Vec2, p3: Vec2, dim_type: str
) -> tuple[Vec2, Vec2, Vec2, Vec2, float]:
    """Return (foot1, foot2, dim_dir, ext_dir, measurement) for either dim type."""
    if dim_type == "linear":
        dx, dy = p2.x - p1.x, p2.y - p1.y
        if abs(dx) >= abs(dy):
            dim_dir = Vec2(1.0, 0.0)
            ext_dir = Vec2(0.0, 1.0)
            foot1 = Vec2(p1.x, p3.y)
            foot2 = Vec2(p2.x, p3.y)
            measurement = abs(p2.x - p1.x)
        else:
            dim_dir = Vec2(0.0, 1.0)
            ext_dir = Vec2(1.0, 0.0)
            foot1 = Vec2(p3.x, p1.y)
            foot2 = Vec2(p3.x, p2.y)
            measurement = abs(p2.y - p1.y)
    else:
        seg_dx, seg_dy = p2.x - p1.x, p2.y - p1.y
        seg_len = math.hypot(seg_dx, seg_dy) or 1.0
        dim_dir = Vec2(seg_dx / seg_len, seg_dy / seg_len)
        ext_dir = Vec2(-dim_dir.y, dim_dir.x)
        t = (p3.x - p1.x) * ext_dir.x + (p3.y - p1.y) * ext_dir.y
        foot1 = Vec2(p1.x + t * ext_dir.x, p1.y + t * ext_dir.y)
        foot2 = Vec2(p2.x + t * ext_dir.x, p2.y + t * ext_dir.y)
        measurement = seg_len
    return foot1, foot2, dim_dir, ext_dir, measurement


def _dim_line_midpoint(p1: Vec2, p2: Vec2, p3: Vec2, dim_type: str) -> Vec2:
    """World-space midpoint of the dimension line (the natural p3 resting position)."""
    foot1, foot2, *_ = _dim_geometry(p1, p2, p3, dim_type)
    return Vec2((foot1.x + foot2.x) / 2, (foot1.y + foot2.y) / 2)


@dataclass
class DimensionEntity(BaseEntity):
    """A linear or aligned dimension annotation."""

    _entity_kind: ClassVar[str] = "dimension"
    type: str = field(default="dimension", init=False, repr=False)
    p1: Vec2 = field(default_factory=Vec2)
    p2: Vec2 = field(default_factory=Vec2)
    # p3 controls the offset of the dimension line from p1/p2.
    # It is always snapped back to the midpoint of the dim line after a grip move,
    # so its only meaningful component is the perpendicular offset distance.
    p3: Vec2 = field(default_factory=Vec2)
    dim_type: DimType = "linear"
    text_height: float = 2.5
    mark_type: MarkType = "arrow"
    arrow_size: float = 2.5
    text_position: TextPosition = "above"
    text_offset: float = 0.0
    # World-space gap between the measurement point and where the extension line starts
    ext_offset: float = 1.0
    # World-space overshoot of the extension line past the dimension line
    dim_offset: float = 1.0

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[BBox]:
        foot1, foot2, *_ = _dim_geometry(self.p1, self.p2, self.p3, self.dim_type)
        xs = [self.p1.x, self.p2.x, foot1.x, foot2.x]
        ys = [self.p1.y, self.p2.y, foot1.y, foot2.y]
        return BBox(min(xs), min(ys), max(xs), max(ys))

    def hit_test(self, pt: Vec2, tolerance: float) -> bool:
        for a, b in [(self.p1, self.p2), (self.p1, self.p3), (self.p2, self.p3)]:
            if _geo_pt_seg_dist(pt, a, b) <= tolerance:
                return True
        return False

    def snap_candidates(self, enabled: AbstractSet) -> List:
        from app.entities.snap_types import SnapType, SnapResult
        results = []
        if SnapType.ENDPOINT in enabled:
            for p in (self.p1, self.p2, self.p3):
                results.append(SnapResult(Vec2(p.x, p.y), SnapType.ENDPOINT, self.id))
        return results

    def nearest_snap(self, cursor: Vec2) -> Optional[object]:
        return None

    def perp_snaps(self, from_pt: Vec2) -> List:
        return []

    def draw(self, painter, world_to_screen, scale: float) -> None:
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QPolygonF, QFont, QFontMetrics, QBrush

        foot1, foot2, dim_dir, ext_dir, measurement = _dim_geometry(
            self.p1, self.p2, self.p3, self.dim_type
        )

        def ws(v: Vec2) -> QPointF:
            return world_to_screen(QPointF(v.x, v.y))

        s_p1    = ws(self.p1)
        s_p2    = ws(self.p2)
        s_foot1 = ws(foot1)
        s_foot2 = ws(foot2)

        ext_gap_px  = self.ext_offset * scale
        dim_over_px = self.dim_offset * scale
        arrow_px    = self.arrow_size * scale

        # ── extension lines ──────────────────────────────────────────────
        def ext_line(meas_s: QPointF, foot_s: QPointF) -> None:
            vx = foot_s.x() - meas_s.x()
            vy = foot_s.y() - meas_s.y()
            length = math.hypot(vx, vy) or 1.0
            ux, uy = vx / length, vy / length
            x0 = meas_s.x() + ux * ext_gap_px
            y0 = meas_s.y() + uy * ext_gap_px
            x1 = foot_s.x() + ux * dim_over_px
            y1 = foot_s.y() + uy * dim_over_px
            painter.drawLine(x0, y0, x1, y1)

        ext_line(s_p1, s_foot1)
        ext_line(s_p2, s_foot2)

        # ── dimension line ───────────────────────────────────────────────
        def dim_line_ends(fa: QPointF, fb: QPointF, inset: float):
            vx = fb.x() - fa.x()
            vy = fb.y() - fa.y()
            length = math.hypot(vx, vy) or 1.0
            ux, uy = vx / length, vy / length
            if self.mark_type == "arrow" and length > 2 * inset:
                return (fa.x() + ux * inset, fa.y() + uy * inset,
                        fb.x() - ux * inset, fb.y() - uy * inset)
            return fa.x(), fa.y(), fb.x(), fb.y()

        lx0, ly0, lx1, ly1 = dim_line_ends(s_foot1, s_foot2, arrow_px)
        painter.drawLine(lx0, ly0, lx1, ly1)

        # ── arrowheads / marks ───────────────────────────────────────────
        old_brush = painter.brush()
        old_pen   = painter.pen()
        painter.setBrush(QBrush(old_pen.color()))

        def arrow_tip(tip: QPointF, toward: QPointF) -> None:
            vx = toward.x() - tip.x()
            vy = toward.y() - tip.y()
            length = math.hypot(vx, vy) or 1.0
            ux, uy = vx / length, vy / length
            hw = arrow_px * 0.35
            bx = tip.x() + ux * arrow_px
            by = tip.y() + uy * arrow_px
            poly = QPolygonF([
                QPointF(tip.x(), tip.y()),
                QPointF(bx + uy * hw, by - ux * hw),
                QPointF(bx - uy * hw, by + ux * hw),
            ])
            painter.drawPolygon(poly)

        if self.mark_type == "arrow":
            arrow_tip(s_foot1, s_foot2)
            arrow_tip(s_foot2, s_foot1)
        elif self.mark_type == "mark":
            # Diagonal tick mark (45° slash across the foot point)
            tick_len = arrow_px * 0.7
            vx = s_foot2.x() - s_foot1.x()
            vy = s_foot2.y() - s_foot1.y()
            ln = math.hypot(vx, vy) or 1.0
            tx, ty = vy / ln * tick_len, -vx / ln * tick_len
            painter.drawLine(s_foot1.x() - tx, s_foot1.y() - ty,
                             s_foot1.x() + tx, s_foot1.y() + ty)
            painter.drawLine(s_foot2.x() - tx, s_foot2.y() - ty,
                             s_foot2.x() + tx, s_foot2.y() + ty)
        # "none" → nothing

        painter.setBrush(old_brush)

        # ── measurement text ─────────────────────────────────────────────
        label = f"{measurement:.2f}".rstrip("0").rstrip(".")

        font = QFont("Arial")
        font_px = max(1, int(self.text_height * scale))
        font.setPixelSize(font_px)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(label)
        text_h = fm.height()

        mid_x = (s_foot1.x() + s_foot2.x()) * 0.5
        mid_y = (s_foot1.y() + s_foot2.y()) * 0.5

        # Screen-space direction along the dimension line
        dlx = s_foot2.x() - s_foot1.x()
        dly = s_foot2.y() - s_foot1.y()
        dl_len = math.hypot(dlx, dly) or 1.0
        dlx, dly = dlx / dl_len, dly / dl_len

        # Screen-space extension direction (perpendicular to dim line)
        s_ext1 = ws(Vec2(self.p1.x + ext_dir.x, self.p1.y + ext_dir.y))
        s_ext0 = ws(self.p1)
        epx = s_ext1.x() - s_ext0.x()
        epy = s_ext1.y() - s_ext0.y()
        ep_len = math.hypot(epx, epy) or 1.0
        epx, epy = epx / ep_len, epy / ep_len

        TEXT_GAP = 3.0 + self.text_offset * scale
        if self.text_position == "above":
            offset_dist = text_h / 2 + TEXT_GAP
            cx = mid_x + epx * offset_dist
            cy = mid_y + epy * offset_dist
        elif self.text_position == "below":
            offset_dist = text_h / 2 + TEXT_GAP
            cx = mid_x - epx * offset_dist
            cy = mid_y - epy * offset_dist
        else:
            cx = mid_x
            cy = mid_y

        # Rotation angle of the dim line in screen space
        text_angle_deg = math.degrees(math.atan2(dly, dlx))
        # Keep text readable — flip if pointing left
        if abs(text_angle_deg) > 90:
            text_angle_deg += 180

        painter.setPen(old_pen)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(text_angle_deg)
        painter.drawText(QRectF(-text_w / 2, -text_h, text_w + 2, text_h + 2), label)
        painter.restore()

    # ------------------------------------------------------------------
    # Grip editing
    # ------------------------------------------------------------------

    def grip_points(self):
        from app.entities.base import GripPoint, GripType
        # p3 grip is always shown at the midpoint of the dimension line,
        # regardless of where p3 was stored.
        mid = _dim_line_midpoint(self.p1, self.p2, self.p3, self.dim_type)
        return [
            GripPoint(self.p1, self.id, 0, GripType.ENDPOINT),
            GripPoint(self.p2, self.id, 1, GripType.ENDPOINT),
            GripPoint(mid,     self.id, 2, GripType.MIDPOINT),
        ]

    def move_grip(self, index: int, new_pos: Vec2) -> None:
        if index == 0:
            self.p1 = new_pos
        elif index == 1:
            self.p2 = new_pos
        elif index == 2:
            # Accept the dragged position for the offset, then snap p3 back
            # to the midpoint of the resulting dim line so the grip always
            # starts from the centre on the next pick.
            self.p3 = new_pos
            mid = _dim_line_midpoint(self.p1, self.p2, self.p3, self.dim_type)
            self.p3 = mid

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = self._base_dict()
        d["p1"] = self.p1.to_dict()
        d["p2"] = self.p2.to_dict()
        d["p3"] = self.p3.to_dict()
        d["dimType"] = self.dim_type
        d["textHeight"] = self.text_height
        d["markType"] = self.mark_type
        d["arrowSize"] = self.arrow_size
        d["textPosition"] = self.text_position
        d["textOffset"] = self.text_offset
        d["extOffset"] = self.ext_offset
        d["dimOffset"] = self.dim_offset
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DimensionEntity":
        return cls(
            **cls._base_kwargs(d),
            p1=Vec2.from_dict(d["p1"]),
            p2=Vec2.from_dict(d["p2"]),
            p3=Vec2.from_dict(d["p3"]),
            dim_type=d.get("dimType", "linear"),
            text_height=float(d.get("textHeight", 2.5)),
            mark_type=d.get("markType", d.get("arrowheadType", "arrow")),
            arrow_size=float(d.get("arrowSize", d.get("arrowheadSize", 2.5))),
            text_position=d.get("textPosition", "above"),
            text_offset=float(d.get("textOffset", 0.0)),
            ext_offset=float(d.get("extOffset", 1.0)),
            dim_offset=float(d.get("dimOffset", 1.0)),
        )
