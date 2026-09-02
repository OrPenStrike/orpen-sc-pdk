"""Layout routing helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from heapq import heappop, heappush
from itertools import count
from math import atan2, ceil, cos, degrees, floor, hypot, pi, radians, sin, tan
from typing import Any, cast

import gdsfactory as gf
import networkx as nx
import numpy as np
from gdsfactory.routing.route_astar import (
    _generate_grid,
    get_route_bend_count,
    route_astar_single,
)
from gdsfactory.typings import ComponentSpec, CrossSectionSpec, LayerSpec, Port, Route

Coordinate = tuple[float, float]
RouteBbox = tuple[float, float, float, float]
GridNode = tuple[int, int]
_PATH_REGION_LAYER: LayerSpec = (1, 0)


@dataclass(frozen=True)
class EightDirectionRoutePlan:
    """Describe an 8-direction centerline route before GF geometry rendering.

    Use when callers need route diagnostics, length, turn count, or debug
    drawing without inspecting the rendered route component.

    Example:
        plan = plan_route_8dir(port1, port2, keepout_region=keepout)
    """

    points: list[Coordinate]
    length: float
    cost: float
    turns: int
    grid_resolution: float
    visited_nodes: int


@dataclass
class EightDirectionRoute:
    """Bundle a rendered route reference with its planning metadata.

    Use when chip assembly code needs both the GF reference added to the parent
    component and the plan metrics used to create it.

    Example:
        routes, plans = route_bundle_8dir(c, [p1], [p2], cross_section="cpw_6_7_6")
    """

    reference: gf.ComponentReference
    component: gf.Component
    plan: EightDirectionRoutePlan
    length: float
    start_straight_length: float
    end_straight_length: float
    min_straight_between_turns: float
    bend_style: str


@dataclass
class RoutePair8Dir:
    """Specify one net and optional per-net routing overrides.

    Use when a global bundle needs different cross sections, bend radii, or
    lead lengths per routed pair.

    Example:
        pair = RoutePair8Dir("readout", port1=left, port2=right, bend_radius=100.0)
    """

    name: str
    port1: Port
    port2: Port
    cross_section: CrossSectionSpec | None = None
    bend_radius: float | None = None
    start_straight_length: float | None = None
    end_straight_length: float | None = None
    min_straight_between_turns: float | None = None
    bend_margin: float | None = None
    bend_style: str | None = None
    euler_angular_step: float | None = None
    simplify: float | None = None


@dataclass(frozen=True)
class RouteConflict8Dir:
    """Report the first physical route-resource conflict in global routing.

    Use when the global router fails or resolves conflicts and the caller needs
    actionable route names and a bounding box for debugging.

    Example:
        conflict = bundle.last_conflict
    """

    route1_index: int
    route2_index: int
    route1_name: str
    route2_name: str
    bbox: RouteBbox


@dataclass
class GlobalEightDirectionRouteBundle:
    """Collect routes and search metrics from global 8-direction routing.

    Use when routing several nets together and the caller needs the rendered
    routes plus whether conflict resolution found an optimal bundle.

    Example:
        bundle = route_bundle_8dir_global(c, route_pairs=pairs, keepout_region=keepout)
    """

    routes: list[EightDirectionRoute]
    plans: list[EightDirectionRoutePlan]
    route_pairs: list[RoutePair8Dir]
    total_length: float
    total_cost: float
    search_nodes: int
    conflicts_resolved: int
    is_optimal: bool
    last_conflict: RouteConflict8Dir | None = None


@dataclass
class _RouteCandidate8Dir:
    pair: RoutePair8Dir
    plan: EightDirectionRoutePlan
    path: gf.Path
    cross_section: Any
    simplify: float | None
    resource_region: gf.Region
    resource_width: float
    length: float
    cost: float
    start_straight_length: float
    end_straight_length: float
    min_straight_between_turns: float
    bend_style: str


@dataclass
class _GlobalSearchNode8Dir:
    constraints: tuple[tuple[gf.Region, ...], ...]
    constraint_keys: tuple[tuple[tuple[int, int, int, int], ...], ...]
    candidates: tuple[_RouteCandidate8Dir, ...]
    cost: float
    length: float
    conflicts_resolved: int


_DIRECTION_STEPS_8: tuple[GridNode, ...] = (
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
    (0, -1),
    (1, -1),
)


def _orientation_vector(orientation: float) -> Coordinate:
    radians = orientation * pi / 180
    return (cos(radians), sin(radians))


def _point_along_orientation(
    point: Coordinate,
    orientation: float,
    distance: float,
) -> Coordinate:
    vx, vy = _orientation_vector(orientation)
    return (point[0] + vx * distance, point[1] + vy * distance)


def _port_with_center(port: Port, center: Coordinate) -> Port:
    return Port(
        name=port.name,
        width=port.width,
        orientation=port.orientation,
        center=center,
        layer_info=port.layer_info,
        port_type=port.port_type,
        cross_section=port.cross_section,
    )


def _dedupe_consecutive_points(points: Sequence[Coordinate]) -> list[Coordinate]:
    deduped: list[Coordinate] = []
    for point in points:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    return deduped


def _as_port_list(ports: Port | Sequence[Port]) -> list[Port]:
    if hasattr(ports, "center"):
        return [cast(Port, ports)]
    return list(ports)


def _normalize_route_pairs(
    route_pairs: Sequence[RoutePair8Dir] | None,
    ports1: Port | Sequence[Port] | None,
    ports2: Port | Sequence[Port] | None,
    cross_section: CrossSectionSpec,
) -> list[RoutePair8Dir]:
    if route_pairs is not None:
        if ports1 is not None or ports2 is not None:
            raise ValueError("Use either route_pairs or ports1/ports2, not both.")
        if not route_pairs:
            raise ValueError("route_pairs must contain at least one pair.")
        return list(route_pairs)

    if ports1 is None or ports2 is None:
        raise ValueError("Either route_pairs or both ports1 and ports2 are required.")

    ports1_list = _as_port_list(ports1)
    ports2_list = _as_port_list(ports2)
    if len(ports1_list) != len(ports2_list):
        raise ValueError(
            f"ports1 and ports2 must have the same length, got {len(ports1_list)} "
            f"and {len(ports2_list)}."
        )

    return [
        RoutePair8Dir(
            name=f"route_{index}",
            port1=port1,
            port2=port2,
            cross_section=cross_section,
        )
        for index, (port1, port2) in enumerate(zip(ports1_list, ports2_list, strict=True))
    ]


def _merged_region(
    base_region: gf.Region | None,
    extra_regions: Sequence[gf.Region] = (),
) -> gf.Region | None:
    region = gf.Region()
    if base_region is not None and not base_region.is_empty():
        region += base_region
    for extra_region in extra_regions:
        if not extra_region.is_empty():
            region += extra_region

    if region.is_empty():
        return None
    return region.merged()


def _region_bbox_key(region: gf.Region) -> tuple[int, int, int, int]:
    bbox = region.bbox()
    return (bbox.left, bbox.bottom, bbox.right, bbox.top)


def _cross_section_footprint_width(cross_section: gf.CrossSection) -> float:
    half_width = cross_section.width / 2
    for section in cross_section.sections:
        half_width = max(half_width, abs(section.offset) + section.width / 2)
    return 2 * half_width


def _resolve_route_straight_length(
    length: float | None,
    *,
    bend_radius: float,
    grid_resolution: float,
    name: str,
) -> float:
    if length is None:
        return max(grid_resolution, bend_radius)
    if length < 0:
        raise ValueError(f"{name} must be non-negative, got {length!r}.")
    return length


def _resolve_min_straight_between_turns(
    length: float | None,
) -> float:
    if length is None:
        return 0.0
    if length < 0:
        raise ValueError(f"min_straight_between_turns must be non-negative, got {length!r}.")
    return length


def _circular_bend_points(
    radius: float,
    angle: float,
    angular_step: float,
) -> np.ndarray:
    signed_angle = angle
    angle = abs(angle)
    sample_count = max(8, ceil(angle / angular_step))
    theta = np.linspace(0, radians(angle), sample_count + 1)
    points = np.column_stack(
        [
            radius * np.sin(theta),
            radius * (1 - np.cos(theta)),
        ]
    )
    if signed_angle < 0:
        points[:, 1] *= -1
    return points


@lru_cache(maxsize=128)
def _normalized_euler_bend_points(
    angle: float,
    angular_step: float,
) -> tuple[tuple[float, float], ...]:
    angle = abs(angle)
    if angle <= 1e-9:
        return ((0.0, 0.0),)

    theta = radians(angle)
    half_length = theta
    sample_count = max(16, ceil(angle / angular_step) * 4)
    sample_positions = np.linspace(0, 2 * half_length, sample_count + 1)
    tangent_angles = np.empty_like(sample_positions)

    first_half = sample_positions <= half_length
    tangent_angles[first_half] = sample_positions[first_half] ** 2 / (2 * half_length)

    second_positions = sample_positions[~first_half] - half_length
    tangent_angles[~first_half] = (
        theta / 2 + second_positions - second_positions**2 / (2 * half_length)
    )

    points = np.zeros((sample_count + 1, 2))
    for index in range(1, sample_count + 1):
        ds = sample_positions[index] - sample_positions[index - 1]
        points[index, 0] = (
            points[index - 1, 0]
            + 0.5 * (cos(tangent_angles[index - 1]) + cos(tangent_angles[index])) * ds
        )
        points[index, 1] = (
            points[index - 1, 1]
            + 0.5 * (sin(tangent_angles[index - 1]) + sin(tangent_angles[index])) * ds
        )

    return tuple((float(point[0]), float(point[1])) for point in points)


def _euler_bend_points(
    radius: float,
    angle: float,
    angular_step: float,
) -> np.ndarray:
    normalized_points = np.array(
        _normalized_euler_bend_points(
            round(abs(angle), 9),
            round(angular_step, 9),
        )
    )
    points = normalized_points * radius
    if angle < 0:
        points[:, 1] *= -1
    return points


def _bend_shape_points(
    *,
    radius: float,
    angle: float,
    bend_style: str,
    angular_step: float,
) -> np.ndarray:
    if bend_style == "circular":
        return _circular_bend_points(
            radius=radius,
            angle=angle,
            angular_step=angular_step,
        )
    if bend_style == "euler":
        return _euler_bend_points(
            radius=radius,
            angle=angle,
            angular_step=angular_step,
        )
    raise ValueError(f"bend_style must be 'circular' or 'euler', got {bend_style!r}.")


def _bend_tangent_length(angle: float, radius: float, bend_style: str) -> float:
    angle = abs(angle)
    if angle <= 1e-9:
        return 0.0
    if angle >= 180:
        raise ValueError(f"Bend angle must be smaller than 180 degrees, got {angle!r}.")
    if bend_style == "circular":
        return radius * tan(radians(angle / 2))
    if bend_style == "euler":
        end_x, end_y = _normalized_euler_bend_points(angle, 1.0)[-1]
        return radius * (end_x - end_y / tan(radians(angle)))
    raise ValueError(f"bend_style must be 'circular' or 'euler', got {bend_style!r}.")


def _turn_angle_degrees(direction1: int, direction2: int) -> float:
    delta = (direction2 - direction1) % len(_DIRECTION_STEPS_8)
    if delta > len(_DIRECTION_STEPS_8) / 2:
        delta -= len(_DIRECTION_STEPS_8)
    return delta * 45.0


def _unit_vector(point1: Coordinate, point2: Coordinate) -> Coordinate:
    dx = point2[0] - point1[0]
    dy = point2[1] - point1[1]
    length = hypot(dx, dy)
    if length == 0:
        raise ValueError("Route points must not contain zero-length segments.")
    return (dx / length, dy / length)


def _signed_turn_angle(point1: Coordinate, point2: Coordinate, point3: Coordinate) -> float:
    v1 = _unit_vector(point1, point2)
    v2 = _unit_vector(point2, point3)
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    return degrees(atan2(cross, dot))


def _route_segment_requirements(
    points: Sequence[Coordinate],
    *,
    bend_radius: float,
    bend_style: str,
    min_straight_between_turns: float,
    bend_margin: float,
) -> list[float]:
    points = _simplify_collinear_points(_dedupe_consecutive_points(points))
    if len(points) < 2:
        raise ValueError("Route needs at least two points.")

    requirements = [0.0] * (len(points) - 1)
    interior_tangents: list[float] = []
    for index in range(1, len(points) - 1):
        angle = _signed_turn_angle(points[index - 1], points[index], points[index + 1])
        tangent = _bend_tangent_length(angle, bend_radius, bend_style)
        interior_tangents.append(tangent)
        requirements[index - 1] += tangent
        requirements[index] += tangent

    for index in range(1, len(points) - 2):
        if interior_tangents[index - 1] > 0 and interior_tangents[index] > 0:
            requirements[index] = max(requirements[index], min_straight_between_turns)

    return [requirement + bend_margin if requirement > 0 else 0.0 for requirement in requirements]


def _validate_route_bend_footprint(
    points: Sequence[Coordinate],
    *,
    bend_radius: float,
    bend_style: str,
    min_straight_between_turns: float,
    bend_margin: float,
) -> None:
    points = _simplify_collinear_points(_dedupe_consecutive_points(points))
    requirements = _route_segment_requirements(
        points,
        bend_radius=bend_radius,
        bend_style=bend_style,
        min_straight_between_turns=min_straight_between_turns,
        bend_margin=bend_margin,
    )
    for index, (point1, point2) in enumerate(zip(points, points[1:], strict=False)):
        length = hypot(point2[0] - point1[0], point2[1] - point1[1])
        if length + 1e-6 < requirements[index]:
            raise ValueError(
                "Route segment is too short for the requested bend footprint: "
                f"segment={index}, length={length:.6g}, required={requirements[index]:.6g}."
            )


def _transform_path_points(
    points: np.ndarray,
    *,
    origin: Coordinate,
    angle: float,
) -> np.ndarray:
    theta = radians(angle)
    rotation = np.array(
        [
            [cos(theta), -sin(theta)],
            [sin(theta), cos(theta)],
        ]
    )
    return points @ rotation.T + np.array(origin)


def _append_route_point(points: list[Coordinate], point: Coordinate) -> None:
    if not points or hypot(points[-1][0] - point[0], points[-1][1] - point[1]) > 1e-9:
        points.append(point)


def _bend_route_path(
    points: Sequence[Coordinate],
    *,
    bend_radius: float,
    bend_style: str,
    euler_angular_step: float,
) -> gf.Path:
    points = _simplify_collinear_points(_dedupe_consecutive_points(points))
    if len(points) < 2:
        raise ValueError("Route needs at least two points.")

    route_points: list[Coordinate] = [points[0]]
    for index in range(1, len(points) - 1):
        previous_point = points[index - 1]
        corner = points[index]
        next_point = points[index + 1]
        incoming = _unit_vector(previous_point, corner)
        outgoing = _unit_vector(corner, next_point)
        turn_angle = _signed_turn_angle(previous_point, corner, next_point)
        tangent = _bend_tangent_length(turn_angle, bend_radius, bend_style)
        entry = (
            corner[0] - incoming[0] * tangent,
            corner[1] - incoming[1] * tangent,
        )
        exit_ = (
            corner[0] + outgoing[0] * tangent,
            corner[1] + outgoing[1] * tangent,
        )
        _append_route_point(route_points, entry)

        bend_points = _bend_shape_points(
            radius=bend_radius,
            angle=turn_angle,
            bend_style=bend_style,
            angular_step=euler_angular_step,
        )

        incoming_angle = degrees(atan2(incoming[1], incoming[0]))
        transformed_points = _transform_path_points(
            bend_points,
            origin=entry,
            angle=incoming_angle,
        )
        transformed_points[-1] = np.array(exit_)
        for bend_point in transformed_points[1:]:
            _append_route_point(
                route_points,
                (float(bend_point[0]), float(bend_point[1])),
            )

    _append_route_point(route_points, points[-1])
    return gf.Path(route_points)


def _bend_route_component(
    points: Sequence[Coordinate],
    *,
    cross_section: CrossSectionSpec,
    bend_radius: float,
    bend_style: str,
    euler_angular_step: float,
    simplify: float | None,
) -> gf.Component:
    path = _bend_route_path(
        points,
        bend_radius=bend_radius,
        bend_style=bend_style,
        euler_angular_step=euler_angular_step,
    )
    component = path.extrude(cross_section=cross_section, simplify=simplify)
    component.flatten()
    return component


def _route_resource_region(
    path: gf.Path,
    *,
    resource_width: float,
) -> gf.Region:
    return _path_region(
        path.points,
        width=resource_width,
    )


def _path_region(
    points: Sequence[Coordinate] | np.ndarray,
    *,
    width: float,
) -> gf.Region:
    path_region_shape = _path_region_shape(
        points=points,
        width=width,
        layer=_PATH_REGION_LAYER,
    )
    return path_region_shape.get_region(_PATH_REGION_LAYER, merge=True)


def _add_debug_path_region(
    component: gf.Component,
    points: Sequence[Coordinate] | np.ndarray,
    *,
    layer: LayerSpec,
    width: float,
) -> None:
    path_region_debug = _path_region_shape(points=points, width=width, layer=layer)
    if not path_region_debug.get_region(layer, merge=True).is_empty():
        _ = component << path_region_debug


def _conflict_constraint_region(
    region: gf.Region,
    *,
    grid_resolution: float,
    route_clearance: float,
) -> gf.Region:
    bbox = region.bbox()
    dbu = gf.kcl.dbu
    padding = round(max(grid_resolution / 2, route_clearance / 2, 1.0) / dbu)
    left = bbox.left - padding
    right = bbox.right + padding
    bottom = bbox.bottom - padding
    top = bbox.top + padding

    conflict_box = gf.components.rectangle(
        size=((right - left) * dbu, (top - bottom) * dbu),
        centered=False,
        layer=_PATH_REGION_LAYER,
    )
    conflict = gf.Component()
    conflict_ref = conflict << conflict_box
    conflict_ref.dmove((left * dbu, bottom * dbu))
    return conflict.get_region(_PATH_REGION_LAYER, merge=True)


def _path_region_shape(
    points: Sequence[Coordinate] | np.ndarray,
    *,
    width: float,
    layer: LayerSpec,
) -> gf.Component:
    points_f = [(float(point[0]), float(point[1])) for point in points]
    if len(points_f) == 0:
        raise ValueError("points must contain at least one point.")

    footprint = gf.Component()
    for index in range(len(points_f) - 1):
        point1 = points_f[index]
        point2 = points_f[index + 1]
        if point1 == point2:
            continue

        segment = gf.Path([point1, point2]).extrude(
            width=width,
            layer=layer,
        )
        footprint << segment

    for point in points_f:
        corner = gf.components.rectangle(
            size=(width, width),
            centered=True,
            layer=layer,
        )
        corner_ref = footprint << corner
        corner_ref.dmove(point)

    return footprint


def _first_route_conflict(
    candidates: Sequence[_RouteCandidate8Dir],
) -> tuple[RouteConflict8Dir, gf.Region] | None:
    for index1, route1 in enumerate(candidates):
        for index2 in range(index1 + 1, len(candidates)):
            route2 = candidates[index2]
            conflict_region = (route1.resource_region & route2.resource_region).merged()
            if conflict_region.is_empty():
                continue

            bbox = _region_bbox_um(conflict_region)
            if bbox is None:
                continue
            return (
                RouteConflict8Dir(
                    route1_index=index1,
                    route2_index=index2,
                    route1_name=route1.pair.name,
                    route2_name=route2.pair.name,
                    bbox=bbox,
                ),
                conflict_region,
            )
    return None


def _closest_direction_index(vector: Coordinate) -> int:
    vx, vy = vector
    vector_length = hypot(vx, vy)
    if vector_length == 0:
        raise ValueError("Direction vector must not be zero.")

    vx /= vector_length
    vy /= vector_length
    return min(
        range(len(_DIRECTION_STEPS_8)),
        key=lambda index: (
            (_DIRECTION_STEPS_8[index][0] / hypot(*_DIRECTION_STEPS_8[index]) - vx) ** 2
            + (_DIRECTION_STEPS_8[index][1] / hypot(*_DIRECTION_STEPS_8[index]) - vy) ** 2
        ),
    )


def _turn_angle_45_steps(direction1: int, direction2: int) -> int:
    delta = abs(direction1 - direction2) % len(_DIRECTION_STEPS_8)
    return min(delta, len(_DIRECTION_STEPS_8) - delta)


def _route_length(points: Sequence[Coordinate]) -> float:
    return sum(
        hypot(point2[0] - point1[0], point2[1] - point1[1])
        for point1, point2 in zip(points, points[1:], strict=False)
    )


def _count_turns(points: Sequence[Coordinate]) -> int:
    turns = 0
    previous_direction: Coordinate | None = None
    for point1, point2 in zip(points, points[1:], strict=False):
        direction = (point2[0] - point1[0], point2[1] - point1[1])
        if direction == (0, 0):
            continue
        if previous_direction is not None:
            cross = previous_direction[0] * direction[1] - previous_direction[1] * direction[0]
            if abs(cross) > 1e-9:
                turns += 1
        previous_direction = direction
    return turns


def _simplify_collinear_points(points: Sequence[Coordinate]) -> list[Coordinate]:
    if len(points) <= 2:
        return list(points)

    simplified = [points[0]]
    for index in range(1, len(points) - 1):
        previous = simplified[-1]
        point = points[index]
        next_point = points[index + 1]
        vector1 = (point[0] - previous[0], point[1] - previous[1])
        vector2 = (next_point[0] - point[0], next_point[1] - point[1])
        cross = vector1[0] * vector2[1] - vector1[1] * vector2[0]
        if abs(cross) > 1e-9:
            simplified.append(point)

    simplified.append(points[-1])
    return simplified


def _snap_node(point: Coordinate, x0: float, y0: float, resolution: float) -> GridNode:
    return (
        round((point[0] - x0) / resolution),
        round((point[1] - y0) / resolution),
    )


def _node_to_point(node: GridNode, x0: float, y0: float, resolution: float) -> Coordinate:
    return (x0 + node[0] * resolution, y0 + node[1] * resolution)


def _region_bbox_um(region: gf.Region | None) -> RouteBbox | None:
    if region is None or region.is_empty():
        return None

    bbox = region.bbox()
    return (
        bbox.left * gf.kcl.dbu,
        bbox.bottom * gf.kcl.dbu,
        bbox.right * gf.kcl.dbu,
        bbox.top * gf.kcl.dbu,
    )


def _point_intersects_region_um(region: gf.Region | None, point: Coordinate) -> bool:
    if region is None or region.is_empty():
        return False

    # GF public APIs do not expose an arbitrary CBS-accurate point-in-region query.
    # Retain a narrow KLayout boundary probe at only this boundary; point
    # coordinates are converted from µm to active dbu before Region testing.
    x = round(point[0] / gf.kcl.dbu)
    y = round(point[1] / gf.kcl.dbu)
    point_box = gf.kdb.Box(x, y, x + 1, y + 1)
    return not (region & gf.Region(point_box)).is_empty()


def _segment_intersects_region_um(
    region: gf.Region | None,
    point1: Coordinate,
    point2: Coordinate,
    sample_step_um: float,
) -> bool:
    if region is None or region.is_empty():
        return False

    length = hypot(point2[0] - point1[0], point2[1] - point1[1])
    sample_count = max(1, ceil(length / sample_step_um))
    for index in range(sample_count + 1):
        t = index / sample_count
        point = (
            point1[0] + (point2[0] - point1[0]) * t,
            point1[1] + (point2[1] - point1[1]) * t,
        )
        if _point_intersects_region_um(region, point):
            return True

    return False


def _routing_bounds(
    port1: Port,
    port2: Port,
    keepout_region: gf.Region | None,
    route_bbox: RouteBbox | None,
    margin: float,
    resolution: float,
) -> RouteBbox:
    if route_bbox is not None:
        xmin, ymin, xmax, ymax = route_bbox
    else:
        xs = [port1.x, port2.x]
        ys = [port1.y, port2.y]
        keepout_bbox = _region_bbox_um(keepout_region)
        if keepout_bbox is not None:
            xs.extend([keepout_bbox[0], keepout_bbox[2]])
            ys.extend([keepout_bbox[1], keepout_bbox[3]])

        xmin = min(xs) - margin
        xmax = max(xs) + margin
        ymin = min(ys) - margin
        ymax = max(ys) + margin

    xmin = floor(xmin / resolution) * resolution
    ymin = floor(ymin / resolution) * resolution
    xmax = ceil(xmax / resolution) * resolution
    ymax = ceil(ymax / resolution) * resolution
    return xmin, ymin, xmax, ymax


def _nearest_valid_node(
    node: GridNode,
    node_is_valid: Any,
    max_i: int,
    max_j: int,
) -> GridNode:
    if node_is_valid(node):
        return node

    max_radius = max(max_i, max_j)
    for radius in range(1, max_radius + 1):
        for di in range(-radius, radius + 1):
            for dj in (-radius, radius):
                candidate = (node[0] + di, node[1] + dj)
                if node_is_valid(candidate):
                    return candidate
        for dj in range(-radius + 1, radius):
            for di in (-radius, radius):
                candidate = (node[0] + di, node[1] + dj)
                if node_is_valid(candidate):
                    return candidate

    raise RuntimeError("No valid routing node found inside route_bbox.")


def _astar_candidate_coordinates(
    port: Port,
    distance_from_node_to_port: float,
) -> list[tuple[float, float]]:
    if port.orientation in [0, 180]:
        x_offset = np.cos(port.orientation * np.pi / 180) * distance_from_node_to_port
        return [
            (port.x + x_offset, port.y),
            (port.x + x_offset, port.y + distance_from_node_to_port),
            (port.x + x_offset, port.y - distance_from_node_to_port),
        ]
    if port.orientation in [90, 270]:
        y_offset = np.sin(port.orientation * np.pi / 180) * distance_from_node_to_port
        return [
            (port.x, port.y + y_offset),
            (port.x + distance_from_node_to_port, port.y + y_offset),
            (port.x - distance_from_node_to_port, port.y + y_offset),
        ]

    raise ValueError("port orientation must be in [0, 90, 180, 270]")


def _route_backbone_points_um(route: Route) -> list[tuple[float, float]]:
    points = []
    for point in getattr(route, "backbone", []):
        if not hasattr(point, "x") or not hasattr(point, "y"):
            continue

        x = float(point.x)
        y = float(point.y)
        if abs(x) > 1e5 or abs(y) > 1e5:
            x *= gf.kcl.dbu
            y *= gf.kcl.dbu
        points.append((x, y))

    return points


def _route_port_overrun_um(route: Route, port: Port) -> float:
    points = _route_backbone_points_um(route)
    if not points:
        return 0.0

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]

    if port.orientation == 0:
        return max(0.0, port.x - min(xs))
    if port.orientation == 180:
        return max(0.0, max(xs) - port.x)
    if port.orientation == 90:
        return max(0.0, port.y - min(ys))
    if port.orientation == 270:
        return max(0.0, max(ys) - port.y)

    raise ValueError("port orientation must be in [0, 90, 180, 270]")


def route_astar_shortest(
    component: gf.Component,
    port1: Port,
    port2: Port,
    resolution: float = 1.0,
    avoid_layers: Sequence[LayerSpec] | None = None,
    distance: float = 8.0,
    cross_section: CrossSectionSpec = "strip",
    bend: ComponentSpec = "wire_corner",
    **kwargs: Any,
) -> Route:
    """Route with GF A* while minimizing port overrun before bend count.

    Use when the stock GF A* route can choose several start/end grid nodes and
    the layout should prefer the physically shortest port connection.

    Example:
        route = route_astar_shortest(c, port1, port2, avoid_layers=[draw_layer])
    """

    cross_section = gf.get_cross_section(cross_section, **kwargs)
    grid, x, y = _generate_grid(component, resolution, avoid_layers, distance)
    graph_ = nx.grid_2d_graph(len(x), len(y))
    graph = cast(nx.Graph, graph_)

    for i in range(len(x)):
        for j in range(len(y)):
            if grid[i, j] == 1:
                graph.remove_node((i, j))

    distance_from_node_to_port = 3 * (cross_section.radius or 3)
    start_node_coordinates = _astar_candidate_coordinates(port1, distance_from_node_to_port)
    end_node_coordinates = _astar_candidate_coordinates(port2, distance_from_node_to_port)

    candidates: list[tuple[float, int, float, tuple[float, float], tuple[float, float]]] = []
    for start_coords in start_node_coordinates:
        for end_coords in end_node_coordinates:
            try:
                temp = component.copy()
                route = route_astar_single(
                    component=temp,
                    port1=port1,
                    port2=port2,
                    start_node=(
                        round((start_coords[0] - x.min()) / resolution),
                        round((start_coords[1] - y.min()) / resolution),
                    ),
                    end_node=(
                        round((end_coords[0] - x.min()) / resolution),
                        round((end_coords[1] - y.min()) / resolution),
                    ),
                    resolution=resolution,
                    cross_section=cross_section,
                    bend=bend,
                    G=graph,
                    x=x,
                    y=y,
                    **kwargs,
                )
                overrun = _route_port_overrun_um(route, port1) + _route_port_overrun_um(
                    route, port2
                )
                candidates.append(
                    (
                        overrun,
                        get_route_bend_count(route),
                        float(getattr(route, "length", 0.0)),
                        start_coords,
                        end_coords,
                    )
                )
            except Exception:
                continue

    if not candidates:
        raise RuntimeError("All A* routing attempts failed.")

    _, _, _, optimized_start_coords, optimized_end_coords = min(
        candidates,
        key=lambda item: (item[0], item[1], item[2]),
    )

    return route_astar_single(
        component=component,
        port1=port1,
        port2=port2,
        start_node=(
            round((optimized_start_coords[0] - x.min()) / resolution),
            round((optimized_start_coords[1] - y.min()) / resolution),
        ),
        end_node=(
            round((optimized_end_coords[0] - x.min()) / resolution),
            round((optimized_end_coords[1] - y.min()) / resolution),
        ),
        resolution=resolution,
        cross_section=cross_section,
        bend=bend,
        G=graph,
        x=x,
        y=y,
        **kwargs,
    )


def plan_route_8dir(
    port1: Port,
    port2: Port,
    keepout_region: gf.Region | None = None,
    route_bbox: RouteBbox | None = None,
    grid_resolution: float = 100.0,
    bbox_margin: float = 500.0,
    bend_penalty: float = 250.0,
    min_straight_between_turns: float = 0.0,
    initial_straight_length: float = 0.0,
    final_straight_length: float = 0.0,
    bend_radius: float | None = None,
    bend_style: str = "euler",
    bend_margin: float = 0.0,
    match_port_orientations: bool = True,
    edge_sample_step_um: float | None = None,
    simplify: bool = True,
) -> EightDirectionRoutePlan:
    """Plan a bend-aware centerline with 8-direction A* around keepouts.

    Use when a route should allow Manhattan and diagonal segments while honoring
    port orientation, bend footprint, and Region obstacles before geometry is
    rendered.

    Example:
        plan = plan_route_8dir(port1, port2, keepout_region=keepout, bend_radius=100.0)
    """

    if grid_resolution <= 0:
        raise ValueError(f"grid_resolution must be positive, got {grid_resolution!r}.")
    if bbox_margin < 0:
        raise ValueError(f"bbox_margin must be non-negative, got {bbox_margin!r}.")
    if min_straight_between_turns < 0:
        raise ValueError(
            f"min_straight_between_turns must be non-negative, got {min_straight_between_turns!r}."
        )
    if initial_straight_length < 0:
        raise ValueError(
            f"initial_straight_length must be non-negative, got {initial_straight_length!r}."
        )
    if final_straight_length < 0:
        raise ValueError(
            f"final_straight_length must be non-negative, got {final_straight_length!r}."
        )
    if bend_radius is not None and bend_radius <= 0:
        raise ValueError(f"bend_radius must be positive, got {bend_radius!r}.")
    if bend_style not in {"circular", "euler"}:
        raise ValueError(f"bend_style must be 'circular' or 'euler', got {bend_style!r}.")
    if bend_margin < 0:
        raise ValueError(f"bend_margin must be non-negative, got {bend_margin!r}.")

    edge_sample_step_um = edge_sample_step_um or grid_resolution / 2
    xmin, ymin, xmax, ymax = _routing_bounds(
        port1=port1,
        port2=port2,
        keepout_region=keepout_region,
        route_bbox=route_bbox,
        margin=bbox_margin,
        resolution=grid_resolution,
    )
    max_i = round((xmax - xmin) / grid_resolution)
    max_j = round((ymax - ymin) / grid_resolution)

    def in_bounds(node: GridNode) -> bool:
        return 0 <= node[0] <= max_i and 0 <= node[1] <= max_j

    def node_is_valid(node: GridNode) -> bool:
        return in_bounds(node) and not _point_intersects_region_um(
            keepout_region,
            _node_to_point(node, xmin, ymin, grid_resolution),
        )

    start_node = _nearest_valid_node(
        _snap_node(port1.center, xmin, ymin, grid_resolution),
        node_is_valid=node_is_valid,
        max_i=max_i,
        max_j=max_j,
    )
    end_node = _nearest_valid_node(
        _snap_node(port2.center, xmin, ymin, grid_resolution),
        node_is_valid=node_is_valid,
        max_i=max_i,
        max_j=max_j,
    )

    start_direction = _closest_direction_index(_orientation_vector(port1.orientation))
    end_direction = _closest_direction_index(_orientation_vector(port2.orientation + 180))

    def turn_tangent(direction1: int, direction2: int) -> float:
        if bend_radius is None:
            return 0.0
        return _bend_tangent_length(
            _turn_angle_degrees(direction1, direction2),
            bend_radius,
            bend_style,
        )

    max_turn_tangent = (
        _bend_tangent_length(135.0, bend_radius, bend_style) if bend_radius is not None else 0.0
    )
    distance_cap = max(
        min_straight_between_turns,
        2 * max_turn_tangent + bend_margin,
        initial_straight_length,
        final_straight_length,
    )

    def distance_key(distance: float) -> float:
        if distance_cap == 0:
            return 0.0
        return round(min(distance, distance_cap), 6)

    def tangent_key(tangent: float) -> float:
        return round(tangent, 6)

    frontier: list[tuple[float, float, int, GridNode, int, float, float]] = []
    sequence = count()
    start_distance = distance_key(initial_straight_length)
    start_exit_tangent = tangent_key(0.0)
    start_state = (start_node, start_direction, start_distance, start_exit_tangent)
    best_cost: dict[tuple[GridNode, int, float, float], float] = {start_state: 0.0}
    came_from: dict[
        tuple[GridNode, int, float, float],
        tuple[GridNode, int, float, float] | None,
    ] = {start_state: None}

    def heuristic(node: GridNode) -> float:
        point = _node_to_point(node, xmin, ymin, grid_resolution)
        target = _node_to_point(end_node, xmin, ymin, grid_resolution)
        return hypot(target[0] - point[0], target[1] - point[1])

    heappush(
        frontier,
        (
            heuristic(start_node),
            0.0,
            next(sequence),
            start_node,
            start_direction,
            start_distance,
            start_exit_tangent,
        ),
    )
    final_state: tuple[GridNode, int, float, float] | None = None
    visited_nodes = 0

    while frontier:
        _, cost, _, node, previous_direction, straight_distance, previous_exit_tangent = heappop(
            frontier
        )
        state = (node, previous_direction, straight_distance, previous_exit_tangent)
        if cost != best_cost.get(state):
            continue

        visited_nodes += 1
        if node == end_node:
            if match_port_orientations and previous_direction != end_direction:
                continue
            required_final_straight = previous_exit_tangent + bend_margin
            if previous_exit_tangent > 0:
                required_final_straight = max(
                    required_final_straight,
                    min_straight_between_turns,
                )
            if straight_distance + final_straight_length < required_final_straight:
                continue
            final_state = state
            break

        current_point = _node_to_point(node, xmin, ymin, grid_resolution)
        for direction_index, direction in enumerate(_DIRECTION_STEPS_8):
            next_node = (node[0] + direction[0], node[1] + direction[1])
            if not node_is_valid(next_node):
                continue

            next_point = _node_to_point(next_node, xmin, ymin, grid_resolution)
            if _segment_intersects_region_um(
                keepout_region,
                current_point,
                next_point,
                edge_sample_step_um,
            ):
                continue

            step_length = grid_resolution * hypot(direction[0], direction[1])
            turn_steps = _turn_angle_45_steps(previous_direction, direction_index)
            if turn_steps >= len(_DIRECTION_STEPS_8) // 2:
                continue
            if turn_steps:
                entry_tangent = turn_tangent(previous_direction, direction_index)
                required_straight = max(
                    min_straight_between_turns,
                    previous_exit_tangent + entry_tangent + bend_margin,
                )
                if straight_distance < required_straight:
                    continue
                next_exit_tangent = tangent_key(entry_tangent)
            else:
                next_exit_tangent = previous_exit_tangent
            next_straight_distance = distance_key(
                step_length if turn_steps else straight_distance + step_length
            )
            candidate_cost = cost + step_length + bend_penalty * turn_steps

            next_state = (
                next_node,
                direction_index,
                next_straight_distance,
                next_exit_tangent,
            )
            if candidate_cost < best_cost.get(next_state, float("inf")):
                best_cost[next_state] = candidate_cost
                came_from[next_state] = state
                priority = candidate_cost + heuristic(next_node)
                heappush(
                    frontier,
                    (
                        priority,
                        candidate_cost,
                        next(sequence),
                        next_node,
                        direction_index,
                        next_straight_distance,
                        next_exit_tangent,
                    ),
                )

    if final_state is None:
        raise RuntimeError("8-direction A* could not find a valid path.")

    states = []
    state: tuple[GridNode, int, float, float] | None = final_state
    while state is not None:
        states.append(state)
        state = came_from[state]
    states.reverse()

    points = [_node_to_point(state[0], xmin, ymin, grid_resolution) for state in states]
    points[0] = port1.center
    points[-1] = port2.center
    if simplify:
        points = _simplify_collinear_points(points)

    return EightDirectionRoutePlan(
        points=points,
        length=_route_length(points),
        cost=best_cost[final_state],
        turns=_count_turns(points),
        grid_resolution=grid_resolution,
        visited_nodes=visited_nodes,
    )


def _plan_route_candidate_8dir(
    pair: RoutePair8Dir,
    *,
    keepout_region: gf.Region | None,
    route_bbox: RouteBbox | None,
    grid_resolution: float,
    cross_section: CrossSectionSpec,
    bbox_margin: float,
    bend_penalty: float,
    bend_radius: float | None,
    start_straight_length: float | None,
    end_straight_length: float | None,
    min_straight_between_turns: float | None,
    bend_margin: float,
    bend_style: str,
    euler_angular_step: float,
    simplify: float | None,
    route_clearance: float,
) -> _RouteCandidate8Dir:
    xs = gf.get_cross_section(pair.cross_section or cross_section)

    resolved_bend_radius = pair.bend_radius
    if resolved_bend_radius is None:
        resolved_bend_radius = bend_radius
    if resolved_bend_radius is None:
        resolved_bend_radius = float(xs.radius or grid_resolution)
    if resolved_bend_radius <= 0:
        raise ValueError(f"bend_radius must be positive, got {resolved_bend_radius!r}.")

    resolved_bend_margin = pair.bend_margin if pair.bend_margin is not None else bend_margin
    if resolved_bend_margin < 0:
        raise ValueError(f"bend_margin must be non-negative, got {resolved_bend_margin!r}.")

    resolved_bend_style = pair.bend_style or bend_style
    if resolved_bend_style not in {"circular", "euler"}:
        raise ValueError(f"bend_style must be 'circular' or 'euler', got {resolved_bend_style!r}.")

    resolved_euler_angular_step = pair.euler_angular_step or euler_angular_step
    if resolved_euler_angular_step <= 0:
        raise ValueError(
            f"euler_angular_step must be positive, got {resolved_euler_angular_step!r}."
        )

    resolved_turn_spacing = _resolve_min_straight_between_turns(
        pair.min_straight_between_turns
        if pair.min_straight_between_turns is not None
        else min_straight_between_turns
    )
    resolved_start_length = _resolve_route_straight_length(
        pair.start_straight_length
        if pair.start_straight_length is not None
        else start_straight_length,
        bend_radius=resolved_bend_radius,
        grid_resolution=grid_resolution,
        name="start_straight_length",
    )
    resolved_end_length = _resolve_route_straight_length(
        pair.end_straight_length if pair.end_straight_length is not None else end_straight_length,
        bend_radius=resolved_bend_radius,
        grid_resolution=grid_resolution,
        name="end_straight_length",
    )

    edge_sample_step_um = grid_resolution / 2
    start_lead = _point_along_orientation(
        pair.port1.center,
        pair.port1.orientation,
        resolved_start_length,
    )
    end_lead = _point_along_orientation(
        pair.port2.center,
        pair.port2.orientation,
        resolved_end_length,
    )
    if _segment_intersects_region_um(
        keepout_region,
        pair.port1.center,
        start_lead,
        edge_sample_step_um,
    ):
        raise ValueError(
            f"Start route tangent segment for {pair.name!r} intersects the keepout region."
        )
    if _segment_intersects_region_um(
        keepout_region,
        pair.port2.center,
        end_lead,
        edge_sample_step_um,
    ):
        raise ValueError(
            f"End route tangent segment for {pair.name!r} intersects the keepout region."
        )

    plan_port1 = _port_with_center(pair.port1, start_lead)
    plan_port2 = _port_with_center(pair.port2, end_lead)
    plan = plan_route_8dir(
        port1=plan_port1,
        port2=plan_port2,
        keepout_region=keepout_region,
        route_bbox=route_bbox,
        grid_resolution=grid_resolution,
        bbox_margin=bbox_margin,
        bend_penalty=bend_penalty,
        min_straight_between_turns=resolved_turn_spacing,
        initial_straight_length=resolved_start_length,
        final_straight_length=resolved_end_length,
        bend_radius=resolved_bend_radius,
        bend_style=resolved_bend_style,
        bend_margin=resolved_bend_margin,
        match_port_orientations=True,
    )
    route_points = _dedupe_consecutive_points([pair.port1.center, *plan.points, pair.port2.center])
    route_plan = EightDirectionRoutePlan(
        points=route_points,
        length=_route_length(route_points),
        cost=plan.cost,
        turns=_count_turns(route_points),
        grid_resolution=plan.grid_resolution,
        visited_nodes=plan.visited_nodes,
    )
    _validate_route_bend_footprint(
        route_plan.points,
        bend_radius=resolved_bend_radius,
        bend_style=resolved_bend_style,
        min_straight_between_turns=resolved_turn_spacing,
        bend_margin=resolved_bend_margin,
    )
    route_path = _bend_route_path(
        route_plan.points,
        bend_radius=resolved_bend_radius,
        bend_style=resolved_bend_style,
        euler_angular_step=resolved_euler_angular_step,
    )

    route_simplify = pair.simplify if pair.simplify is not None else simplify
    route_length = float(route_path.length())

    resource_region = _route_resource_region(
        route_path,
        resource_width=_cross_section_footprint_width(xs) + route_clearance,
    )

    return _RouteCandidate8Dir(
        pair=pair,
        plan=route_plan,
        path=route_path,
        cross_section=xs,
        simplify=route_simplify,
        resource_region=resource_region,
        resource_width=_cross_section_footprint_width(xs) + route_clearance,
        length=route_length,
        cost=route_plan.cost,
        start_straight_length=resolved_start_length,
        end_straight_length=resolved_end_length,
        min_straight_between_turns=resolved_turn_spacing,
        bend_style=resolved_bend_style,
    )


def route_bundle_8dir(
    component: gf.Component,
    ports1: Port | Sequence[Port],
    ports2: Port | Sequence[Port],
    keepout_region: gf.Region | None = None,
    route_bbox: RouteBbox | None = None,
    grid_resolution: float = 100.0,
    cross_section: CrossSectionSpec = "strip",
    bbox_margin: float = 500.0,
    bend_penalty: float = 250.0,
    bend_radius: float | None = None,
    start_straight_length: float | None = None,
    end_straight_length: float | None = None,
    min_straight_between_turns: float | None = None,
    bend_margin: float = 0.0,
    bend_style: str = "euler",
    euler_angular_step: float = 4.0,
    simplify: float | None = None,
    debug_plan_layer: LayerSpec | None = None,
    debug_path_layer: LayerSpec | None = None,
    debug_path_width: float = 3.0,
) -> tuple[list[EightDirectionRoute], list[EightDirectionRoutePlan]]:
    """Route port pairs with 8-direction A* and CrossSection extrusion.

    Use when chip code needs rendered CPW geometry from bend-aware centerline
    plans and should avoid automatic jog insertion from generic all-angle
    bundle routing.

    Example:
        routes, plans = route_bundle_8dir(c, ports1=[p1], ports2=[p2],
                                          cross_section="cpw_6_7_6")
    """

    ports1_list = _as_port_list(ports1)
    ports2_list = _as_port_list(ports2)
    if len(ports1_list) != len(ports2_list):
        raise ValueError(
            f"ports1 and ports2 must have the same length, got {len(ports1_list)} "
            f"and {len(ports2_list)}."
        )

    xs = gf.get_cross_section(cross_section)
    if bend_radius is None:
        bend_radius = float(xs.radius or grid_resolution)
    if bend_radius <= 0:
        raise ValueError(f"bend_radius must be positive, got {bend_radius!r}.")
    if bend_margin < 0:
        raise ValueError(f"bend_margin must be non-negative, got {bend_margin!r}.")
    if debug_path_width <= 0:
        raise ValueError(f"debug_path_width must be positive, got {debug_path_width!r}.")
    if euler_angular_step <= 0:
        raise ValueError(f"euler_angular_step must be positive, got {euler_angular_step!r}.")

    turn_spacing = _resolve_min_straight_between_turns(
        min_straight_between_turns,
    )
    start_length = _resolve_route_straight_length(
        start_straight_length,
        bend_radius=bend_radius,
        grid_resolution=grid_resolution,
        name="start_straight_length",
    )
    end_length = _resolve_route_straight_length(
        end_straight_length,
        bend_radius=bend_radius,
        grid_resolution=grid_resolution,
        name="end_straight_length",
    )

    routes: list[EightDirectionRoute] = []
    plans: list[EightDirectionRoutePlan] = []
    for port1, port2 in zip(ports1_list, ports2_list, strict=True):
        edge_sample_step_um = grid_resolution / 2
        start_lead = _point_along_orientation(
            port1.center,
            port1.orientation,
            start_length,
        )
        end_lead = _point_along_orientation(
            port2.center,
            port2.orientation,
            end_length,
        )
        if _segment_intersects_region_um(
            keepout_region,
            port1.center,
            start_lead,
            edge_sample_step_um,
        ):
            raise ValueError("Start route tangent segment intersects the keepout region.")
        if _segment_intersects_region_um(
            keepout_region,
            port2.center,
            end_lead,
            edge_sample_step_um,
        ):
            raise ValueError("End route tangent segment intersects the keepout region.")

        plan_port1 = _port_with_center(port1, start_lead)
        plan_port2 = _port_with_center(port2, end_lead)

        plan = plan_route_8dir(
            port1=plan_port1,
            port2=plan_port2,
            keepout_region=keepout_region,
            route_bbox=route_bbox,
            grid_resolution=grid_resolution,
            bbox_margin=bbox_margin,
            bend_penalty=bend_penalty,
            min_straight_between_turns=turn_spacing,
            initial_straight_length=start_length,
            final_straight_length=end_length,
            bend_radius=bend_radius,
            bend_style=bend_style,
            bend_margin=bend_margin,
            match_port_orientations=True,
        )
        route_points = _dedupe_consecutive_points([port1.center, *plan.points, port2.center])
        route_plan = EightDirectionRoutePlan(
            points=route_points,
            length=_route_length(route_points),
            cost=plan.cost,
            turns=_count_turns(route_points),
            grid_resolution=plan.grid_resolution,
            visited_nodes=plan.visited_nodes,
        )
        _validate_route_bend_footprint(
            route_plan.points,
            bend_radius=bend_radius,
            bend_style=bend_style,
            min_straight_between_turns=turn_spacing,
            bend_margin=bend_margin,
        )
        route_path = _bend_route_path(
            route_plan.points,
            bend_radius=bend_radius,
            bend_style=bend_style,
            euler_angular_step=euler_angular_step,
        )
        if debug_plan_layer is not None:
            _add_debug_path_region(
                component,
                route_plan.points,
                layer=debug_plan_layer,
                width=debug_path_width,
            )
        if debug_path_layer is not None:
            _add_debug_path_region(
                component,
                route_path.points,
                layer=debug_path_layer,
                width=debug_path_width,
            )
        route_component = route_path.extrude(cross_section=xs, simplify=simplify)
        route_component.flatten()
        route_ref = component << route_component
        route_length = float(route_component.info.get("length", route_plan.length))
        routes.append(
            EightDirectionRoute(
                reference=route_ref,
                component=route_component,
                plan=route_plan,
                length=route_length,
                start_straight_length=start_length,
                end_straight_length=end_length,
                min_straight_between_turns=turn_spacing,
                bend_style=bend_style,
            )
        )
        plans.append(route_plan)

    return routes, plans


def route_bundle_8dir_global(
    component: gf.Component,
    route_pairs: Sequence[RoutePair8Dir] | None = None,
    ports1: Port | Sequence[Port] | None = None,
    ports2: Port | Sequence[Port] | None = None,
    keepout_region: gf.Region | None = None,
    route_bbox: RouteBbox | None = None,
    grid_resolution: float = 100.0,
    cross_section: CrossSectionSpec = "strip",
    bbox_margin: float = 500.0,
    bend_penalty: float = 250.0,
    bend_radius: float | None = None,
    start_straight_length: float | None = None,
    end_straight_length: float | None = None,
    min_straight_between_turns: float | None = None,
    bend_margin: float = 0.0,
    bend_style: str = "euler",
    euler_angular_step: float = 4.0,
    simplify: float | None = None,
    route_clearance: float = 0.0,
    max_search_nodes: int = 256,
    conflict_scope: str = "route",
    debug_plan_layer: LayerSpec | None = None,
    debug_path_layer: LayerSpec | None = None,
    debug_path_width: float = 3.0,
) -> GlobalEightDirectionRouteBundle:
    """Route multiple nets with CBS-like global conflict search.

    Use when independent 8-direction routes overlap and the bundle needs a
    reusable high-level search that adds physical route-resource constraints
    until a conflict-free set is found.

    Example:
        bundle = route_bundle_8dir_global(c, route_pairs=pairs, route_clearance=10.0)
    """

    if grid_resolution <= 0:
        raise ValueError(f"grid_resolution must be positive, got {grid_resolution!r}.")
    if route_clearance < 0:
        raise ValueError(f"route_clearance must be non-negative, got {route_clearance!r}.")
    if max_search_nodes <= 0:
        raise ValueError(f"max_search_nodes must be positive, got {max_search_nodes!r}.")
    if conflict_scope not in {"route", "local"}:
        raise ValueError(f"conflict_scope must be 'route' or 'local', got {conflict_scope!r}.")
    if debug_path_width <= 0:
        raise ValueError(f"debug_path_width must be positive, got {debug_path_width!r}.")

    pairs = _normalize_route_pairs(
        route_pairs=route_pairs,
        ports1=ports1,
        ports2=ports2,
        cross_section=cross_section,
    )

    def plan_candidate(
        pair_index: int,
        constraints: Sequence[gf.Region],
    ) -> _RouteCandidate8Dir:
        route_keepout_region = _merged_region(keepout_region, constraints)
        return _plan_route_candidate_8dir(
            pairs[pair_index],
            keepout_region=route_keepout_region,
            route_bbox=route_bbox,
            grid_resolution=grid_resolution,
            cross_section=cross_section,
            bbox_margin=bbox_margin,
            bend_penalty=bend_penalty,
            bend_radius=bend_radius,
            start_straight_length=start_straight_length,
            end_straight_length=end_straight_length,
            min_straight_between_turns=min_straight_between_turns,
            bend_margin=bend_margin,
            bend_style=bend_style,
            euler_angular_step=euler_angular_step,
            simplify=simplify,
            route_clearance=route_clearance,
        )

    empty_constraints: tuple[tuple[gf.Region, ...], ...] = tuple(() for _ in pairs)
    empty_constraint_keys: tuple[tuple[tuple[int, int, int, int], ...], ...] = tuple(
        () for _ in pairs
    )
    candidates = tuple(
        plan_candidate(index, empty_constraints[index]) for index in range(len(pairs))
    )
    root = _GlobalSearchNode8Dir(
        constraints=empty_constraints,
        constraint_keys=empty_constraint_keys,
        candidates=candidates,
        cost=sum(candidate.cost for candidate in candidates),
        length=sum(candidate.length for candidate in candidates),
        conflicts_resolved=0,
    )

    frontier: list[tuple[float, float, int, _GlobalSearchNode8Dir]] = []
    sequence = count()
    heappush(frontier, (root.cost, root.length, next(sequence), root))
    seen = {root.constraint_keys}
    search_nodes = 0
    last_conflict: RouteConflict8Dir | None = None

    while frontier and search_nodes < max_search_nodes:
        _, _, _, node = heappop(frontier)
        search_nodes += 1

        conflict = _first_route_conflict(node.candidates)
        if conflict is None:
            routes: list[EightDirectionRoute] = []
            plans: list[EightDirectionRoutePlan] = []
            for candidate in node.candidates:
                if debug_plan_layer is not None:
                    _add_debug_path_region(
                        component,
                        candidate.plan.points,
                        layer=debug_plan_layer,
                        width=debug_path_width,
                    )
                if debug_path_layer is not None:
                    _add_debug_path_region(
                        component,
                        candidate.path.points,
                        layer=debug_path_layer,
                        width=debug_path_width,
                    )

                route_component = candidate.path.extrude(
                    cross_section=candidate.cross_section,
                    simplify=candidate.simplify,
                )
                route_component.flatten()
                route_ref = component << route_component
                routes.append(
                    EightDirectionRoute(
                        reference=route_ref,
                        component=route_component,
                        plan=candidate.plan,
                        length=candidate.length,
                        start_straight_length=candidate.start_straight_length,
                        end_straight_length=candidate.end_straight_length,
                        min_straight_between_turns=candidate.min_straight_between_turns,
                        bend_style=candidate.bend_style,
                    )
                )
                plans.append(candidate.plan)

            return GlobalEightDirectionRouteBundle(
                routes=routes,
                plans=plans,
                route_pairs=pairs,
                total_length=node.length,
                total_cost=node.cost,
                search_nodes=search_nodes,
                conflicts_resolved=node.conflicts_resolved,
                is_optimal=conflict_scope == "local" or len(pairs) == 1,
                last_conflict=None,
            )

        last_conflict, conflict_region = conflict
        for route_index in (last_conflict.route1_index, last_conflict.route2_index):
            other_route_index = (
                last_conflict.route2_index
                if route_index == last_conflict.route1_index
                else last_conflict.route1_index
            )
            if conflict_scope == "route":
                centerline_padding = round(
                    node.candidates[route_index].resource_width / 2 / gf.kcl.dbu
                )
                constraint_region = node.candidates[other_route_index].resource_region.sized(
                    centerline_padding
                )
            else:
                constraint_region = _conflict_constraint_region(
                    conflict_region,
                    grid_resolution=grid_resolution,
                    route_clearance=route_clearance,
                )
            constraint_key = _region_bbox_key(constraint_region)
            if constraint_key in node.constraint_keys[route_index]:
                continue

            next_constraints = [list(route_constraints) for route_constraints in node.constraints]
            next_constraint_keys = [
                list(route_constraint_keys) for route_constraint_keys in node.constraint_keys
            ]
            next_constraints[route_index].append(constraint_region)
            next_constraint_keys[route_index].append(constraint_key)

            next_constraints_tuple = tuple(
                tuple(route_constraints) for route_constraints in next_constraints
            )
            next_constraint_keys_tuple = tuple(
                tuple(route_constraint_keys) for route_constraint_keys in next_constraint_keys
            )
            if next_constraint_keys_tuple in seen:
                continue
            seen.add(next_constraint_keys_tuple)

            try:
                next_candidate = plan_candidate(
                    route_index,
                    next_constraints_tuple[route_index],
                )
            except (RuntimeError, ValueError):
                continue

            next_candidates = list(node.candidates)
            next_candidates[route_index] = next_candidate
            next_candidates_tuple = tuple(next_candidates)
            next_node = _GlobalSearchNode8Dir(
                constraints=next_constraints_tuple,
                constraint_keys=next_constraint_keys_tuple,
                candidates=next_candidates_tuple,
                cost=sum(candidate.cost for candidate in next_candidates_tuple),
                length=sum(candidate.length for candidate in next_candidates_tuple),
                conflicts_resolved=node.conflicts_resolved + 1,
            )
            heappush(
                frontier,
                (
                    next_node.cost,
                    next_node.length,
                    next(sequence),
                    next_node,
                ),
            )

    if last_conflict is None:
        raise RuntimeError("Global 8-direction router could not initialize a route bundle.")

    raise RuntimeError(
        "Global 8-direction router exhausted max_search_nodes="
        f"{max_search_nodes} before finding a conflict-free bundle. "
        f"Last conflict: {last_conflict.route1_name!r} with "
        f"{last_conflict.route2_name!r} at bbox={last_conflict.bbox!r}."
    )


def route_8dir_all_angle(
    component: gf.Component,
    port1: Port,
    port2: Port,
    keepout_region: gf.Region | None = None,
    route_bbox: RouteBbox | None = None,
    grid_resolution: float = 100.0,
    cross_section: CrossSectionSpec | None = None,
    bbox_margin: float = 500.0,
    bend_penalty: float = 250.0,
    separation: float = 3.0,
    terminal_straight_length: float | None = None,
    min_straight_between_turns: float | None = None,
    bend_margin: float = 0.0,
    bend_style: str = "euler",
    debug_plan_layer: LayerSpec | None = None,
    debug_path_layer: LayerSpec | None = None,
    debug_path_width: float = 3.0,
) -> tuple[list[EightDirectionRoute], EightDirectionRoutePlan]:
    """Route one all-angle-style pair through the 8-direction bundle backend.

    Use when older caller code expects a one-pair helper but the project should
    still use the same bend-aware 8-direction route implementation.

    Example:
        routes, plan = route_8dir_all_angle(c, port1, port2, cross_section="cpw_6_7_6")
    """

    _ = separation
    routes, plans = route_bundle_8dir(
        component=component,
        ports1=[port1],
        ports2=[port2],
        keepout_region=keepout_region,
        route_bbox=route_bbox,
        grid_resolution=grid_resolution,
        cross_section=cross_section or "strip",
        bbox_margin=bbox_margin,
        bend_penalty=bend_penalty,
        start_straight_length=terminal_straight_length,
        end_straight_length=terminal_straight_length,
        min_straight_between_turns=min_straight_between_turns,
        bend_margin=bend_margin,
        bend_style=bend_style,
        debug_plan_layer=debug_plan_layer,
        debug_path_layer=debug_path_layer,
        debug_path_width=debug_path_width,
    )
    return routes, plans[0]


__all__ = [
    "EightDirectionRoute",
    "EightDirectionRoutePlan",
    "GlobalEightDirectionRouteBundle",
    "RouteConflict8Dir",
    "RoutePair8Dir",
    "plan_route_8dir",
    "route_bundle_8dir",
    "route_bundle_8dir_global",
    "route_8dir_all_angle",
    "route_astar_shortest",
]
