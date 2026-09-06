"""Dimension commands — linear and aligned annotation."""
from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import DimensionEntity, LineEntity, Vec2


class _BaseDimensionCommand(StatefulCommandBase):
    """Shared stateful workflow for dimension placement."""

    dim_type: str = "linear"
    prompt_name: str = "Dimension"

    first_point = export(None, label="First measurement point", input_kind="point")
    second_point = export(None, label="Second measurement point", input_kind="point")
    dimension_line_point = export(None, label="Dimension line position", input_kind="point")

    def start(self) -> None:
        self.begin(
            active_export="first_point",
            reset=("first_point", "second_point", "dimension_line_point"),
        )

    def update(self) -> None:
        p1 = self.point_value("first_point")
        p2 = self.point_value("second_point")
        p3 = self.point_value("dimension_line_point")

        self.set_snap_for_active(
            {
                "second_point": p1,
                "dimension_line_point": p2,
                "first_point": (p3, p2),
            },
            default=(p3, p2, p1),
        )

        if p1 is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2):
            if p2 is None:
                return [LineEntity(p1=p1, p2=mouse)]

            dim_line = p3 if p3 is not None else mouse
            return [
                DimensionEntity(
                    p1=p1,
                    p2=p2,
                    p3=dim_line,
                    dim_type=self.dim_type,
                )
            ]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        p1 = self.point_value("first_point")
        p2 = self.point_value("second_point")
        p3 = self.point_value("dimension_line_point")
        if p1 is None or p2 is None or p3 is None:
            self.editor.status_message.emit(
                f"{self.prompt_name}: measurement points and dimension line position are required"
            )
            return

        self.editor.add_entity(
            DimensionEntity(
                p1=p1,
                p2=p2,
                p3=p3,
                dim_type=self.dim_type,
            )
        )
        self.editor.snap_from_point = p3


@command("linearDimensionCommand")
class LinearDimensionCommand(_BaseDimensionCommand):
    """Add a linear (horizontal/vertical) dimension."""

    dim_type = "linear"
    prompt_name = "Linear Dim"


@command("alignedDimensionCommand")
class AlignedDimensionCommand(_BaseDimensionCommand):
    """Add an aligned dimension (parallel to the p1–p2 vector)."""

    dim_type = "aligned"
    prompt_name = "Aligned Dim"
