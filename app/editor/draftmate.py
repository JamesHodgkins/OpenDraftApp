"""
Draftmate — Object Snap Tracking + Polar Tracking engine for OpenDraft.

Provides dynamic, temporary alignment guides by "tracking" acquired snap
points and projecting infinite extension lines from them.  Offers polar
tracking at configurable angle increments from the current base point.

Architecture
------------
The engine is instantiated once by ``CADCanvas`` and consulted on every
``mouseMoveEvent`` when a command is waiting for point input.  It:

1.  **Acquires** snap points the user hovers over for ≥ ``acquire_ms``
    (default 400 ms) and marks them with green crosses.
2.  **Projects** horizontal/vertical extension lines from tracked points,
    enabling intersectional alignment snapping.
3.  **Computes** polar guides at the configured angle increment from the
    command's base (from) point.
4.  Returns an optional ``DraftmateResult`` consumed by the canvas to
    override the cursor position and draw visual feedback.

Mutual exclusivity
------------------
Draftmate and Ortho mode are mutually exclusive.  The caller is responsible
for disabling Ortho when Draftmate is activated (and vice-versa).

Visual feedback
---------------
- **Green crosses (+)** — tracked (acquired) points.
- **Green dashed lines** — active alignment / polar guides.
- Standard OSNAP markers are drawn separately by the canvas.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Set, Tuple

from app.entities.base import Vec2
from app.entities.snap_types import SnapResult, SnapType


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrackedPoint:
    """A point acquired for object-snap tracking."""
    point: Vec2
    snap_type: SnapType
    entity_id: str = ""


@dataclass
class AlignmentLine:
    """An infinite alignment guide rendered as a green dashed line.

    Stored as a line from *origin* in *direction* (unit vector).
    The canvas clips it to the viewport when drawing.
    """
    origin: Vec2
    direction: Vec2           # unit vector
    kind: str = "ortho"       # "ortho" | "polar"


@dataclass
class DraftmateResult:
    """Result returned by :meth:`DraftmateEngine.update` each frame."""
    tracked_points: List[TrackedPoint]
    alignment_lines: List[AlignmentLine]
    # If the cursor is close enough to an alignment intersection, this is
    # the snapped cursor position; otherwise ``None``.
    snapped_point: Optional[Vec2] = None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass
class DraftmateSettings:
    """User-configurable Draftmate parameters."""
    enabled: bool = False
    polar_angle_deg: float = 45.0
    max_tracked: int = 6
    acquire_ms: int = 400               # hover time to acquire a point (ms)
    snap_tolerance_px: float = 8.0      # pixel proximity for alignment snap
    # Which OSNAP types qualify for tracking:
    trackable_types: Set[SnapType] = field(default_factory=lambda: {
        SnapType.ENDPOINT,
        SnapType.MIDPOINT,
        SnapType.CENTER,
    })


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DraftmateEngine:
    """Core Draftmate engine — call :meth:`update` every mouse-move frame.

    Parameters
    ----------
    settings:
        A :class:`DraftmateSettings` instance.  Mutate its fields at
        runtime to reflect user configuration changes.
    """

    def __init__(self, settings: Optional[DraftmateSettings] = None) -> None:
        self.settings: DraftmateSettings = settings or DraftmateSettings()
        # Acquired (tracked) points — newest at the end.
        self._tracked: List[TrackedPoint] = []
        # Hover acquisition state: the snap result being "hovered" for timing.
        self._hover_snap: Optional[SnapResult] = None
        self._hover_start: float = 0.0   # time.monotonic() when hover began

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def tracked_points(self) -> List[TrackedPoint]:
        """Currently tracked points (read-only copy)."""
        return list(self._tracked)

    def clear(self) -> None:
        """Remove all tracked points and reset hover state.

        Called by the canvas on ``mousedown`` so each drawing step starts
        clean.
        """
        self._tracked.clear()
        self._hover_snap = None
        self._hover_start = 0.0

    def update(
        self,
        cursor: Vec2,
        snap_result: Optional[SnapResult],
        from_point: Optional[Vec2],
        scale: float,
    ) -> Optional[DraftmateResult]:
        """Compute tracking / alignment for the current frame.

        Parameters
        ----------
        cursor:
            Raw world-space cursor position.
        snap_result:
            The OSNAP snap result for this frame (may be ``None``).
        from_point:
            The command's base / previous point (for polar guides).
        scale:
            Viewport pixels-per-world-unit (for pixel tolerance conversion).

        Returns ``None`` when Draftmate is disabled.
        """
        if not self.settings.enabled:
            return None

        now = time.monotonic()

        # ---- 1. Point acquisition (hover timing) -------------------------
        self._process_acquisition(snap_result, now)

        # ---- 2. Build alignment lines from tracked points -----------------
        alignment_lines: List[AlignmentLine] = []
        for tp in self._tracked:
            # Horizontal extension
            alignment_lines.append(AlignmentLine(
                origin=tp.point,
                direction=Vec2(1.0, 0.0),
                kind="ortho",
            ))
            # Vertical extension
            alignment_lines.append(AlignmentLine(
                origin=tp.point,
                direction=Vec2(0.0, 1.0),
                kind="ortho",
            ))

        # ---- 3. Polar guides from from_point -----------------------------
        if from_point is not None:
            polar_lines = self._polar_lines(from_point)
            alignment_lines.extend(polar_lines)

        # ---- 4. Snap cursor to nearest alignment line / intersection ------
        tol = self.settings.snap_tolerance_px / max(scale, 1e-12)
        snapped = self._snap_to_alignment(cursor, alignment_lines, tol)

        # ---- 5. Filter to only lines the cursor is actually near ----------
        # Guides are invisible unless the cursor (or snapped point) is close
        # enough to them, so the viewport isn't cluttered with all possible
        # angles at once.
        active_lines = _active_lines(cursor, alignment_lines, tol)

        return DraftmateResult(
            tracked_points=list(self._tracked),
            alignment_lines=active_lines,
            snapped_point=snapped,
        )

    # ------------------------------------------------------------------
    # Internals — acquisition
    # ------------------------------------------------------------------

    def _process_acquisition(
        self,
        snap_result: Optional[SnapResult],
        now: float,
    ) -> None:
        """Track dwell-time on a snap point and promote it once the
        threshold is reached."""
        if snap_result is None or snap_result.snap_type not in self.settings.trackable_types:
            # Cursor moved away from a trackable snap — reset timer.
            self._hover_snap = None
            self._hover_start = 0.0
            return

        # Check if this is the same snap as last frame.
        if (
            self._hover_snap is not None
            and _same_snap(self._hover_snap, snap_result)
        ):
            # Continue timing…
            elapsed_ms = (now - self._hover_start) * 1000.0
            if elapsed_ms >= self.settings.acquire_ms:
                self._acquire(snap_result)
                self._hover_snap = None
                self._hover_start = 0.0
        else:
            # New candidate — start timing.
            self._hover_snap = snap_result
            self._hover_start = now

    def _acquire(self, snap: SnapResult) -> None:
        """Promote a snap result to a tracked point (if not duplicate)."""
        for tp in self._tracked:
            if _near(tp.point, snap.point, 1e-6):
                return  # already tracked

        tp = TrackedPoint(
            point=snap.point,
            snap_type=snap.snap_type,
            entity_id=snap.entity_id,
        )
        self._tracked.append(tp)

        # Evict oldest if over the limit.
        while len(self._tracked) > self.settings.max_tracked:
            self._tracked.pop(0)

    # ------------------------------------------------------------------
    # Internals — polar guides
    # ------------------------------------------------------------------

    def _polar_lines(self, from_point: Vec2) -> List[AlignmentLine]:
        """Generate polar guide lines at the configured angle increments."""
        inc = self.settings.polar_angle_deg
        if inc <= 0:
            return []

        lines: List[AlignmentLine] = []
        angle = 0.0
        while angle < 360.0:
            rad = math.radians(angle)
            d = Vec2(math.cos(rad), math.sin(rad))
            lines.append(AlignmentLine(origin=from_point, direction=d, kind="polar"))
            angle += inc
        return lines

    # ------------------------------------------------------------------
    # Internals — alignment snapping
    # ------------------------------------------------------------------

    def _snap_to_alignment(
        self,
        cursor: Vec2,
        lines: List[AlignmentLine],
        tol: float,
    ) -> Optional[Vec2]:
        """Snap cursor to the nearest alignment guide or intersection.

        First tries intersections between pairs of alignment lines (e.g.
        the X-guide of one point crossing the Y-guide of another), then
        falls back to the nearest single-line projection.
        """
        if not lines:
            return None

        # ---- Intersection snapping (highest priority) ---------------------
        best_int: Optional[Vec2] = None
        best_int_dist = float("inf")

        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                pt = _line_line_intersect(lines[i], lines[j])
                if pt is None:
                    continue
                d = _dist(pt, cursor)
                if d <= tol and d < best_int_dist:
                    best_int = pt
                    best_int_dist = d

        if best_int is not None:
            return best_int

        # ---- Single-line projection (lower priority) ----------------------
        best_proj: Optional[Vec2] = None
        best_proj_dist = float("inf")

        for ln in lines:
            proj = _project_onto_line(cursor, ln)
            d = _dist(proj, cursor)
            if d <= tol and d < best_proj_dist:
                best_proj = proj
                best_proj_dist = d

        return best_proj

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _dist(a: Vec2, b: Vec2) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _near(a: Vec2, b: Vec2, tol: float) -> bool:
    return _dist(a, b) < tol


def _same_snap(a: SnapResult, b: SnapResult) -> bool:
    """True when *a* and *b* refer to the same tracked snap candidate."""
    return (
        a.snap_type == b.snap_type
        and a.entity_id == b.entity_id
        and _near(a.point, b.point, 1e-6)
    )


def _project_onto_line(p: Vec2, ln: AlignmentLine) -> Vec2:
    """Orthogonal projection of *p* onto the infinite line through *ln*."""
    dx, dy = ln.direction.x, ln.direction.y
    t = (p.x - ln.origin.x) * dx + (p.y - ln.origin.y) * dy
    return Vec2(ln.origin.x + t * dx, ln.origin.y + t * dy)


def _point_line_dist(p: Vec2, ln: AlignmentLine) -> float:
    """Perpendicular distance from *p* to the infinite line *ln*."""
    proj = _project_onto_line(p, ln)
    return _dist(p, proj)


def _active_lines(
    cursor: Vec2,
    lines: List[AlignmentLine],
    tol: float,
) -> List[AlignmentLine]:
    """Return active alignment lines the cursor is within *tol* of.

    All qualifying ortho lines are kept, but at most **one** polar line
    (the nearest) is included so the viewport stays uncluttered.
    """
    active_ortho: List[AlignmentLine] = []
    best_polar: Optional[AlignmentLine] = None
    best_polar_dist: float = float("inf")

    for ln in lines:
        d = _point_line_dist(cursor, ln)
        if d > tol:
            continue
        if ln.kind != "polar":
            active_ortho.append(ln)
        elif d < best_polar_dist:
            best_polar = ln
            best_polar_dist = d

    if best_polar is not None:
        active_ortho.append(best_polar)
    return active_ortho


def _line_line_intersect(a: AlignmentLine, b: AlignmentLine) -> Optional[Vec2]:
    """Intersection of two infinite lines, or ``None`` if parallel."""
    # a: P + t*D,  b: Q + s*E
    denom = a.direction.x * b.direction.y - a.direction.y * b.direction.x
    if abs(denom) < 1e-12:
        return None  # (near) parallel
    qp_x = b.origin.x - a.origin.x
    qp_y = b.origin.y - a.origin.y
    t = (qp_x * b.direction.y - qp_y * b.direction.x) / denom
    return Vec2(a.origin.x + t * a.direction.x, a.origin.y + t * a.direction.y)
