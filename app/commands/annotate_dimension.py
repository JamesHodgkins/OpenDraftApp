"""Dimension commands — linear and aligned annotation."""
from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import DimensionEntity
from app.entities.base import Vec2
from app.entities.line import LineEntity


@command("linearDimensionCommand")
class LinearDimensionCommand(CommandBase):
    """Add a linear (horizontal/vertical) dimension."""

    def execute(self) -> None:
        p1 = self.editor.get_point("Linear Dim: pick first measurement point")

        self.editor.set_dynamic(lambda m: [LineEntity(p1=p1, p2=m)])
        p2 = self.editor.get_point("Linear Dim: pick second measurement point")
        self.editor.clear_dynamic()

        def _preview(m: Vec2):
            return [DimensionEntity(p1=p1, p2=p2, p3=m, dim_type="linear")]

        self.editor.set_dynamic(_preview)
        p3 = self.editor.get_point("Linear Dim: pick dimension line position")
        self.editor.clear_dynamic()

        self.editor.add_entity(DimensionEntity(p1=p1, p2=p2, p3=p3, dim_type="linear"))


@command("alignedDimensionCommand")
class AlignedDimensionCommand(CommandBase):
    """Add an aligned dimension (parallel to the p1–p2 vector)."""

    def execute(self) -> None:
        p1 = self.editor.get_point("Aligned Dim: pick first measurement point")

        self.editor.set_dynamic(lambda m: [LineEntity(p1=p1, p2=m)])
        p2 = self.editor.get_point("Aligned Dim: pick second measurement point")
        self.editor.clear_dynamic()

        def _preview(m: Vec2):
            return [DimensionEntity(p1=p1, p2=p2, p3=m, dim_type="aligned")]

        self.editor.set_dynamic(_preview)
        p3 = self.editor.get_point("Aligned Dim: pick dimension line position")
        self.editor.clear_dynamic()

        self.editor.add_entity(DimensionEntity(p1=p1, p2=p2, p3=p3, dim_type="aligned"))
