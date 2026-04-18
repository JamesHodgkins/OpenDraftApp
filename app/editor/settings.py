"""
Editor-wide settings and tolerances.

A single :class:`EditorSettings` instance lives on the :class:`~app.editor.Editor`
and is the sole source of truth for all configurable thresholds. Subsystems
read from it at initialisation time (canvas, OSNAP engine) or at call time
(commands), so changing a value here propagates everywhere without hunting
down magic numbers spread across multiple files.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EditorSettings:
    """Centralised tolerances and user-configurable editor preferences.

    Attributes
    ----------
    pick_tolerance_px:
        Pixel radius for click-to-select entity hit testing.
    grip_pick_px:
        Pixel tolerance for detecting grip hover / pick.
    grip_half_size_px:
        Half-width of rendered grip squares in screen pixels.
    osnap_aperture_px:
        Snap aperture passed to :class:`~app.editor.osnap_engine.OsnapEngine`.
    extend_boundary_tolerance:
        Pixel tolerance used when picking the boundary entity in Extend.
    extend_target_tolerance:
        Pixel tolerance used when picking the entity to extend.
    trim_pick_tolerance:
        Pixel tolerance used when picking entities during Trim.
    """

    pick_tolerance_px: float = 7.0
    grip_pick_px: float = 7.0
    grip_half_size_px: int = 5
    osnap_aperture_px: float = 12.0
    extend_boundary_tolerance: float = 10.0
    extend_target_tolerance: float = 20.0
    trim_pick_tolerance: float = 10.0
