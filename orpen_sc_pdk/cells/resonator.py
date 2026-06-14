"""Public resonator primitives."""

from __future__ import annotations

import gdsfactory as gf
from gdsfactory.typings import LayerSpec

from orpen_sc_pdk.cells.cpw import cpw_straight
from orpen_sc_pdk.tech import LAYER


@gf.cell
def quarter_wave_resonator(
    length: float = 1000.0,
    signal_width: float = 10.0,
    gap: float = 6.0,
    ground_width: float = 50.0,
    coupling_length: float = 100.0,
    layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
) -> gf.Component:
    """Return a compact public CPW resonator demo primitive."""

    component = gf.Component()
    resonator = component << cpw_straight(
        length=length,
        signal_width=signal_width,
        gap=gap,
        ground_width=ground_width,
        layer=layer,
    )
    resonator.movey(ground_width + signal_width + 2 * gap)
    feedline = component << cpw_straight(
        length=coupling_length,
        signal_width=signal_width,
        gap=gap,
        ground_width=ground_width,
        layer=layer,
    )
    component.add_port("o1", port=feedline.ports["o1"])
    component.add_port("o2", port=feedline.ports["o2"])
    component.add_port("open", port=resonator.ports["o2"])
    return component
