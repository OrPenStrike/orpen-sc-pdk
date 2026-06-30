"""Single-resonator chip with keepout-aware indium bump fill."""

import gdsfactory as gf

from orpen_sc_pdk.cells.indium import indium_ground
from orpen_sc_pdk.helpers.layout import get_keepout_region_from_targets
from orpen_sc_pdk.ports import SimulationPortType
from orpen_sc_pdk.tech import LAYER, Layer


@gf.cell(tags=["chips"])
def resonator_with_indium_bumps(
    resonator_length: float = 4000.0,
    resonator_meanders: int = 6,
    bump_field_padding: float = 360.0,
    indium_bump_size: float = 20.0,
    indium_bump_gap: float = 40.0,
    indium_margin: float = 90.0,
    indium_keepout_clearance: float = 30.0,
    under_bump_size: float = 40.0,
    include_under_bump: bool = True,
    # Layers
    resonator_draw_layer: Layer = LAYER.D1_BOTTOM_M1_DRAW,
    resonator_etch_layer: Layer = LAYER.D1_BOTTOM_M1_ETCH,
    resonator_ground_mask_layer: Layer = LAYER.D1_BOTTOM_GROUND_MASK,
    indium_bump_layer: Layer = LAYER.D0_D1_INDIUM_BUMP,
    under_bump_layer: Layer = LAYER.D0_D1_UNDER_BUMP,
) -> gf.Component:
    """Return one resonator with bumps filling chip padding outside keepout."""

    if resonator_length <= 0:
        raise ValueError(f"resonator_length must be positive, got {resonator_length!r}.")
    if resonator_meanders <= 0:
        raise ValueError(f"resonator_meanders must be positive, got {resonator_meanders!r}.")
    if bump_field_padding < 0:
        raise ValueError(f"bump_field_padding must be non-negative, got {bump_field_padding!r}.")

    c = gf.Component()

    res = c << gf.get_component(
        "resonator",
        length=resonator_length,
        meanders=resonator_meanders,
        coupling_length=200.0,
        hanger_straight_length=160.0,
        hanger_bend_segment2_angle=90,
        cpw_xs="cpw_6_7_6",
        cpw_radius=100.0,
        meander_radius=80.0,
        draw_layer=resonator_draw_layer,
        etch_layer=resonator_etch_layer,
        ground_mask_layer=resonator_ground_mask_layer,
    )
    res.move(origin=res.center, destination=(0.0, 0.0))
    c.add_ports(port for port in res.ports if str(port.port_type) == str(SimulationPortType.MESH))

    bounds = c.size_info
    bump_field_width = float(bounds.east - bounds.west) + 2 * bump_field_padding
    bump_field_height = float(bounds.north - bounds.south) + 2 * bump_field_padding

    keepout_region = get_keepout_region_from_targets(
        targets=(res,),
        layers=(
            resonator_draw_layer,
            resonator_etch_layer,
            resonator_ground_mask_layer,
        ),
        clearance_um=indium_keepout_clearance,
    )
    c << indium_ground(
        width=bump_field_width,
        height=bump_field_height,
        bump_gap=indium_bump_gap,
        margin=indium_margin,
        indium_bump_size=indium_bump_size,
        under_bump_size=under_bump_size,
        keepout_region=keepout_region,
        indium_bump_layer=indium_bump_layer,
        under_bump_layer=under_bump_layer,
        include_under_bump=include_under_bump,
    )

    return c


__all__ = ["resonator_with_indium_bumps"]
