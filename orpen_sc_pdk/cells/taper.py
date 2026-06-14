"""CPW taper primitive with explicit ground-mask and etch derivation."""

import gdsfactory as gf

from orpen_sc_pdk.tech import LAYER, Layer


@gf.cell(tags=["elements"])
def taper(
    width1: float = 10.0,
    width2: float = 7.0,
    gap1: float = 6.0,
    gap2: float = 6.0,
    length: float = 100.0,
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Return a DRAW taper plus its local CPW clearance and derived ETCH.

    Use this when chip assemblies need a compact transition between two CPW
    widths while keeping route ports on the center conductor DRAW layer.
    """

    c = gf.Component()

    taper = c << gf.components.taper(
        width1=width1,
        width2=width2,
        length=length,
        layer=draw_layer,
    )

    ground_mask = c << gf.components.taper(
        width1=width1 + 2 * gap1,
        width2=width2 + 2 * gap2,
        length=length,
        layer=ground_mask_layer,
    )

    _ = c << gf.boolean(
        A=ground_mask,
        B=taper,
        operation="A-B",
        layer1=ground_mask_layer,
        layer2=draw_layer,
        layer=etch_layer,
    )

    # Route ports are placed on the DRAW conductor, not on the derived ETCH gap.
    c.add_port(
        name="o_taper_in",
        center=(0, 0),
        width=width1,
        orientation=180,
        layer=draw_layer,
    )
    c.add_port(
        name="o_taper_out",
        center=(length, 0),
        width=width2,
        orientation=0,
        layer=draw_layer,
    )

    return c
