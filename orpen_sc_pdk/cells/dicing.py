"""Dicing-edge keepout ring used by chip-level assemblies."""

import gdsfactory as gf

from orpen_sc_pdk.tech import LAYER


@gf.cell
def dicing_edge(
    size: tuple[float, float] = (10000.0, 10000.0),
    width: float = 50.0,
    layer: tuple[int, int] = LAYER.D0_TOP_M1_ETCH,
) -> gf.Component:
    """Return a rectangular edge ring on the requested layer.

    The ring is authored as outer minus inner rectangles so chip assemblies can
    place it on an ETCH or marker layer without inventing another edge helper.
    """

    sx, sy = size

    outer_size = (sx + 2 * width, sy + 2 * width)
    outer = gf.components.rectangle(size=outer_size, layer=layer, centered=True)
    inner = gf.components.rectangle(size=size, layer=layer, centered=True)

    ring = gf.boolean(
        A=outer,
        B=inner,
        operation="A-B",
        layer=layer,
    )

    return ring
