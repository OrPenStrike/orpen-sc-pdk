"""Small launcher-to-launcher CPW chip with airbridges."""

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec

from orpen_sc_pdk.cells.airbridge import airbridge
from orpen_sc_pdk.tech import LAYER, Layer


@gf.cell(tags=["chips"])
def small_airbridge_chip(
    chip_width: float = 2200.0,
    chip_height: float = 900.0,
    launcher_spacing: float = 900.0,
    airbridge_count: int = 3,
    airbridge_pitch: float = 260.0,
    airbridge_span: float = 84.0,
    airbridge_width: float = 12.0,
    airbridge_via_size: float = 14.0,
    cpw_xs: CrossSectionSpec = "cpw_6_7_6",
    cpw_radius: float = 60.0,
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    sim_boundary_layer: Layer = LAYER.D0_TOP_SIM_BOUNDARY,
    airbridge_draw_layer: Layer = LAYER.D0_TOP_AB_DRAW,
    airbridge_via_layer: Layer = LAYER.D0_TOP_AB_VIA,
) -> gf.Component:
    """Return a small symmetric CPW chip with airbridge geometry."""

    if chip_width <= 0 or chip_height <= 0:
        raise ValueError("chip_width and chip_height must be positive.")
    if launcher_spacing <= 0:
        raise ValueError(f"launcher_spacing must be positive, got {launcher_spacing!r}.")
    if airbridge_count < 0:
        raise ValueError(f"airbridge_count must be non-negative, got {airbridge_count!r}.")

    c = gf.Component()
    c << gf.get_component("dicing_edge", size=(chip_width, chip_height), layer=etch_layer)

    xs = gf.get_cross_section(
        cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=cpw_radius,
    )
    launcher = gf.get_component(
        "launcher",
        cpw_xs=cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        sim_boundary_layer=sim_boundary_layer,
    )

    left = c << launcher
    left.move(origin=left.ports["o_neck"].center, destination=(-launcher_spacing / 2, 0.0))
    right = c << launcher
    right.rotate(180)
    right.move(origin=right.ports["o_neck"].center, destination=(launcher_spacing / 2, 0.0))

    line = c << gf.components.straight(length=launcher_spacing, cross_section=xs)
    line.move(origin=line.ports["o1"].center, destination=left.ports["o_neck"].center)

    if airbridge_count:
        start_x = -((airbridge_count - 1) * airbridge_pitch) / 2
        for index in range(airbridge_count):
            x = start_x + index * airbridge_pitch
            bridge = c << airbridge(
                bridge_span=airbridge_span,
                bridge_width=airbridge_width,
                via_size=airbridge_via_size,
                airbridge_draw_layer=airbridge_draw_layer,
                airbridge_via_layer=airbridge_via_layer,
            )
            bridge.move((x, 0.0))

    c.add_port(name="o_left", port=left.ports["o_pad"])
    c.add_port(name="o_right", port=right.ports["o_pad"])
    return c


__all__ = ["small_airbridge_chip"]
