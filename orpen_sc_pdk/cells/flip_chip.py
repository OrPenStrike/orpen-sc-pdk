"""Public flip-chip demos ported with AI assistance using GDSFactory+ MCP."""

import gdsfactory as gf

from orpen_sc_pdk.cells.dicing import dicing_edge
from orpen_sc_pdk.cells.indium import indium_ground
from orpen_sc_pdk.cells.resonator import resonator
from orpen_sc_pdk.cells.taper import taper
from orpen_sc_pdk.helpers.assembly import place_launchers
from orpen_sc_pdk.helpers.layout import (
    get_keepout_region,
    get_keepout_region_from_targets,
)
from orpen_sc_pdk.helpers.routing import (
    route_bundle_8dir,
    route_bundle_8dir_global,
)
from orpen_sc_pdk.ports import MeshProfile, SimulationPortType, add_mesh_port
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
    """Place one public resonator as a routing obstacle in a Q-chip channel demo."""

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


@gf.cell
def sim_flip_chip_distance(
    c_chip_width: float = 9900.0,
    c_chip_height: float = 9900.0,
    q_chip_width: float = 7500.0,
    q_chip_height: float = 7500.0,
    # XS
    cpw_6_10_6_radius: float = 100.0,
    cpw_6_7_6_radius: float = 100.0,
    cpw_2dot7_4_2dot7_radius: float = 100.0,
    q0_resonator_length: float = 4000.0,
    q0_meander_straight_length_weights: tuple[float, ...] | None = None,
    q0_qubit_resonator_segment_reference_point: tuple[float, float] | None = None,
    q0_qubit_resonator_segment_length: float = 0.0,
    q0_qubit_resonator_segment_gap: float = 10.0,
    q0_route_to_qubit_resonator_segment: bool = False,
    # Layers
    q_chip_draw_layer: Layer = LAYER.D1_BOTTOM_M1_DRAW,
    q_chip_etch_layer: Layer = LAYER.D1_BOTTOM_M1_ETCH,
    q_chip_ground_mask_layer: Layer = LAYER.D1_BOTTOM_GROUND_MASK,
    c_chip_draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    c_chip_etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    c_chip_ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    under_bump_layer: Layer = LAYER.D0_D1_UNDER_BUMP,
    indium_bump_layer: Layer = LAYER.D0_D1_INDIUM_BUMP,
    indium_keepout_clearance: float | None = 30.0,
    indium_keepout_layers: tuple[Layer, ...] | None = None,
) -> gf.Component:
    """Return a two-face flip-chip distance layout with one routed readout line.

    The C-chip owns launchers and readout routing; the Q-chip owns the resonator
    and optional indium bump field. Indium placement is evaluated after signal
    geometry so keepouts reflect the actual authored layout.
    """

    cpw_6_10_6_xs = gf.get_cross_section(
        "cpw_6_10_6",
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
        radius=cpw_6_10_6_radius,
    )
    cpw_6_7_6_xs = gf.get_cross_section(
        "cpw_6_7_6",
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
        radius=cpw_6_7_6_radius,
    )
    cpw_2dot7_4_2dot7_xs = gf.get_cross_section(
        "cpw_2dot7_4_2dot7",
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
        radius=cpw_2dot7_4_2dot7_radius,
    )

    c = gf.Component()

    # Dicing rings mark the C-chip and Q-chip boundaries on their own ETCH layers.
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

    # Launchers live on the C-chip face and define off-chip readout endpoints.
    launchers = place_launchers(
        c=c,
        chip_height=c_chip_height,
        chip_width=c_chip_width,
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
        cpw_xs=cpw_6_10_6_xs,
    )

    # Entry ports describe where the C-chip line hands off into the Q-chip span.
    c.add_port(
        name="o_readout_in_entry_point",
        center=(-3800, 0),
        width=cpw_6_10_6_xs["cpw_draw"].width,
        orientation=180,
        layer=c_chip_draw_layer,
    )
    c.add_port(
        name="o_readout_out_entry_point",
        center=(3800, 0),
        width=cpw_6_10_6_xs["cpw_draw"].width,
        orientation=0,
        layer=c_chip_draw_layer,
    )

    # Readout segment 1: route from the launcher into the Q-chip handoff width.
    readout_line_segment1 = gf.routing.route_bundle(
        component=c,
        ports1=launchers.left[1].ports["o_neck"],
        ports2=c.ports["o_readout_in_entry_point"],
        cross_section=cpw_6_10_6_xs,
        radius=cpw_6_10_6_radius,
        start_straight_length=127.5,
    )
    # Width transition at the Q-chip entry.
    readout_in_taper = c << taper(
        width1=cpw_6_10_6_xs["cpw_draw"].width,
        gap1=cpw_6_10_6_xs["cpw_etch_pos"].width,
        width2=cpw_2dot7_4_2dot7_xs["cpw_draw"].width,
        gap2=cpw_2dot7_4_2dot7_xs["cpw_etch_pos"].width,
        length=100.0,
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
    )
    readout_in_taper.connect("o_taper_in", readout_line_segment1[0].end_port)

    # Readout segment 3: route back from the Q-chip handoff to the output launcher.
    readout_line_segment3 = gf.routing.route_bundle(
        component=c,
        ports1=c.ports["o_readout_out_entry_point"],
        ports2=launchers.right[1].ports["o_neck"],
        cross_section=cpw_6_10_6_xs,
        radius=cpw_6_10_6_radius,
        end_straight_length=127.5,
    )
    # Width transition at the Q-chip exit.
    readout_out_taper = c << taper(
        width1=cpw_2dot7_4_2dot7_xs["cpw_draw"].width,
        gap1=cpw_2dot7_4_2dot7_xs["cpw_etch_pos"].width,
        width2=cpw_6_10_6_xs["cpw_draw"].width,
        gap2=cpw_6_10_6_xs["cpw_etch_pos"].width,
        length=100.0,
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
    )
    readout_out_taper.connect("o_taper_out", readout_line_segment3[0].start_port)

    # Resonator placement is anchored by its hanger center, not by a route port.
    q0_resonator_hanger_center = (0, 0)

    q0_resonator = c << resonator(
        length=q0_resonator_length,
        coupling_length=200.0,
        hanger_bend_segment2_angle=90,
        cpw_xs="cpw_6_7_6",
        draw_layer=q_chip_draw_layer,
        etch_layer=q_chip_etch_layer,
        ground_mask_layer=q_chip_ground_mask_layer,
        cpw_radius=cpw_6_7_6_radius,
        meander_radius=80,
        meander_straight_length_weights=q0_meander_straight_length_weights,
        qubit_resonator_segment_reference_point=q0_qubit_resonator_segment_reference_point,
        qubit_resonator_segment_length=q0_qubit_resonator_segment_length,
        qubit_resonator_segment_gap=q0_qubit_resonator_segment_gap,
        route_to_qubit_resonator_segment=q0_route_to_qubit_resonator_segment,
    )
    q0_resonator.move(
        origin=q0_resonator.ports["o_hanger_center"].center,
        destination=q0_resonator_hanger_center,
    )
    c.add_ports(
        (
            port
            for port in q0_resonator.ports
            if str(port.port_type) == str(SimulationPortType.MESH)
        ),
        prefix="q0_",
    )

    readout_coupling_start_port = q0_resonator.ports["o_hanger_readout_coupling_start"]
    readout_coupling_end_port = q0_resonator.ports["o_hanger_readout_coupling_end"]
    readout_coupling_length = readout_coupling_end_port.x - readout_coupling_start_port.x
    if readout_coupling_length <= 0:
        raise ValueError(
            "Readout coupling window must have positive length; "
            f"got start={tuple(readout_coupling_start_port.center)!r}, "
            f"end={tuple(readout_coupling_end_port.center)!r}."
        )

    # Segment 2 keeps the Q-chip span narrow except for the local coupling window.
    readout_coupling_straight = c << gf.components.straight(
        length=readout_coupling_length,
        cross_section=cpw_6_7_6_xs,
    )
    readout_coupling_straight.move(
        origin=readout_coupling_straight.ports["o1"].center,
        destination=readout_coupling_start_port.center,
    )
    readout_coupling_width = float(cpw_6_7_6_xs["cpw_draw"].width)
    add_mesh_port(
        c,
        name="o_mesh_readout_coupling_straight",
        center=readout_coupling_straight.center,
        width=readout_coupling_width,
        feature_width_um=readout_coupling_width,
        orientation=readout_coupling_straight.ports["o1"].orientation,
        layer=c_chip_draw_layer,
        mesh_profile=MeshProfile.CRITICAL_METAL_TRACE,
    )

    readout_coupling_in_taper = c << taper(
        width1=cpw_2dot7_4_2dot7_xs["cpw_draw"].width,
        gap1=cpw_2dot7_4_2dot7_xs["cpw_etch_pos"].width,
        width2=cpw_6_7_6_xs["cpw_draw"].width,
        gap2=cpw_6_7_6_xs["cpw_etch_pos"].width,
        length=100.0,
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
    )
    readout_coupling_in_taper.connect(
        "o_taper_out",
        readout_coupling_straight.ports["o1"],
    )

    readout_coupling_out_taper = c << taper(
        width1=cpw_6_7_6_xs["cpw_draw"].width,
        gap1=cpw_6_7_6_xs["cpw_etch_pos"].width,
        width2=cpw_2dot7_4_2dot7_xs["cpw_draw"].width,
        gap2=cpw_2dot7_4_2dot7_xs["cpw_etch_pos"].width,
        length=100.0,
        draw_layer=c_chip_draw_layer,
        etch_layer=c_chip_etch_layer,
        ground_mask_layer=c_chip_ground_mask_layer,
    )
    readout_coupling_out_taper.connect(
        "o_taper_in",
        readout_coupling_straight.ports["o2"],
    )

    gf.routing.route_bundle(
        component=c,
        ports1=readout_in_taper.ports["o_taper_out"],
        ports2=readout_coupling_in_taper.ports["o_taper_in"],
        cross_section=cpw_2dot7_4_2dot7_xs,
        radius=cpw_2dot7_4_2dot7_radius,
    )
    gf.routing.route_bundle(
        component=c,
        ports1=readout_coupling_out_taper.ports["o_taper_out"],
        ports2=readout_out_taper.ports["o_taper_in"],
        cross_section=cpw_2dot7_4_2dot7_xs,
        radius=cpw_2dot7_4_2dot7_radius,
    )

    if indium_keepout_clearance is None:
        indium_keepout_region = None
    else:
        if indium_keepout_layers is None:
            indium_keepout_layers = (
                q_chip_draw_layer,
                q_chip_etch_layer,
                q_chip_ground_mask_layer,
                c_chip_draw_layer,
                c_chip_etch_layer,
                c_chip_ground_mask_layer,
            )
        indium_keepout_region = get_keepout_region(
            component=c,
            layers=indium_keepout_layers,
            clearance_um=indium_keepout_clearance,
        )

    # Place the indium plane last, after the signal layout can define keepout regions.
    _ = c << indium_ground(
        width=q_chip_width,
        height=q_chip_height,
        indium_bump_layer=indium_bump_layer,
        under_bump_layer=under_bump_layer,
        keepout_region=indium_keepout_region,
    )
    return c


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
