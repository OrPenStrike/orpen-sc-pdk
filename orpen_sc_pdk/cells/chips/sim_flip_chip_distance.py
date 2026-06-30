"""Flip-chip distance simulation demo cell."""

import gdsfactory as gf

from orpen_sc_pdk.cells.dicing import dicing_edge
from orpen_sc_pdk.cells.indium import indium_ground
from orpen_sc_pdk.cells.resonator import resonator
from orpen_sc_pdk.cells.taper import taper
from orpen_sc_pdk.helpers.assembly import place_launchers
from orpen_sc_pdk.helpers.layout import get_keepout_region
from orpen_sc_pdk.ports import MeshProfile, SimulationPortType, add_mesh_port
from orpen_sc_pdk.tech import LAYER, Layer


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


__all__ = ["sim_flip_chip_distance"]
