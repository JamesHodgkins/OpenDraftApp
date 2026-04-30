"""Draw ellipse command — pick centre, then major-axis endpoint, then minor radius."""
import math

from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import LineEntity, Vec2
from app.entities.ellipse import EllipseEntity


@command("ellipseCommand")
class DrawEllipseCommand(StatefulCommandBase):
    """Draw an ellipse: pick centre, major-axis point, then minor-axis distance."""

    center = export(None, label="Center", input_kind="point")
    major_axis_point = export(None, label="Major-axis point", input_kind="point")
    minor_axis_point = export(None, label="Minor-axis point", input_kind="point")

    def start(self) -> None:
        self.begin(
            active_export="center",
            reset=("center", "major_axis_point", "minor_axis_point"),
        )

    def update(self) -> None:
        center = self.point_value("center")
        major = self.point_value("major_axis_point")
        minor = self.point_value("minor_axis_point")

        self.set_snap_for_active(
            {
                "major_axis_point": center,
                "minor_axis_point": major,
                "center": (major, minor),
            },
            default=(minor, major, center),
        )

        if center is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2) -> list:
            if major is None:
                return [LineEntity(p1=center, p2=mouse)]

            radius_x = math.hypot(major.x - center.x, major.y - center.y)
            if radius_x < 1e-6:
                return [LineEntity(p1=center, p2=mouse)]

            rotation = math.atan2(major.y - center.y, major.x - center.x)
            probe = minor if minor is not None else mouse
            perp_angle = rotation + math.pi / 2
            px = math.cos(perp_angle)
            py = math.sin(perp_angle)
            dx = probe.x - center.x
            dy = probe.y - center.y
            radius_y = max(abs(dx * px + dy * py), 1e-6)
            return [
                EllipseEntity(
                    center=center,
                    radius_x=radius_x,
                    radius_y=radius_y,
                    rotation=rotation,
                )
            ]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        center = self.point_value("center")
        major = self.point_value("major_axis_point")
        minor = self.point_value("minor_axis_point")
        if center is None or major is None or minor is None:
            self.editor.status_message.emit("Ellipse: center, major, and minor points are required")
            return

        radius_x = math.hypot(major.x - center.x, major.y - center.y)
        if radius_x < 1e-6:
            self.editor.status_message.emit("Ellipse: zero-length major axis - cancelled")
            return

        rotation = math.atan2(major.y - center.y, major.x - center.x)
        perp_angle = rotation + math.pi / 2
        px, py = math.cos(perp_angle), math.sin(perp_angle)
        dx = minor.x - center.x
        dy = minor.y - center.y
        radius_y = max(abs(dx * px + dy * py), 1e-6)

        self.editor.add_entity(
            EllipseEntity(
                center=center,
                radius_x=radius_x,
                radius_y=radius_y,
                rotation=rotation,
            )
        )
        self.editor.snap_from_point = minor
