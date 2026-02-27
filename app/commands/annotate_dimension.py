"""Dimension commands — linear and aligned annotation."""
from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import DimensionEntity


@command("linearDimensionCommand")
class LinearDimensionCommand(CommandBase):
    """Add a linear (horizontal/vertical) dimension.

    Pick the two measurement points, then pick the dimension-line offset
    point (p3) which controls how far the annotation sits from the geometry.
    """

    def execute(self) -> None:
        p1 = self.editor.get_point("Linear Dim: pick first measurement point")
        p2 = self.editor.get_point("Linear Dim: pick second measurement point")
        p3 = self.editor.get_point("Linear Dim: pick dimension line position")
        self.editor.add_entity(DimensionEntity(
            p1=p1, p2=p2, p3=p3,
            dim_type="linear",
        ))


@command("alignedDimensionCommand")
class AlignedDimensionCommand(CommandBase):
    """Add an aligned dimension (parallel to the p1–p2 vector).

    Same three-pick workflow as the linear dimension.
    """

    def execute(self) -> None:
        p1 = self.editor.get_point("Aligned Dim: pick first measurement point")
        p2 = self.editor.get_point("Aligned Dim: pick second measurement point")
        p3 = self.editor.get_point("Aligned Dim: pick dimension line position")
        self.editor.add_entity(DimensionEntity(
            p1=p1, p2=p2, p3=p3,
            dim_type="aligned",
        ))
