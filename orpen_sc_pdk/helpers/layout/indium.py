"""Indium bump placement helpers for layout authoring."""

from collections.abc import Sequence
from math import floor
from typing import Literal

Point = tuple[float, float]


def indium_bump_centers_around_polygon(
    polygon: Sequence[Point],
    *,
    bump_size_um: float = 20.0,
    bump_gap_um: float = 40.0,
    margin_um: float = 90.0,
    clearance_um: float = 30.0,
    placement_mode: Literal["full_field", "corner_anchors"] = "full_field",
) -> tuple[Point, ...]:
    """Return indium bump centers around a polygon bounding box.

    This intentionally follows the simulation-scene helper semantics: bumps
    surround the target bounds and avoid a keepout expanded by clearance plus
    half the bump size.
    """

    if len(polygon) < 3:
        raise ValueError("polygon must contain at least three points.")
    if bump_size_um <= 0:
        raise ValueError(f"bump_size_um must be positive, got {bump_size_um!r}.")
    for name, value in (
        ("bump_gap_um", bump_gap_um),
        ("margin_um", margin_um),
        ("clearance_um", clearance_um),
    ):
        if value < 0:
            raise ValueError(f"{name} must be non-negative, got {value!r}.")
    if placement_mode not in ("full_field", "corner_anchors"):
        raise ValueError(
            f"placement_mode must be 'full_field' or 'corner_anchors', got {placement_mode!r}."
        )

    west, south, east, north = _polygon_bounds(polygon)
    if west == east or south == north:
        raise ValueError("polygon bounds must have positive width and height.")

    half = bump_size_um / 2
    pitch = bump_size_um + bump_gap_um
    keepout = (
        west - clearance_um - half,
        south - clearance_um - half,
        east + clearance_um + half,
        north + clearance_um + half,
    )
    field = (
        keepout[0] - margin_um,
        keepout[1] - margin_um,
        keepout[2] + margin_um,
        keepout[3] + margin_um,
    )

    for _ in range(1000):
        centers = tuple(
            (x, y)
            for x in _axis_centers(field[0], field[2], pitch)
            for y in _axis_centers(field[1], field[3], pitch)
            if not (keepout[0] <= x <= keepout[2] and keepout[1] <= y <= keepout[3])
        )
        if centers and (
            any(x < keepout[0] for x, _ in centers)
            and any(x > keepout[2] for x, _ in centers)
            and any(y < keepout[1] for _, y in centers)
            and any(y > keepout[3] for _, y in centers)
        ):
            if placement_mode == "full_field":
                return centers
            return _corner_anchor_centers(centers, keepout)
        field = (
            field[0] - pitch,
            field[1] - pitch,
            field[2] + pitch,
            field[3] + pitch,
        )

    raise RuntimeError("Could not place indium bumps around polygon.")


def _polygon_bounds(polygon: Sequence[Point]) -> tuple[float, float, float, float]:
    xs = [float(point[0]) for point in polygon]
    ys = [float(point[1]) for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _axis_centers(low: float, high: float, pitch: float) -> tuple[float, ...]:
    count = floor((high - low) / pitch) + 1
    start = (low + high) / 2 - ((count - 1) * pitch) / 2
    return tuple(start + index * pitch for index in range(count))


def _corner_anchor_centers(
    centers: Sequence[Point],
    box: tuple[float, float, float, float],
) -> tuple[Point, ...]:
    corners = (
        (box[0], box[1], lambda x, y: x < box[0] and y < box[1]),
        (box[0], box[3], lambda x, y: x < box[0] and y > box[3]),
        (box[2], box[1], lambda x, y: x > box[2] and y < box[1]),
        (box[2], box[3], lambda x, y: x > box[2] and y > box[3]),
    )
    selected = [
        min(
            ((x, y) for x, y in centers if predicate(x, y)),
            key=lambda point: (point[0] - corner_x) ** 2 + (point[1] - corner_y) ** 2,
        )
        for corner_x, corner_y, predicate in corners
    ]
    return tuple(dict.fromkeys(selected))


__all__ = [
    "indium_bump_centers_around_polygon",
]
