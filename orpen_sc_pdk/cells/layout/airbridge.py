"""Reusable airbridge primitives."""

from math import isfinite

import gdsfactory as gf

from orpen_sc_pdk.tech import LAYER, Layer


@gf.cell(tags=["layout", "airbridge"])
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

    Canonical same-face layer pairs declare local deck and pier Entities using
    PDK stack levels, without electrical Nets. Unknown/custom pairs remain
    layout-only. The stack is a nominal rectangular-prism electrostatic model,
    not the released reflow arch or a complete paper-footprint replica.
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
    for prefix in ("D0_TOP", "D0_BOTTOM", "D1_TOP", "D1_BOTTOM"):
        if tuple(airbridge_draw_layer) == tuple(getattr(LAYER, f"{prefix}_AB_DRAW")) and tuple(
            airbridge_via_layer
        ) == tuple(getattr(LAYER, f"{prefix}_AB_VIA")):
            c.info["component_semantics"] = {
                "schema_version": 2,
                "conductor_regions": [
                    {
                        "semantic_id": semantic_id,
                        "level": f"{prefix}_{level_suffix}",
                        "gds_layer": tuple(int(value) for value in layer),
                        "geometry": {
                            "geometry_source": "gds_polygon",
                            "selector_point_um": point,
                        },
                        "metadata": {"source_kind": "authored"},
                    }
                    for semantic_id, level_suffix, layer, point in (
                        ("DECK", "AIRBRIDGE", airbridge_draw_layer, (0.0, 0.0)),
                        (
                            "PIER_MINUS",
                            "AIRBRIDGE_VIA",
                            airbridge_via_layer,
                            (0.0, -bridge_span / 2),
                        ),
                        (
                            "PIER_PLUS",
                            "AIRBRIDGE_VIA",
                            airbridge_via_layer,
                            (0.0, bridge_span / 2),
                        ),
                    )
                ],
            }
            break
    return c
