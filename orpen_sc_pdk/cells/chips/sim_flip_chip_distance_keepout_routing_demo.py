"""Single-route flip-chip keepout routing demo cell."""

import gdsfactory as gf

from orpen_sc_pdk.cells.dicing import dicing_edge
from orpen_sc_pdk.cells.resonator import resonator
from orpen_sc_pdk.cells.taper import taper
from orpen_sc_pdk.helpers.layout import get_keepout_region_from_targets
from orpen_sc_pdk.helpers.routing import route_bundle_8dir
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
def sim_flip_chip_distance_keepout_routing_demo(
    c_chip_width: float = 9900.0,
    c_chip_height: float = 9900.0,
    q_chip_width: float = 7500.0,
    q_chip_height: float = 7500.0,
    resonator_pitch: float = 1900.0,
    route_span: float = 7600.0,
    taper_length: float = 100.0,
    start_straight_length: float | None = None,
    end_straight_length: float | None = None,
    routing_grid_resolution: float = 100.0,
    cpw_radius: float = 100.0,
    keepout_clearance: float = 160.0,
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
    """Demo A* CPW routing through two channels between three resonators.

    The context geometry is visible in the output cell, but only the resonator
    keepout region is passed to the route planner. This keeps route validation
    focused on the intended obstacle contract.
    """

    if route_span <= q_chip_width:
        raise ValueError(
            "route_span must be larger than q_chip_width so the outer ports can sit outside "
            "the Q-chip dicing edge."
        )
    if taper_length <= 0:
        raise ValueError(f"taper_length must be positive, got {taper_length!r}.")
    if start_straight_length is not None and start_straight_length < 0:
        raise ValueError(
            f"start_straight_length must be non-negative, got {start_straight_length!r}."
        )
    if end_straight_length is not None and end_straight_length < 0:
        raise ValueError(f"end_straight_length must be non-negative, got {end_straight_length!r}.")

    c = gf.Component()

    # Context geometry is intentionally not part of the A* avoid layer list.
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

    resonator_refs = []
    for y in (resonator_pitch, 0.0, -resonator_pitch):
        ref = _place_resonator_obstacle(
            component=c,
            y=y,
            cpw_radius=cpw_radius,
            draw_layer=q_chip_draw_layer,
            etch_layer=q_chip_etch_layer,
            ground_mask_layer=q_chip_ground_mask_layer,
        )
        resonator_refs.append(ref)

    baseline_region = c.get_region(c_chip_draw_layer, merge=True)
    baseline_region += c.get_region(c_chip_etch_layer, merge=True)
    baseline_region += c.get_region(c_chip_ground_mask_layer, merge=True)
    baseline_region = baseline_region.merged()

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

    c.add_port(
        name="o_route_left",
        center=(-route_span / 2, 0),
        width=outer_xs["cpw_draw"].width,
        orientation=0,
        layer=c_chip_draw_layer,
    )
    c.add_port(
        name="o_route_right",
        center=(route_span / 2, 0),
        width=outer_xs["cpw_draw"].width,
        orientation=180,
        layer=c_chip_draw_layer,
    )

    q_chip_left_edge_x = -q_chip_width / 2
    q_chip_right_edge_x = q_chip_width / 2

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
        destination=(q_chip_left_edge_x, 0),
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
        destination=(q_chip_right_edge_x, 0),
    )

    gf.routing.route_bundle(
        component=c,
        ports1=[c.ports["o_route_left"]],
        ports2=[left_taper.ports["o_taper_in"]],
        cross_section=outer_xs,
        radius=cpw_radius,
    )
    gf.routing.route_bundle(
        component=c,
        ports1=[right_taper.ports["o_taper_in"]],
        ports2=[c.ports["o_route_right"]],
        cross_section=outer_xs,
        radius=cpw_radius,
    )

    route_start_port = left_taper.ports["o_taper_out"]
    route_end_port = right_taper.ports["o_taper_out"]

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
    routes, route_plans = route_bundle_8dir(
        component=c,
        ports1=[route_start_port],
        ports2=[route_end_port],
        keepout_region=resonator_keepout_region,
        route_bbox=route_bbox,
        grid_resolution=routing_grid_resolution,
        cross_section=inner_xs,
        bend_radius=cpw_radius,
        start_straight_length=start_straight_length,
        end_straight_length=end_straight_length,
        debug_plan_layer=route_plan_debug_layer if show_route_centerline else None,
        debug_path_layer=route_path_debug_layer if show_route_centerline else None,
        debug_path_width=route_debug_path_width,
    )
    route = routes[0]
    route_plan = route_plans[0]

    if not show_route_keepout:
        c.remove_layers([route_keepout_layer])

    if validate_route_collision:
        # Compare only newly authored route geometry against the resonator
        # keepout so pre-existing context layers do not create false failures.
        post_route_region = c.get_region(c_chip_draw_layer, merge=True)
        post_route_region += c.get_region(c_chip_etch_layer, merge=True)
        post_route_region += c.get_region(c_chip_ground_mask_layer, merge=True)
        route_region = post_route_region.merged() - baseline_region
        route_intersects_keepout = not (route_region & resonator_keepout_region).is_empty()
        c.info["route_intersects_resonator_keepout"] = route_intersects_keepout
        if route_intersects_keepout:
            raise ValueError("8-direction route intersects the resonator keepout region.")

    c.info["route_grid_resolution"] = routing_grid_resolution
    c.info["route_cpw_radius"] = cpw_radius
    c.info["route_keepout_clearance"] = keepout_clearance
    c.info["route_taper_length"] = taper_length
    c.info["route_start_straight_length"] = route.start_straight_length
    c.info["route_end_straight_length"] = route.end_straight_length
    c.info["route_min_straight_between_turns"] = route.min_straight_between_turns
    c.info["route_bend_style"] = route.bend_style
    c.info["route_show_centerline"] = show_route_centerline
    c.info["route_plan_debug_layer"] = route_plan_debug_layer
    c.info["route_path_debug_layer"] = route_path_debug_layer
    c.info["route_plan_turns"] = route_plan.turns
    c.info["route_plan_length"] = route_plan.length
    c.info["route_plan_visited_nodes"] = route_plan.visited_nodes
    c.info["route_length"] = route.length

    return c


__all__ = ["sim_flip_chip_distance_keepout_routing_demo"]
