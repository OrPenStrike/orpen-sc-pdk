"""Public Purcell-filter cells."""

from __future__ import annotations

from math import isfinite

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec, Layer

from orpen_sc_pdk.tech import LAYER, route_bundle_cpw


def _opposite_orientation(orientation: float) -> float:
    orientation = float(orientation % 360)
    if orientation not in {0.0, 90.0, 180.0, 270.0}:
        raise ValueError(
            "Anchor and MTL orientations must be cardinal and one of {0, 90, 180, 270}. "
            f"Got {orientation!r}."
        )
    return float((orientation + 180) % 360)


def _is_grid_aligned(value: float, dbu: float, *, name: str) -> None:
    if abs((value / dbu) - round(value / dbu)) > 1e-9:
        raise ValueError(
            f"{name} must be aligned to the active manufacturing grid {dbu} um, got {value!r}."
        )


def _coerce_anchor(
    name: str,
    anchor: tuple[float, float, float],
    *,
    dbu: float,
) -> tuple[float, float, float]:
    if not isinstance(anchor, tuple) or len(anchor) != 3:
        raise ValueError(f"{name} must be a 3-tuple (x, y, orientation), got {anchor!r}.")
    try:
        x, y, orientation = float(anchor[0]), float(anchor[1]), float(anchor[2])
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name} must contain numeric values, got {anchor!r}.") from e
    if not all(isfinite(value) for value in (x, y, orientation)):
        raise ValueError(f"{name} must contain finite values, got {anchor!r}.")
    _is_grid_aligned(x, dbu, name=f"{name}[0]")
    _is_grid_aligned(y, dbu, name=f"{name}[1]")
    orientation = float(orientation % 360)
    _opposite_orientation(orientation)
    return (x, y, orientation)


def _coerce_waypoints(
    name: str,
    waypoints: tuple[tuple[float, float], ...],
    *,
    dbu: float,
) -> tuple[tuple[float, float], ...]:
    if not isinstance(waypoints, tuple) or not waypoints:
        raise ValueError(f"{name} must be a non-empty tuple of (x, y) points.")
    coerced: list[tuple[float, float]] = []
    for point in waypoints:
        if not isinstance(point, tuple) or len(point) != 2:
            raise ValueError(f"{name} must contain 2-tuples, got {point!r}.")
        try:
            x, y = float(point[0]), float(point[1])
        except (TypeError, ValueError) as e:
            raise ValueError(f"{name} points must be numeric, got {point!r}.") from e
        if not all(isfinite(value) for value in (x, y)):
            raise ValueError(f"{name} points must be finite, got {point!r}.")
        _is_grid_aligned(x, dbu, name=f"{name} x")
        _is_grid_aligned(y, dbu, name=f"{name} y")
        coerced.append((x, y))
    return tuple(coerced)


def _to_port(
    name: str,
    anchor: tuple[float, float],
    orientation: float,
    width: float,
    layer: Layer,
) -> gf.Port:
    x, y = anchor
    return gf.Port(
        name=name,
        center=(x, y),
        width=width,
        orientation=int(orientation),
        layer=layer,
        port_type="optical",
    )


def _route_once(
    component: gf.Component,
    start_port: gf.Port,
    end_port: gf.Port,
    waypoints: tuple[tuple[float, float], ...],
    route_cross_section: CrossSectionSpec,
    cpw_radius: float,
) -> object:
    routes = route_bundle_cpw(
        component=component,
        ports1=[start_port],
        ports2=[end_port],
        waypoints=waypoints,
        cross_section=route_cross_section,
        radius=cpw_radius,
        auto_taper=False,
        raise_on_error=True,
        on_collision="error",
        on_placer_error="error",
    )
    if not routes:
        raise ValueError("route_bundle_cpw returned no routes.")
    if len(routes) != 1:
        raise ValueError("route_bundle_cpw returned more than one route for a single-link route.")
    return routes[0]


def _route_length_um(route: object, dbu: float) -> float:
    return float(route.length) * dbu


def _extract_backbone(route: object, dbu: float) -> list[tuple[float, float]]:
    return [(float(point.x) * dbu, float(point.y) * dbu) for point in route.backbone]


def _pick_axis_aligned_candidate(
    waypoints: tuple[tuple[float, float], ...],
    mtl_center: tuple[float, float],
    cpw_radius: float,
) -> tuple[int, str, tuple[float, float], tuple[float, float]]:
    candidates: list[tuple[float, float, int, str, tuple[float, float], tuple[float, float]]] = []
    for index in range(len(waypoints) - 1):
        x0, y0 = waypoints[index]
        x1, y1 = waypoints[index + 1]
        if x0 == x1:
            segment_length = abs(y1 - y0)
            axis = "v"
            midpoint_x, midpoint_y = x0, (y0 + y1) / 2.0
        elif y0 == y1:
            segment_length = abs(x1 - x0)
            axis = "h"
            midpoint_x, midpoint_y = (x0 + x1) / 2.0, y0
        else:
            continue
        if segment_length < 6 * cpw_radius:
            continue
        dist2 = (midpoint_x - mtl_center[0]) ** 2 + (midpoint_y - mtl_center[1]) ** 2
        candidates.append((segment_length, dist2, index, axis, (x0, y0), (x1, y1)))

    if not candidates:
        raise ValueError(
            "No axis-aligned supplied-waypoint segment is suitable for dogleg insertion."
        )
    segment_length, _dist2, index, axis, p0, p1 = max(
        candidates,
        key=lambda item: (item[0], item[1]),
    )
    return index, axis, p0, p1


def _route_arm_with_length(
    component: gf.Component,
    start_port: gf.Port,
    end_port: gf.Port,
    requested_length_um: float,
    supplied_waypoints: tuple[tuple[float, float], ...],
    anchor_orientation: float,
    mtl_center: tuple[float, float],
    cpw_radius: float,
    route_cross_section: CrossSectionSpec,
) -> dict[str, object]:
    dbu = float(component.kcl.dbu)
    target_length_um = round(requested_length_um / dbu) * dbu
    fallback_layer = start_port.layer if start_port.layer is not None else end_port.layer
    if fallback_layer is None:
        fallback_layer = LAYER.D0_TOP_M1_DRAW

    def _scratch_route(route_waypoints: tuple[tuple[float, float], ...]) -> object:
        scratch = gf.Component()
        scratch_start = _to_port(
            name="start",
            anchor=(float(start_port.x), float(start_port.y)),
            orientation=float(start_port.orientation),
            width=float(start_port.width) if start_port.width else 0.0,
            layer=fallback_layer,
        )
        scratch_end = _to_port(
            name="end",
            anchor=(float(end_port.x), float(end_port.y)),
            orientation=float(end_port.orientation),
            width=float(end_port.width) if end_port.width else 0.0,
            layer=fallback_layer,
        )
        return _route_once(
            component=scratch,
            start_port=scratch_start,
            end_port=scratch_end,
            waypoints=route_waypoints,
            route_cross_section=route_cross_section,
            cpw_radius=cpw_radius,
        )

    base_route = _scratch_route(supplied_waypoints)
    base_length_um = _route_length_um(base_route, dbu)
    if base_length_um > target_length_um + dbu:
        raise ValueError(
            "Constrained base route exceeds target length. "
            f"base={base_length_um!r}um, target_grid={target_length_um!r}um."
        )

    routed_waypoints = supplied_waypoints
    tuning = {
        "enabled": False,
        "requested_length_um": requested_length_um,
        "target_length_um": target_length_um,
        "base_length_um": base_length_um,
        "extra_needed_um": max(0.0, target_length_um - base_length_um),
        "dogleg": None,
        "solver_attempts": 0,
    }

    extra_needed = target_length_um - base_length_um
    if extra_needed > dbu:
        selected_index, axis, p0, p1 = _pick_axis_aligned_candidate(
            supplied_waypoints,
            mtl_center=mtl_center,
            cpw_radius=cpw_radius,
        )
        lead = 2 * cpw_radius
        h = max(2 * cpw_radius, extra_needed / 2.0)
        h = round(h / dbu) * dbu
        if h < dbu:
            h = dbu

        for attempt in range(1, 3):
            if axis == "h":
                y = p0[1]
                direction = 1.0 if p1[0] >= p0[0] else -1.0
                if (y - mtl_center[1]) >= 0:
                    normal = 1.0
                else:
                    normal = -1.0
                x_enter = p0[0] + direction * lead
                x_exit = p1[0] - direction * lead
                if abs(x_exit - x_enter) < 2 * cpw_radius:
                    raise ValueError(
                        "Selected segment has insufficient span for dogleg lead clearance."
                    )
                trial = (
                    *supplied_waypoints[: selected_index + 1],
                    (x_enter, y),
                    (x_enter, y + normal * h),
                    (x_exit, y + normal * h),
                    *supplied_waypoints[selected_index + 1 :],
                )
            else:
                x = p0[0]
                direction = 1.0 if p1[1] >= p0[1] else -1.0
                if (x - mtl_center[0]) >= 0:
                    normal = 1.0
                else:
                    normal = -1.0
                y_enter = p0[1] + direction * lead
                y_exit = p1[1] - direction * lead
                if abs(y_exit - y_enter) < 2 * cpw_radius:
                    raise ValueError(
                        "Selected segment has insufficient span for dogleg lead clearance."
                    )
                trial = (
                    *supplied_waypoints[: selected_index + 1],
                    (x, y_enter),
                    (x + normal * h, y_enter),
                    (x + normal * h, y_exit),
                    *supplied_waypoints[selected_index + 1 :],
                )

            try:
                trial_route = _scratch_route(trial)
            except ValueError:
                if attempt == 2:
                    raise
                h += dbu
                continue
            trial_length = _route_length_um(trial_route, dbu)
            tuning["solver_attempts"] = attempt

            if abs(trial_length - target_length_um) <= dbu:
                routed_waypoints = tuple(trial)
                tuning["enabled"] = True
                tuning["dogleg"] = {
                    "segment_axis": axis,
                    "segment_index": selected_index,
                    "lead_um": float(lead),
                    "dogleg_height_um": float(h),
                    "normal_direction": float(normal),
                    "iterations": attempt,
                    "target_error_um": float(trial_length - target_length_um),
                    "anchor_outward_orientation": float(anchor_orientation),
                }
                break

            error = target_length_um - trial_length
            h += error / 2.0
            h = round(max(h, 2 * cpw_radius) / dbu) * dbu
            if attempt == 2 and abs(trial_length - target_length_um) > dbu:
                raise ValueError(
                    "Unable to satisfy requested arm length with one rectangular dogleg tuning."
                )

    route = _route_once(
        component=component,
        start_port=start_port,
        end_port=end_port,
        waypoints=routed_waypoints,
        route_cross_section=route_cross_section,
        cpw_radius=cpw_radius,
    )
    route_length_um = _route_length_um(route, dbu)
    if abs(route_length_um - target_length_um) > dbu:
        raise ValueError(
            "Final route for arm is outside 1-dbu tolerance. "
            f"target_grid={target_length_um!r}um, realized={route_length_um!r}um."
        )

    route_error = route_length_um - target_length_um
    route_backbone = _extract_backbone(route, dbu)
    return {
        "requested_length_um": requested_length_um,
        "target_grid_length_um": target_length_um,
        "supplied_waypoints": supplied_waypoints,
        "routed_waypoints": routed_waypoints,
        "route_backbone": route_backbone,
        "base_length_um": base_length_um,
        "realized_length_um": route_length_um,
        "length_error_um": route_error,
        "tuning": tuning,
        "start_port": {
            "x": float(start_port.x),
            "y": float(start_port.y),
            "orientation": float(start_port.orientation),
            "name": str(start_port.name),
        },
        "end_port": {
            "x": float(end_port.x),
            "y": float(end_port.y),
            "orientation": float(end_port.orientation),
            "name": str(end_port.name),
        },
    }


def _add_open_end_cap(
    component: gf.Component,
    end_port: gf.Port,
    etch_width: float,
    cpw_width: float,
    etch_layer: Layer,
    mask_layer: Layer,
    ground_mask_width: float,
) -> tuple[gf.ComponentReference, str]:
    """Add OrPen-style open-end CPW cap aligned to ``end_port``."""

    open_etch_comp = gf.components.rectangle(
        size=(etch_width, cpw_width + 2 * etch_width),
        layer=etch_layer,
        centered=True,
        port_type="optical",
        port_orientations=(0, 180),
    )
    open_mask_comp = gf.components.rectangle(
        size=(etch_width, ground_mask_width),
        layer=mask_layer,
        centered=True,
        port_type="optical",
        port_orientations=(0, 180),
    )
    open_etch_ref = component << open_etch_comp
    open_mask_ref = component << open_mask_comp
    orientation = float(end_port.orientation) % 360
    if orientation == 180.0:
        connected_port_name = "o2"
    elif orientation in {0.0, 90.0, 270.0}:
        connected_port_name = "o1"
    else:
        raise ValueError(
            f"readout_open end port orientation must be cardinal, got {orientation!r}."
        )
    open_cap_port_name = "o1" if connected_port_name == "o2" else "o2"
    open_etch_ref.connect(
        connected_port_name,
        end_port,
        allow_width_mismatch=True,
        allow_layer_mismatch=True,
    )
    open_mask_ref.connect(
        connected_port_name,
        end_port,
        allow_width_mismatch=True,
        allow_layer_mismatch=True,
    )
    return open_etch_ref, open_cap_port_name


@gf.cell(tags=["elements"])
def capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators(
    readout_open_length: float = 2539.512388,
    shared_short_length: float = 2270.302789,
    coupled_length: float = 311.256590,
    filter_open_length: float = 2319.359517,
    cpw_radius: float = 100.0,
    single_cpw_xs: CrossSectionSpec = "cpw_6_7_6",
    coupled_cpw_xs: CrossSectionSpec = "coupled_cpw_w7_s6_d3",
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    idc_finger_length: float = 59.924760,
    mtl_center: tuple[float, float] = (0.0, 0.0),
    mtl_orientation: float = 0.0,
    filter_open_anchor: tuple[float, float, float] = (-355.628, -1011.0, 270.0),
    filter_open_waypoints: tuple[tuple[float, float], ...] = (
        (-255.628, -11.0),
        (-355.628, -11.0),
        (-355.628, -411.0),
        (-1022.608, -411.0),
        (-1022.608, -811.0),
        (-355.628, -811.0),
        (-355.628, -911.0),
    ),
    readout_open_anchor: tuple[float, float, float] = (-355.628, 1011.0, 90.0),
    readout_open_waypoints: tuple[tuple[float, float], ...] = (
        (-255.628, 11.0),
        (-355.628, 11.0),
        (-355.628, 411.0),
        (-1132.684, 411.0),
        (-1132.684, 811.0),
        (-355.628, 811.0),
        (-355.628, 911.0),
    ),
    readout_short_anchor: tuple[float, float, float] = (2022.771, 500.0, 0.0),
    readout_short_waypoints: tuple[tuple[float, float], ...] = (
        (255.628, 11.0),
        (355.628, 11.0),
        (355.628, 500.0),
        (1922.771, 500.0),
    ),
    filter_short_anchor: tuple[float, float, float] = (2022.771, -500.0, 0.0),
    filter_short_waypoints: tuple[tuple[float, float], ...] = (
        (255.628, -11.0),
        (355.628, -11.0),
        (355.628, -500.0),
        (1922.771, -500.0),
    ),
) -> gf.Component:
    """Return an individual readout/coupled Purcell-filter topology sharing one coupled MTL section.

    Public preview defaults:
    readout_open_length=2539.512388, shared_short_length=2270.302789,
    coupled_length=311.256590,
    filter_open_length=2319.359517, idc_finger_length=59.924760.
    """

    for name, value in (
        ("readout_open_length", readout_open_length),
        ("shared_short_length", shared_short_length),
        ("coupled_length", coupled_length),
        ("filter_open_length", filter_open_length),
        ("idc_finger_length", idc_finger_length),
        ("cpw_radius", cpw_radius),
    ):
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"{name} must be finite and positive, got {value!r}.") from e
        if not isfinite(numeric_value) or numeric_value <= 0:
            raise ValueError(f"{name} must be finite and positive, got {value!r}.")
    (
        readout_open_length,
        shared_short_length,
        coupled_length,
        filter_open_length,
        idc_finger_length,
        cpw_radius,
    ) = map(
        float,
        (
            readout_open_length,
            shared_short_length,
            coupled_length,
            filter_open_length,
            idc_finger_length,
            cpw_radius,
        ),
    )
    try:
        mtl_orientation = float(mtl_orientation)
    except (TypeError, ValueError) as e:
        raise ValueError(
            "mtl_orientation must be numeric and one of {0, 90, 180, 270}, "
            f"got {mtl_orientation!r}."
        ) from e
    if not isfinite(mtl_orientation):
        raise ValueError(f"mtl_orientation must be finite, got {mtl_orientation!r}.")
    if mtl_orientation % 90 != 0:
        raise ValueError(
            "mtl_orientation must be cardinal and one of {0, 90, 180, 270}. "
            f"Got {mtl_orientation!r}."
        )
    mtl_orientation = float(mtl_orientation % 360)

    single_xs = gf.get_cross_section(
        single_cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=cpw_radius,
    )
    coupled_xs = gf.get_cross_section(
        coupled_cpw_xs,
        trace_names=("p", "r"),
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=cpw_radius,
    )

    c = gf.Component()
    c.info["topology"] = (
        "capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators"
    )
    c.info["readout_open_length_um"] = float(readout_open_length)
    c.info["shared_short_length_um"] = float(shared_short_length)
    c.info["coupled_length_um"] = float(coupled_length)
    c.info["filter_open_length_um"] = float(filter_open_length)
    c.info["idc_finger_length_um"] = float(idc_finger_length)
    c.info["cpw_radius_um"] = float(cpw_radius)
    c.info["ordered_port_names"] = ("o_readout_open", "o_feedline_coupling")

    shared_short_length = float(shared_short_length)

    cpw_width = float(single_xs.width)
    etch_section = single_xs["cpw_etch_pos"]
    ground_mask_section = single_xs["cpw_ground_mask"]
    c.info["draw_layer"] = tuple(int(value) for value in single_xs["cpw_draw"].layer)
    c.info["etch_layer"] = tuple(int(value) for value in etch_section.layer)
    c.info["ground_mask_layer"] = tuple(int(value) for value in ground_mask_section.layer)
    c.info["ground_mask_width"] = float(ground_mask_section.width)

    c.info["readout_trace"] = "r"
    c.info["filter_trace"] = "p"

    if not isinstance(mtl_center, tuple) or len(mtl_center) != 2:
        raise ValueError(f"mtl_center must be a 2-tuple (x, y), got {mtl_center!r}.")
    mtl_center = (float(mtl_center[0]), float(mtl_center[1]))
    requested_mtl_center_um = tuple(mtl_center)
    dbu = float(c.kcl.dbu)
    if not isfinite(mtl_center[0]) or not isfinite(mtl_center[1]):
        raise ValueError(f"mtl_center coordinates must be finite, got {mtl_center!r}.")
    _is_grid_aligned(mtl_center[0], dbu, name="mtl_center[0]")
    _is_grid_aligned(mtl_center[1], dbu, name="mtl_center[1]")

    filter_open_anchor = _coerce_anchor("filter_open_anchor", filter_open_anchor, dbu=dbu)
    readout_open_anchor = _coerce_anchor("readout_open_anchor", readout_open_anchor, dbu=dbu)
    readout_short_anchor = _coerce_anchor("readout_short_anchor", readout_short_anchor, dbu=dbu)
    filter_short_anchor = _coerce_anchor("filter_short_anchor", filter_short_anchor, dbu=dbu)
    filter_open_waypoints = _coerce_waypoints(
        "filter_open_waypoints", filter_open_waypoints, dbu=dbu
    )
    readout_open_waypoints = _coerce_waypoints(
        "readout_open_waypoints", readout_open_waypoints, dbu=dbu
    )
    readout_short_waypoints = _coerce_waypoints(
        "readout_short_waypoints", readout_short_waypoints, dbu=dbu
    )
    filter_short_waypoints = _coerce_waypoints(
        "filter_short_waypoints", filter_short_waypoints, dbu=dbu
    )

    shared_coupled_length = float(coupled_length)
    coupled = c << gf.get_component(
        "n_trace_mtl_section",
        length=shared_coupled_length,
        cross_section=coupled_xs,
    )
    coupled.dmove((-shared_coupled_length / 2.0, 0.0))
    if mtl_orientation != 0:
        coupled.drotate(mtl_orientation)
    if mtl_center != (0.0, 0.0):
        coupled.dmove(mtl_center)

    readout_open_target_port = _to_port(
        "o_readout_open_target",
        (readout_open_anchor[0], readout_open_anchor[1]),
        _opposite_orientation(readout_open_anchor[2]),
        cpw_width,
        draw_layer,
    )
    readout_open_cap_anchor_port = _to_port(
        "o_readout_open_cap_anchor",
        (readout_open_anchor[0], readout_open_anchor[1]),
        readout_open_anchor[2],
        cpw_width,
        draw_layer,
    )
    readout_short_target_port = _to_port(
        "o_readout_short_target",
        (readout_short_anchor[0], readout_short_anchor[1]),
        _opposite_orientation(readout_short_anchor[2]),
        cpw_width,
        draw_layer,
    )
    filter_short_target_port = _to_port(
        "o_filter_short_target",
        (filter_short_anchor[0], filter_short_anchor[1]),
        _opposite_orientation(filter_short_anchor[2]),
        cpw_width,
        draw_layer,
    )

    # Route short and open arms with anchor/waypoint authority.
    readout_short_info = _route_arm_with_length(
        component=c,
        start_port=coupled.ports["r_o2"],
        end_port=readout_short_target_port,
        requested_length_um=shared_short_length,
        supplied_waypoints=readout_short_waypoints,
        anchor_orientation=readout_short_anchor[2],
        mtl_center=mtl_center,
        cpw_radius=cpw_radius,
        route_cross_section=single_xs,
    )
    filter_short_info = _route_arm_with_length(
        component=c,
        start_port=coupled.ports["p_o2"],
        end_port=filter_short_target_port,
        requested_length_um=shared_short_length,
        supplied_waypoints=filter_short_waypoints,
        anchor_orientation=filter_short_anchor[2],
        mtl_center=mtl_center,
        cpw_radius=cpw_radius,
        route_cross_section=single_xs,
    )

    capacitor_component = gf.get_component(
        "interdigital_capacitor",
        finger_length=idc_finger_length,
        cpw_xs=single_cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    filter_open_cap_in_target_orientation = _opposite_orientation(filter_open_anchor[2])
    capacitor = c << capacitor_component
    capacitor.drotate(
        (
            filter_open_cap_in_target_orientation
            - float(capacitor_component.ports["o_capacitor_in"].orientation)
        )
        % 360
    )
    capacitor.dmove(
        (
            filter_open_anchor[0] - float(capacitor.ports["o_capacitor_in"].x),
            filter_open_anchor[1] - float(capacitor.ports["o_capacitor_in"].y),
        )
    )
    if (
        float(capacitor.ports["o_capacitor_in"].orientation)
        != filter_open_cap_in_target_orientation
        or abs(float(capacitor.ports["o_capacitor_in"].x) - filter_open_anchor[0]) > dbu
        or abs(float(capacitor.ports["o_capacitor_in"].y) - filter_open_anchor[1]) > dbu
    ):
        raise ValueError(
            "Failed to align interdigital_capacitor o_capacitor_in to the requested "
            "filter-open anchor position and orientation."
        )

    filter_open_info = _route_arm_with_length(
        component=c,
        start_port=coupled.ports["p_o1"],
        end_port=capacitor.ports["o_capacitor_in"],
        requested_length_um=filter_open_length,
        supplied_waypoints=filter_open_waypoints,
        anchor_orientation=filter_open_anchor[2],
        mtl_center=mtl_center,
        cpw_radius=cpw_radius,
        route_cross_section=single_xs,
    )

    readout_open_info = _route_arm_with_length(
        component=c,
        start_port=coupled.ports["r_o1"],
        end_port=readout_open_target_port,
        requested_length_um=readout_open_length,
        supplied_waypoints=readout_open_waypoints,
        anchor_orientation=readout_open_anchor[2],
        mtl_center=mtl_center,
        cpw_radius=cpw_radius,
        route_cross_section=single_xs,
    )

    c.info["short_termination"] = "cpw_gap_stop"

    c.info["path_geometry"] = {
        "requested": {
            "anchors": {
                "mtl_center": tuple(requested_mtl_center_um),
                "mtl_orientation": float(mtl_orientation),
                "filter_open_anchor": tuple(filter_open_anchor),
                "readout_open_anchor": tuple(readout_open_anchor),
                "readout_short_anchor": tuple(readout_short_anchor),
                "filter_short_anchor": tuple(filter_short_anchor),
            },
            "waypoints": {
                "filter_open_waypoints": filter_open_waypoints,
                "readout_open_waypoints": readout_open_waypoints,
                "readout_short_waypoints": readout_short_waypoints,
                "filter_short_waypoints": filter_short_waypoints,
            },
        },
        "mtl_instance": {
            "length_um": shared_coupled_length,
            "orientation_deg": float(mtl_orientation),
            "requested_center_um": tuple(requested_mtl_center_um),
            "actual_center_um": (
                0.25
                * (
                    float(coupled.ports["r_o1"].x)
                    + float(coupled.ports["r_o2"].x)
                    + float(coupled.ports["p_o1"].x)
                    + float(coupled.ports["p_o2"].x)
                ),
                0.25
                * (
                    float(coupled.ports["r_o1"].y)
                    + float(coupled.ports["r_o2"].y)
                    + float(coupled.ports["p_o1"].y)
                    + float(coupled.ports["p_o2"].y)
                ),
            ),
            "port_span_um": {
                "r_span_um": float(
                    (
                        (float(coupled.ports["r_o1"].x) - float(coupled.ports["r_o2"].x)) ** 2
                        + (float(coupled.ports["r_o1"].y) - float(coupled.ports["r_o2"].y)) ** 2
                    )
                    ** 0.5
                ),
                "p_span_um": float(
                    (
                        (float(coupled.ports["p_o1"].x) - float(coupled.ports["p_o2"].x)) ** 2
                        + (float(coupled.ports["p_o1"].y) - float(coupled.ports["p_o2"].y)) ** 2
                    )
                    ** 0.5
                ),
            },
            "ports": {
                "r_o1": {
                    "center_um": tuple(coupled.ports["r_o1"].center),
                    "orientation_deg": float(coupled.ports["r_o1"].orientation),
                },
                "r_o2": {
                    "center_um": tuple(coupled.ports["r_o2"].center),
                    "orientation_deg": float(coupled.ports["r_o2"].orientation),
                },
                "p_o1": {
                    "center_um": tuple(coupled.ports["p_o1"].center),
                    "orientation_deg": float(coupled.ports["p_o1"].orientation),
                },
                "p_o2": {
                    "center_um": tuple(coupled.ports["p_o2"].center),
                    "orientation_deg": float(coupled.ports["p_o2"].orientation),
                },
            },
        },
        "readout_short": readout_short_info,
        "filter_short": filter_short_info,
        "readout_open": readout_open_info,
        "filter_open": filter_open_info,
    }

    readout_open_cap, readout_open_cap_port_name = _add_open_end_cap(
        component=c,
        end_port=readout_open_cap_anchor_port,
        etch_width=float(etch_section.width),
        cpw_width=cpw_width,
        etch_layer=etch_layer,
        mask_layer=ground_mask_layer,
        ground_mask_width=float(ground_mask_section.width),
    )

    c.info["filter_capacitor_instance"] = "interdigital_capacitor"
    c.info["path_geometry"]["idc_outer_port"] = {
        "name": "o_feedline_coupling",
        "orientation": float(capacitor.ports["o_capacitor_out"].orientation),
        "center_um": tuple(capacitor.ports["o_capacitor_out"].center),
    }
    c.info["path_geometry"]["idc_input_port"] = {
        "name": str(capacitor.ports["o_capacitor_in"].name),
        "orientation": float(capacitor.ports["o_capacitor_in"].orientation),
        "center_um": tuple(capacitor.ports["o_capacitor_in"].center),
    }
    c.info["path_geometry"]["readout_open"]["cap_outer_port"] = {
        "name": readout_open_cap_port_name,
        "orientation": float(readout_open_cap.ports[readout_open_cap_port_name].orientation),
        "center_um": tuple(readout_open_cap.ports[readout_open_cap_port_name].center),
    }

    c.add_port(port=readout_open_cap.ports[readout_open_cap_port_name], name="o_readout_open")
    c.add_port(port=capacitor.ports["o_capacitor_out"], name="o_feedline_coupling")

    pair_bbox = c.bbox()
    c.info["pair_bbox_um"] = {
        "width": float(pair_bbox.width()),
        "height": float(pair_bbox.height()),
    }

    return c


__all__ = [
    "capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators",
]
