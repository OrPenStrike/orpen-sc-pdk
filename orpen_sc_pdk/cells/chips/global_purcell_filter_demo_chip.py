"""Global Purcell-filter demo chip cell."""

from math import pi

import gdsfactory as gf
from gdsfactory.typings import ComponentSpec, CrossSectionSpec

from orpen_sc_pdk.helpers.assembly import place_launchers
from orpen_sc_pdk.helpers.layout import merge_component_layers
from orpen_sc_pdk.ports import (
    AxisDirection,
    MeshProfile,
    add_driven_lumped_port,
    add_mesh_port,
)
from orpen_sc_pdk.tech import LAYER, Layer


@gf.cell(tags=["chips", "demos"])
def global_purcell_filter_demo_chip(
    chip_width: float = 9900,
    chip_height: float = 9900,
    dicing_edge: ComponentSpec = "dicing_edge",
    # Common
    cpw_xs: CrossSectionSpec = "coplanar_waveguide",
    cpw_radius: float = 100,
    # Readout line
    start_straight_length: float = 500,
    end_straight_length: float = 500,
    purcell_filter_length: float = 8550,
    capacitor_in: ComponentSpec = "interdigital_capacitor",
    capacitor_out: ComponentSpec = "interdigital_capacitor",
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    sim_boundary_layer: Layer = LAYER.D0_TOP_SIM_BOUNDARY,
) -> gf.Component:
    """Return a public launcher-to-launcher global Purcell-filter demo chip."""

    c = gf.Component()

    _ = c << gf.get_component(
        component=dicing_edge,
        size=(chip_width, chip_height),
        layer=etch_layer,
    )

    launchers = place_launchers(
        c=c,
        chip_height=chip_height,
        chip_width=chip_width,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        cpw_xs=cpw_xs,
    )

    readout_xs = gf.get_cross_section(cpw_xs, radius=cpw_radius)
    temp = gf.Component()
    readout_line_routes = gf.routing.route_bundle(
        component=temp,
        ports1=launchers.left[0].ports["o_neck"],
        ports2=launchers.right[3].ports["o_neck"],
        cross_section=readout_xs,
        start_straight_length=start_straight_length,
        end_straight_length=end_straight_length,
        steps=[
            {"x": -3000, "y": 0},
            {"x": 3000, "y": 0},
        ],
    )

    capacitor_in_ref = c << gf.get_component(
        capacitor_in,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        cpw_xs=cpw_xs,
    )
    capacitor_out_ref = c << gf.get_component(
        capacitor_out,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        cpw_xs=cpw_xs,
    )
    capacitor_in_half_length = capacitor_in_ref.xmax
    capacitor_out_half_length = capacitor_out_ref.xmax
    middle_length = (
        (launchers.right[3].ports["o_neck"].x - launchers.left[0].ports["o_neck"].x)
        - start_straight_length
        - end_straight_length
        - 4 * cpw_radius
    )
    case_2_dy = (
        purcell_filter_length
        - middle_length
        - pi * cpw_radius
        - capacitor_in_half_length
        - capacitor_out_half_length
    ) / 2

    if (
        purcell_filter_length + capacitor_in_half_length + capacitor_out_half_length
    ) <= middle_length:
        capacitor_in_ref.movex(-purcell_filter_length / 2)
        capacitor_out_ref.movex(purcell_filter_length / 2)
        routing_case = 1
    elif (
        (purcell_filter_length - capacitor_in_half_length - capacitor_out_half_length)
        >= middle_length + pi * cpw_radius
    ) and (
        (
            (launchers.left[0].y - cpw_radius - 20)
            > case_2_dy + cpw_radius + 2 * capacitor_in_half_length
        )
        and (
            (abs(launchers.right[3].y) - cpw_radius - 20)
            > case_2_dy + cpw_radius + 2 * capacitor_out_half_length
        )
    ):
        capacitor_in_ref.rotate(-90)
        capacitor_out_ref.rotate(-90)
        capacitor_in_ref.move(
            (
                launchers.left[0].ports["o_neck"].x + start_straight_length + cpw_radius,
                case_2_dy + capacitor_in_half_length + cpw_radius,
            )
        )
        capacitor_out_ref.move(
            (
                launchers.right[3].ports["o_neck"].x - end_straight_length - cpw_radius,
                -(case_2_dy + capacitor_out_half_length + cpw_radius),
            )
        )
        routing_case = 2
    else:
        raise ValueError(
            "purcell_filter_length is not suitable for the current readout-line parameter setup."
        )

    gf.routing.route_bundle(
        component=c,
        ports1=[launchers.left[0].ports["o_neck"]],
        ports2=[capacitor_in_ref.ports["o_capacitor_in"]],
        cross_section=readout_xs,
        start_straight_length=start_straight_length,
    )

    if routing_case == 1:
        gf.routing.route_bundle(
            component=c,
            ports1=[capacitor_in_ref.ports["o_capacitor_out"]],
            ports2=[capacitor_out_ref.ports["o_capacitor_in"]],
            cross_section=readout_xs,
        )
    elif routing_case == 2:
        gf.routing.route_bundle(
            component=c,
            ports1=[capacitor_in_ref.ports["o_capacitor_out"]],
            ports2=[capacitor_out_ref.ports["o_capacitor_in"]],
            cross_section=readout_xs,
            steps=[{"x": 0, "y": 0}],
        )

    gf.routing.route_bundle(
        component=c,
        ports1=[launchers.right[3].ports["o_neck"]],
        ports2=[capacitor_out_ref.ports["o_capacitor_out"]],
        cross_section=readout_xs,
        start_straight_length=end_straight_length,
    )

    c = merge_component_layers([c], layers=[draw_layer, etch_layer, ground_mask_layer])

    add_driven_lumped_port(
        c,
        name="o_lumped_readout_in",
        center=launchers.left[0].ports["o_lumped"].center,
        width=1,
        orientation=0,
        layer=sim_boundary_layer,
        direction=AxisDirection.POS_X,
    )
    add_driven_lumped_port(
        c,
        name="o_lumped_readout_out",
        center=launchers.right[3].ports["o_lumped"].center,
        width=1,
        orientation=0,
        layer=sim_boundary_layer,
        direction=AxisDirection.POS_X,
    )

    add_mesh_port(
        c,
        name="o_mesh_readout_in",
        center=launchers.left[0].ports["o_neck"].center,
        layer=draw_layer,
        mesh_profile=MeshProfile.CRITICAL_METAL_TRACE,
        width=10.0,
        orientation=0,
    )
    add_mesh_port(
        c,
        name="o_mesh_readout_out",
        center=launchers.right[3].ports["o_neck"].center,
        layer=draw_layer,
        mesh_profile=MeshProfile.CRITICAL_METAL_TRACE,
        width=10.0,
        orientation=0,
    )
    add_mesh_port(
        c,
        name="o_mesh_purcell_filter",
        center=(0, 0),
        layer=draw_layer,
        mesh_profile=MeshProfile.CRITICAL_METAL_TRACE,
        width=10.0,
        orientation=0,
    )

    c.info["routing_case"] = routing_case
    c.info["purcell_filter_length"] = purcell_filter_length
    c.info["readout_route_probe_length"] = float(readout_line_routes[0].length) / 1e3

    return c


__all__ = ["global_purcell_filter_demo_chip"]
