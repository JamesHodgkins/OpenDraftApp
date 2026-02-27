"""Draw polyline command — pick vertices, press Escape to finish."""
from app.editor import command
from app.editor.base_command import CommandBase, CommandCancelled
from app.entities import PolylineEntity


@command("polylineCommand")
class DrawPolylineCommand(CommandBase):
    """Draw an open polyline by picking successive vertices.

    Pick at least two points.  Press **Escape** to finish the polyline with
    the points collected so far (a minimum of two are required).  Pressing
    Escape before two points have been picked cancels the command entirely.
    """

    def execute(self) -> None:
        points = []
        try:
            first = self.editor.get_point(
                "Polyline: pick first vertex (Esc to cancel)"
            )
            points.append(first)
            # Preview: draw confirmed segments plus a trailing segment to the cursor.
            self.editor.set_dynamic(
                lambda m: [PolylineEntity(points=points + [m], closed=False)]
            )

            while True:
                pts = len(points)
                tip = "Esc to finish" if pts >= 2 else "Esc to cancel"
                pt = self.editor.get_point(
                    f"Polyline: pick vertex {pts + 1} \u2014 {tip}"
                )
                points.append(pt)

        except CommandCancelled:
            self.editor.clear_dynamic()
            # Finish gracefully if at least two points were collected;
            # otherwise let the cancellation propagate (no entity created).
            if len(points) >= 2:
                self.editor.add_entity(PolylineEntity(points=points, closed=False))
            else:
                raise

