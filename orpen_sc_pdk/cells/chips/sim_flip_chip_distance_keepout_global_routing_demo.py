"""Global flip-chip keepout routing demo cell."""

import gdsfactory as gf

from orpen_sc_pdk.cells.dicing import dicing_edge
from orpen_sc_pdk.cells.resonator import resonator
from orpen_sc_pdk.cells.taper import taper
from orpen_sc_pdk.helpers.assembly import place_launchers
from orpen_sc_pdk.helpers.layout import get_keepout_region_from_targets
from orpen_sc_pdk.helpers.routing import route_bundle_8dir_global
from orpen_sc_pdk.tech import LAYER, Layer


def _place_resonator_obstacle(
    component: gf.Component,
    *,
    y: float,
    cpw_radius: float,
    draw_layer: Layer,
    etch_layer: Layer,
    ground_mask_layer: Layer,
) -> gf.ComponentReference:
    ref = component << resonator(
        length=1400.0,
        meanders=2,
        coupling_length=140.0,
        hanger_straight_length=100.0,
        hanger_bend_segment2_angle=90,
        cpw_xs="cpw_6_7_6",
        cpw_radius=min(cpw_radius, 60.0),
        meander_radius=min(cpw_radius, 55.0),
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    ref.move(
        origin=ref.ports["o_hanger_center"].center,
        destination=(0.0, y),
    )
    return ref


@gf.cell(tags=["chips"])
def sim_flip_chip_distance_keepout_global_routing_demo(
    c_chip_width: float = 9900.0,
    c_chip_height: float = 9900.0,
    q_chip_width: float = 7500.0,
    q_chip_height: float = 7500.0,
    resonator_pitch: float = 1650.0,
    resonator_y_offsets: tuple[float, float, float] = (130.0, 80.0, 50.0),
    taper_length: float = 100.0,
    routing_grid_resolution: float = 50.0,
    cpw_radius: float = 100.0,
    keepout_clearance: float = 160.0,
    route_clearance: float = 60.0,
    max_search_nodes: int = 256,
    show_route_keepout: bool = True,
    show_route_centerline: bool = True,
    route_plan_debug_layer: Layer | None = (1000, 1),
    route_path_debug_layer: Layer | None = (1000, 2),
    route_debug_path_width: float = 5.0,
    validate_route_collision: bool = True,
    # Layers
    q_chip_draw_layer: Layer = LAYER.D1_BOTTOM_M1_DRAW,
    q_chip_etch_layer: Layer = LAYER.D1_BOTTOM_M1_ETCH,
    q_chip_ground_mask_layer: Layer = LAYER.D1_BOTTOM_GROUND_MASK,
    c_chip_draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    c_chip_etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    c_chip_ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    route_keepout_layer: Layer = LAYER.ERROR_PATH,
) -> gf.Component:
    """Demo global 8-direction routing for four CPWs through tight resonator keepout channels.

    This assembly exposes route-planner debug metadata in ``Component.info`` so
    routing changes can be compared without inspecting generated polygons by eye.
    """

    if taper_length <= 0:
        raise ValueError(f"taper_length must be positive, got {taper_length!r}.")
    if route_clearance < 0:
        raise ValueError(f"route_clearance must be non-negative, got {route_clearance!r}.")
    if max_search_nodes <= 0:
        raise ValueError(f"max_search_nodes must be positive, got {max_search_nodes!r}.")
    if len(resonator_y_offsets) != 3:
        raise ValueError(
            "resonator_y_offsets must contain exactly three values for the top, middle, "
            f"and bottom resonators, got {resonator_y_offsets!r}."
        )

    c = gf.Component()

    _ = c << gf.get_component(
        dicing_edge,
        size=(c_chip_width, c_chip_height),
        layer=c_chip_etch_layer,
    )
    _ = c << gf.get_component(
        dicing_edge,
        size=(q_chip_width, q_chip_height),
        layer=q_chip_etch_layer,
    )

    outer_xs = gf.get_cross_section(
        "cpw_6_10_6",
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
        radius=cpw_radius,
    )
    inner_xs = gf.get_cross_section(
        "cpw_6_7_6",
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
        radius=cpw_radius,
    )

    launchers = place_launchers(
        c=c,
        chip_height=c_chip_height,
        chip_width=c_chip_width,
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
        cpw_xs=outer_xs,
    )

    resonator_refs = []
    resonator_ys = tuple(
        base_y + offset_y
        for base_y, offset_y in zip(
            (resonator_pitch, 0.0, -resonator_pitch),
            resonator_y_offsets,
            strict=True,
        )
    )
    for index, y in enumerate(resonator_ys):
        ref = _place_resonator_obstacle(
            component=c,
            y=y,
            cpw_radius=cpw_radius,
            draw_layer=q_chip_draw_layer,
            etch_layer=q_chip_etch_layer,
            ground_mask_layer=q_chip_ground_mask_layer,
        )
        resonator_refs.append(ref)
        c.info[f"global_route_resonator_{index}_y"] = y

    q_chip_left_edge_x = -q_chip_width / 2
    q_chip_right_edge_x = q_chip_width / 2
    left_taper_outer_x = q_chip_left_edge_x - taper_length / 2
    right_taper_outer_x = q_chip_right_edge_x + taper_length / 2
    c.info["global_route_left_taper_outer_x"] = left_taper_outer_x
    c.info["global_route_right_taper_outer_x"] = right_taper_outer_x

    left_taper_ports = []
    right_taper_ports = []
    for index, (left_launcher, right_launcher) in enumerate(
        zip(launchers.left, launchers.right, strict=True)
    ):
        y = left_launcher.ports["o_neck"].y
        left_taper = c << taper(
            width1=outer_xs["cpw_draw"].width,
            width2=inner_xs["cpw_draw"].width,
            length=taper_length,
            draw_layer=c_chip_draw_layer,
            etch_layer=c_chip_etch_layer,
            ground_mask_layer=c_chip_ground_mask_layer,
        )
        left_taper.move(
            origin=left_taper.ports["o_taper_in"].center,
            destination=(left_taper_outer_x, y),
        )

        right_taper = c << taper(
            width1=outer_xs["cpw_draw"].width,
            width2=inner_xs["cpw_draw"].width,
            length=taper_length,
            draw_layer=c_chip_draw_layer,
            etch_layer=c_chip_etch_layer,
            ground_mask_layer=c_chip_ground_mask_layer,
        )
        right_taper.rotate(180)
        right_taper.move(
            origin=right_taper.ports["o_taper_in"].center,
            destination=(right_taper_outer_x, y),
        )

        gf.routing.route_bundle(
            component=c,
            ports1=[left_launcher.ports["o_neck"]],
            ports2=[left_taper.ports["o_taper_in"]],
            cross_section=outer_xs,
            radius=cpw_radius,
        )
        gf.routing.route_bundle(
            component=c,
            ports1=[right_taper.ports["o_taper_in"]],
            ports2=[right_launcher.ports["o_neck"]],
            cross_section=outer_xs,
            radius=cpw_radius,
        )

        left_taper_ports.append(left_taper.ports["o_taper_out"])
        right_taper_ports.append(right_taper.ports["o_taper_out"])
        c.info[f"global_route_{index}_nominal_y"] = y

    baseline_region = c.get_region(c_chip_draw_layer, merge=True)
    baseline_region += c.get_region(c_chip_etch_layer, merge=True)
    baseline_region += c.get_region(c_chip_ground_mask_layer, merge=True)
    baseline_region = baseline_region.merged()

    resonator_keepout_region = get_keepout_region_from_targets(
        targets=resonator_refs,
        layers=(
            q_chip_draw_layer,
            q_chip_etch_layer,
            q_chip_ground_mask_layer,
        ),
        clearance_um=keepout_clearance,
    )
    if not resonator_keepout_region.is_empty():
        c.add_polygon(points=resonator_keepout_region, layer=route_keepout_layer)

    route_bbox = (
        q_chip_left_edge_x,
        -q_chip_height / 2,
        q_chip_right_edge_x,
        q_chip_height / 2,
    )
    result = route_bundle_8dir_global(
        component=c,
        ports1=left_taper_ports,
        ports2=right_taper_ports,
        keepout_region=resonator_keepout_region,
        route_bbox=route_bbox,
        grid_resolution=routing_grid_resolution,
        cross_section=inner_xs,
        bend_radius=cpw_radius,
        route_clearance=route_clearance,
        max_search_nodes=max_search_nodes,
        debug_plan_layer=route_plan_debug_layer if show_route_centerline else None,
        debug_path_layer=route_path_debug_layer if show_route_centerline else None,
        debug_path_width=route_debug_path_width,
    )

    if not show_route_keepout:
        c.remove_layers([route_keepout_layer])

    if validate_route_collision:
        # Validate only the delta introduced by global routing against the
        # semantic resonator keepout region.
        post_route_region = c.get_region(c_chip_draw_layer, merge=True)
        post_route_region += c.get_region(c_chip_etch_layer, merge=True)
        post_route_region += c.get_region(c_chip_ground_mask_layer, merge=True)
        route_region = post_route_region.merged() - baseline_region
        route_intersects_keepout = not (route_region & resonator_keepout_region).is_empty()
        c.info["global_route_intersects_resonator_keepout"] = route_intersects_keepout
        if route_intersects_keepout:
            raise ValueError("Global 8-direction route intersects the resonator keepout region.")

    c.info["global_route_count"] = len(result.routes)
    c.info["global_route_grid_resolution"] = routing_grid_resolution
    c.info["global_route_cpw_radius"] = cpw_radius
    c.info["global_route_keepout_clearance"] = keepout_clearance
    c.info["global_route_clearance"] = route_clearance
    c.info["global_route_taper_length"] = taper_length
    c.info["global_route_search_nodes"] = result.search_nodes
    c.info["global_route_conflicts_resolved"] = result.conflicts_resolved
    c.info["global_route_is_optimal"] = result.is_optimal
    c.info["global_route_total_length"] = result.total_length
    c.info["global_route_total_cost"] = result.total_cost
    for index, route in enumerate(result.routes):
        c.info[f"global_route_{index}_length"] = route.length
        c.info[f"global_route_{index}_turns"] = route.plan.turns
        c.info[f"global_route_{index}_visited_nodes"] = route.plan.visited_nodes

    return c


__all__ = ["sim_flip_chip_distance_keepout_global_routing_demo"]
