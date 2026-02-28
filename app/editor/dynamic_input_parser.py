"""
Dynamic input parser for parsing user input during point, integer, float, and string inputs.

Supports multiple input formats:
- Vector inputs (when editor requests a point):
  * Relative: "dx,dy" or "dx dy" (e.g., "10,20" or "10 20")
  * Absolute: "#x,y" or "#x y" (e.g., "#100,50" or "#100 50")
  * Polar: "distance<angle" or "distance@angle" (e.g., "100<45" or "100@45")
  * Direct coordinates: "x,y" (relative to last point or 0,0)

- Scalar inputs (integer/float):
  * Direct value (e.g., "42" or "3.14")
"""
from __future__ import annotations

import re
from typing import Optional, Union, Tuple
from math import radians, cos, sin

from app.entities import Vec2


class DynamicInputParser:
    """Parse various input formats for CAD commands."""

    @staticmethod
    def parse_vector(
        input_str: str,
        current_pos: Vec2,
        base_point: Optional[Vec2] = None,
    ) -> Optional[Vec2]:
        """Parse vector input in various formats.

        Parameters
        ----------
        input_str:
            User input string. Supports:
            - Relative: "dx,dy" or "dx dy"
            - Absolute: "#x,y" or "#x y"
            - Polar: "distance<angle" or "distance@angle"

        current_pos:
            Current cursor position in world coordinates (for default display).

        base_point:
            Reference point for relative coordinates. If None, assumes (0, 0).

        Returns
        -------
        Optional[Vec2]
            Parsed vector, or None if parsing fails.
        """
        input_str = input_str.strip()
        if not input_str:
            return None

        # Try absolute coordinates (#x,y)
        if input_str.startswith("#"):
            return DynamicInputParser._parse_absolute(input_str[1:])

        # Try polar coordinates (distance<angle or distance@angle)
        if "<" in input_str or "@" in input_str:
            return DynamicInputParser._parse_polar(input_str, base_point)

        # Try relative coordinates (dx,dy)
        return DynamicInputParser._parse_relative(input_str, base_point)

    @staticmethod
    def _parse_absolute(coord_str: str) -> Optional[Vec2]:
        """Parse absolute coordinates: x,y or x y."""
        coord_str = coord_str.strip()
        # Replace various separators with comma for uniform parsing
        coord_str = re.sub(r"[\s,;]+", ",", coord_str)
        parts = coord_str.split(",")

        if len(parts) != 2:
            return None

        try:
            x = float(parts[0].strip())
            y = float(parts[1].strip())
            return Vec2(x, y)
        except ValueError:
            return None

    @staticmethod
    def _parse_relative(coord_str: str, base_point: Optional[Vec2] = None) -> Optional[Vec2]:
        """Parse relative coordinates: dx,dy or dx dy."""
        if base_point is None:
            base_point = Vec2(0, 0)

        coord_str = coord_str.strip()
        # Replace various separators with comma for uniform parsing
        coord_str = re.sub(r"[\s,;]+", ",", coord_str)
        parts = coord_str.split(",")

        if len(parts) != 2:
            return None

        try:
            dx = float(parts[0].strip())
            dy = float(parts[1].strip())
            return Vec2(base_point.x + dx, base_point.y + dy)
        except ValueError:
            return None

    @staticmethod
    def _parse_polar(coord_str: str, base_point: Optional[Vec2] = None) -> Optional[Vec2]:
        """Parse polar coordinates: distance<angle or distance@angle.

        Angle is in degrees, measured counter-clockwise from the positive X-axis.
        """
        if base_point is None:
            base_point = Vec2(0, 0)

        # Replace @ with < for uniform parsing
        coord_str = coord_str.replace("@", "<").strip()

        match = re.match(r"^([\d.]+)\s*<\s*([\d.]+)$", coord_str)
        if not match:
            return None

        try:
            distance = float(match.group(1))
            angle_deg = float(match.group(2))
            angle_rad = radians(angle_deg)
            dx = distance * cos(angle_rad)
            dy = distance * sin(angle_rad)
            return Vec2(base_point.x + dx, base_point.y + dy)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def parse_scalar(input_str: str) -> Optional[Union[int, float]]:
        """Parse integer or float input.

        Parameters
        ----------
        input_str:
            User input string.

        Returns
        -------
        Optional[Union[int, float]]
            Parsed number, or None if parsing fails.
        """
        input_str = input_str.strip()
        if not input_str:
            return None

        try:
            # Try integer first
            if "." not in input_str:
                return int(input_str)
            else:
                return float(input_str)
        except ValueError:
            return None

    @staticmethod
    def format_vector_for_display(
        pt: Vec2,
        format_type: str = "relative",
        base_point: Optional[Vec2] = None,
    ) -> tuple[str, str]:
        """Format a vector for display in input boxes.

        Parameters
        ----------
        pt:
            Point to format.

        format_type:
            "relative", "absolute", or "polar".

        base_point:
            Reference point for relative/polar formatting.

        Returns
        -------
        tuple[str, str]
            (value1, value2) for display.
        """
        if format_type == "absolute":
            return f"{pt.x:.2f}", f"{pt.y:.2f}"
        elif format_type == "polar":
            if base_point is None:
                base_point = Vec2(0, 0)
            dx = pt.x - base_point.x
            dy = pt.y - base_point.y
            from math import atan2, sqrt, degrees
            distance = sqrt(dx**2 + dy**2)
            angle = degrees(atan2(dy, dx))
            return f"{distance:.2f}", f"{angle:.2f}"
        else:  # relative
            if base_point is None:
                base_point = Vec2(0, 0)
            dx = pt.x - base_point.x
            dy = pt.y - base_point.y
            return f"{dx:.2f}", f"{dy:.2f}"
