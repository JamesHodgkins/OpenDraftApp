"""Command-mode cursor flow helpers for CADCanvas.

Encapsulates snap/draftmate activation logic and dynamic-input gating so the
canvas widget can remain a thin UI coordinator.
"""

from __future__ import annotations

from typing import Optional

from app.editor.draftmate import DraftmateResult
from app.editor.osnap_engine import SnapResult
from app.entities import Vec2

_POINT_INPUT_MODES = ("point", "angle", "length")


def is_snap_active(
    *,
    active_grip,
    editor,
    document,
    osnap_master: bool,
) -> bool:
    """Return True when command-mode OSNAP evaluation should run."""
    return (
        active_grip is None
        and editor is not None
        and getattr(editor, "_input_mode", "none") in _POINT_INPUT_MODES
        and document is not None
        and osnap_master
        and not getattr(editor, "suppress_osnap", False)
    )


def update_snap_and_draftmate(
    *,
    active_grip,
    editor,
    document,
    osnap_master: bool,
    osnap_engine,
    draftmate_engine,
    raw: Vec2,
    scale: float,
    existing_snap_result: Optional[SnapResult],
) -> tuple[bool, Optional[SnapResult], Optional[DraftmateResult], Optional[Vec2]]:
    """Compute snap-active state plus latest snap/draftmate results.

    Returns (snap_active, snap_result, draftmate_result, from_point).
    """
    from_point = getattr(editor, "snap_from_point", None) if editor is not None else None
    snap_active = is_snap_active(
        active_grip=active_grip,
        editor=editor,
        document=document,
        osnap_master=osnap_master,
    )

    if snap_active and document is not None:
        snap_result = osnap_engine.snap(
            raw,
            document.entities,
            scale,
            from_point=from_point,
        )
    elif active_grip is None:
        # No active grip and no active point-input flow: clear snap marker.
        snap_result = None
    else:
        # Keep grip-move snap result computed in the dedicated grip path.
        snap_result = existing_snap_result

    if snap_active:
        draftmate_result = draftmate_engine.update(raw, snap_result, from_point, scale)
    else:
        draftmate_result = None

    return snap_active, snap_result, draftmate_result, from_point


#
# Note: The cursor-following dynamic input widget was removed in favor of the
# top-of-viewport terminal, so the canvas no longer needs dynamic-input gating.
#
