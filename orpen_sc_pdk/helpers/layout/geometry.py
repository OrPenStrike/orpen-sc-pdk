"""Small reusable geometry math helpers."""

import math

Point = tuple[float, float]
TAU = 2 * math.pi


def polar_point(radius: float, angle: float, origin: Point = (0.0, 0.0)) -> Point:
    """Compute a Cartesian point from a radial layout offset in degrees.

    Use when a component defines repeated radial anchors and the polar intent is
    clearer than writing ``cos``/``sin`` at each callsite.

    Example:
        anchor = polar_point(radius=250.0, angle=45.0)
    """

    angle_rad = math.radians(angle)
    ox, oy = origin
    return (ox + radius * math.cos(angle_rad), oy + radius * math.sin(angle_rad))


def rotate_point(point: Point, angle: float, origin: Point = (0.0, 0.0)) -> Point:
    """Rotate a layout point around an origin in degrees.

    Use when a cell transforms local semantic anchor points, not when a full
    GF reference transform would be clearer.

    Example:
        port_center = rotate_point((10.0, 0.0), angle=90.0, origin=(0.0, 0.0))
    """

    angle_rad = math.radians(angle)
    x, y = point
    ox, oy = origin
    dx = x - ox
    dy = y - oy
    return (
        ox + math.cos(angle_rad) * dx - math.sin(angle_rad) * dy,
        oy + math.sin(angle_rad) * dx + math.cos(angle_rad) * dy,
    )


__all__ = [
    "Point",
    "TAU",
    "polar_point",
    "rotate_point",
]
