"""Public source inspection coupons composed from canonical OrPen children.

Activate the bound OrPen PDK before calling these zero-argument GF factories.
CONVERGING source geometry candidate; no native simulation behavior is implied.
Children retain local Entities; callers, not these cells, assign final Nets.
"""

import gdsfactory as gf

from orpen_sc_pdk.cells.layout.airbridge import airbridge
from orpen_sc_pdk.cells.layout.indium import indium_bump
from orpen_sc_pdk.cells.simulation.simple_pad import square_pad_capacitor
from orpen_sc_pdk.tech import LAYER


@gf.cell(tags=["simulation", "chip", "simple_pad", "flip_chip", "bump"])
def flip_chip_pad_coupon() -> gf.Component:
    """Compose the default lower pad, full upper plane and four Ground bump sites.

    The upper conductor uses the D1 bottom-face layer; its outward normal is -Z.
    The lower child locator remains present but is unused in this coupon.
    The four bump children preserve their existing UBM source footprints.
    """
    c = gf.Component()
    lower = c << square_pad_capacitor()
    lower.name = "LOWER_PAD_DIE"
    upper = c << gf.components.rectangle(
        size=(1000.0, 1000.0), centered=True, layer=LAYER.D1_BOTTOM_M1_DRAW
    )
    upper.name = "UPPER_GROUND"
    upper_substrate = c << gf.components.rectangle(
        size=(1000.0, 1000.0), centered=True, layer=LAYER.D1_SUBSTRATE_AREA
    )
    upper_substrate.name = "UPPER_SUBSTRATE"
    for x, y, name in (
        (-250.0, -250.0, "BUMP_MM"),
        (-250.0, 250.0, "BUMP_MP"),
        (250.0, -250.0, "BUMP_PM"),
        (250.0, 250.0, "BUMP_PP"),
    ):
        bump = c << indium_bump()
        bump.name = name
        bump.move((x, y))
    c.info["component_semantics"] = {
        "schema_version": 2,
        "conductor_regions": [
            {
                "semantic_id": "UPPER_GROUND",
                "level": "D1_BOTTOM_M1",
                "gds_layer": tuple(LAYER.D1_BOTTOM_M1_DRAW),
                "geometry": {"geometry_source": "gds_polygon", "selector_point_um": (0.0, 0.0)},
            }
        ],
    }
    c.info["inspection_source_intent"] = {
        "contact_intent": "Ground-to-Ground only; no bump near central PAD",
        "unused_locator": "LOWER_PAD_DIE/o_junction_lumped; not forwarded or excited",
        "stack_selection": "get_two_die_flip_chip_layer_stack()",
        "final_electrical_nets": "caller-owned, not assigned",
        "upper_face": "D1_BOTTOM; outward -Z",
    }
    return c


@gf.cell(tags=["simulation", "cpw", "single_die", "airbridge"])
def cpw_airbridge_coupon() -> gf.Component:
    """Compose positive finite-ground Al CPW with the unchanged canonical bridge.

    Preserve the existing partial 12 x 7 um deck/pier overlap, rather than
    extending the deck or modifying the nominal rectangular-prism process.
    """
    c = gf.Component()
    signal = c << gf.components.rectangle(
        size=(500.0, 10.0), centered=True, layer=LAYER.D0_TOP_M1_DRAW
    )
    signal.name = "SIGNAL"
    for y, name in ((-51.0, "GROUND_MINUS"), (51.0, "GROUND_PLUS")):
        ground = c << gf.components.rectangle(
            size=(500.0, 80.0), centered=True, layer=LAYER.D0_TOP_M1_DRAW
        )
        ground.name = name
        ground.movey(y)
    substrate = c << gf.components.rectangle(
        size=(500.0, 182.0), centered=True, layer=LAYER.D0_SUBSTRATE_AREA
    )
    substrate.name = "SUBSTRATE"
    bridge = c << airbridge()
    bridge.name = "AIRBRIDGE"
    c.info["component_semantics"] = {
        "schema_version": 2,
        "conductor_regions": [
            {
                "semantic_id": name,
                "level": "D0_TOP_M1",
                "gds_layer": tuple(LAYER.D0_TOP_M1_DRAW),
                "geometry": {"geometry_source": "gds_polygon", "selector_point_um": point},
            }
            for name, point in (
                ("SIGNAL", (0.0, 0.0)),
                ("GROUND_MINUS", (0.0, -51.0)),
                ("GROUND_PLUS", (0.0, 51.0)),
            )
        ],
    }
    c.info["inspection_source_intent"] = {
        "stack_selection": "get_single_die_layer_stack(include_airbridges=True)",
        "final_electrical_nets": "caller-owned, not assigned",
        "ports": "none; no GF or native port invented",
    }
    return c
