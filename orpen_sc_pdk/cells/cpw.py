"""Public CPW primitives."""

from __future__ import annotations

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec, Layer, LayerSpec

from orpen_sc_pdk.helpers.layout import add_etch_for_component
from orpen_sc_pdk.ports import AxisDirection, add_driven_lumped_port
from orpen_sc_pdk.tech import LAYER


@gf.cell
def cpw_straight(
    length: float = 500.0,
    signal_width: float = 10.0,
    gap: float = 6.0,
    ground_width: float = 50.0,
    layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
) -> gf.Component:
    """Return a public CPW straight section with two simulation ports."""

    component = gf.Component()
    component << gf.components.rectangle(
        size=(length, signal_width),
        centered=True,
        layer=layer,
    )
    top_ground = component << gf.components.rectangle(
        size=(length, ground_width),
        centered=True,
        layer=layer,
    )
    top_ground.movey((signal_width + ground_width) / 2 + gap)
    bottom_ground = component << gf.components.rectangle(
        size=(length, ground_width),
        centered=True,
        layer=layer,
    )
    bottom_ground.movey(-((signal_width + ground_width) / 2 + gap))
    component.add_port(
        name="o1",
        center=(-length / 2, 0),
        width=signal_width,
        orientation=180,
        layer=layer,
        port_type="sim_cpw",
    )
    component.add_port(
        name="o2",
        center=(length / 2, 0),
        width=signal_width,
        orientation=0,
        layer=layer,
        port_type="sim_cpw",
    )
    return component


@gf.cell(tags=["elements"])
def launcher(
    pad_width: float = 150.0,
    pad_length: float = 150.0,
    taper_length: float = 150.0,
    side_gap_height: float = 85.0,
    end_gap_width: float = 85.0,
    cpw_xs: CrossSectionSpec = "coplanar_waveguide",
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    sim_boundary_layer: Layer = LAYER.D0_TOP_SIM_BOUNDARY,
) -> gf.Component:
    """Return a tapered CPW launcher from a large pad to a CPW neck."""

    xs = gf.get_cross_section(cpw_xs)
    cpw_width = xs["cpw_draw"].width
    cpw_gap = xs["cpw_etch_pos"].width

    component = gf.Component()

    pad_half = pad_width / 2
    neck_half = cpw_width / 2
    x_pad_end = pad_length
    x_tip = pad_length + taper_length

    component.add_polygon(
        [
            (0, pad_half),
            (x_pad_end, pad_half),
            (x_tip, neck_half),
            (x_tip, -neck_half),
            (x_pad_end, -pad_half),
            (0, -pad_half),
        ],
        layer=draw_layer,
    )

    mask_region = [
        (component.xmin - end_gap_width, component.ymax + side_gap_height),
        (pad_length, component.ymax + side_gap_height),
        (component.xmax, neck_half + cpw_gap),
        (component.xmax, -(neck_half + cpw_gap)),
        (pad_length, component.ymin - side_gap_height),
        (component.xmin - end_gap_width, component.ymin - side_gap_height),
    ]
    component.add_polygon(mask_region, layer=ground_mask_layer)

    sheet_region = [
        (component.xmin, pad_half),
        (0.0, pad_half),
        (0.0, -pad_half),
        (component.xmin, -pad_half),
    ]
    component.add_polygon(sheet_region, layer=sim_boundary_layer)

    component = add_etch_for_component(
        component=component,
        draw_layer=draw_layer,
        mask_layer=ground_mask_layer,
        etch_layer=etch_layer,
    )

    component.add_port(
        name="o_neck",
        center=(x_tip, 0),
        width=cpw_width,
        orientation=0,
        layer=draw_layer,
    )
    component.add_port(
        name="o_pad",
        center=(0, 0),
        width=pad_width,
        orientation=180,
        layer=draw_layer,
    )
    add_driven_lumped_port(
        component,
        name="o_lumped",
        center=(component.xmin / 2, 0),
        width=1,
        orientation=0,
        layer=sim_boundary_layer,
        direction=AxisDirection.POS_X,
    )

    return component
