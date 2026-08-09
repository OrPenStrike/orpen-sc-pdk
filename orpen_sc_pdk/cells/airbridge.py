"""Reusable airbridge primitives."""

from math import isfinite

import gdsfactory as gf

from orpen_sc_pdk.tech import LAYER, Layer


@gf.cell(tags=["elements"])
def airbridge(
    bridge_span: float = 84.0,
    bridge_width: float = 12.0,
    via_size: float = 14.0,
    # Layers
    airbridge_draw_layer: Layer = LAYER.D0_TOP_AB_DRAW,
    airbridge_via_layer: Layer = LAYER.D0_TOP_AB_VIA,
) -> gf.Component:
    """Return a same-face airbridge deck with endpoint landing via pads.

    The deck is a centered rectangle of size ``(bridge_width, bridge_span)``, where
    the bridge span is interpreted as the local Y-extent from -span/2 to +span/2 and
    the width is along local X. The component is centered at the local origin and
    provides no route ports; parent placement is expected to orient/rotate it as
    needed in assembly contexts.
    """

    if not all(isfinite(v) for v in (bridge_span, bridge_width, via_size)):
        raise ValueError("bridge_span, bridge_width, and via_size must be finite.")
    if bridge_span <= 0:
        raise ValueError("bridge_span must be positive.")
    if bridge_width <= 0:
        raise ValueError("bridge_width must be positive.")
    if via_size <= 0:
        raise ValueError("via_size must be positive.")
    if via_size > bridge_span:
        raise ValueError("via_size must be no larger than bridge_span.")

    c = gf.Component()
    deck = c << gf.components.rectangle(
        size=(bridge_width, bridge_span),
        centered=True,
        layer=airbridge_draw_layer,
    )
    deck.move((0.0, 0.0))

    for y in (-bridge_span / 2, bridge_span / 2):
        via = c << gf.components.rectangle(
            size=(via_size, via_size),
            centered=True,
            layer=airbridge_via_layer,
        )
        via.move((0.0, y))

    c.ports.clear()
    return c
