"""Public single-die capacitor geometry for the SCGSim beginner workflows."""

import gdsfactory as gf

from orpen_sc_pdk.ports import add_junction_lumped_port
from orpen_sc_pdk.tech import LAYER


@gf.cell
def square_pad_capacitor(
    pad_side_um: float = 200.0,
    gap_um: float = 20.0,
    die_side_um: float = 1000.0,
    junction_width_um: float = 2.0,
) -> gf.Component:
    """Return one square island surrounded by same-face ground.

    Defaults are explicit synthetic teaching inputs, not a measured qubit or
    fabrication target. The east-edge sheet is a non-metal locator; its optional
    linear inductance belongs to the Eigenmode notebook, not this layout.
    """
    if pad_side_um <= 0 or gap_um <= 0 or junction_width_um <= 0:
        raise ValueError("pad side, gap and junction width must be positive")
    opening_side = pad_side_um + 2 * gap_um
    if die_side_um <= opening_side:
        raise ValueError("die side must exceed the ground opening side")
    if junction_width_um > pad_side_um:
        raise ValueError("junction sheet width must fit on the pad edge")

    component = gf.Component()
    component << gf.components.rectangle(
        size=(pad_side_um, pad_side_um), centered=True, layer=LAYER.D0_TOP_M1_DRAW
    )
    # The PDK recipe fills the die face except this mask, then restores DRAW.
    component << gf.components.rectangle(
        size=(opening_side, opening_side), centered=True, layer=LAYER.D0_TOP_GROUND_MASK
    )
    component << gf.components.rectangle(
        size=(die_side_um, die_side_um), centered=True, layer=LAYER.D0_SUBSTRATE_AREA
    )
    # Positive strips retain the physical opening without a bridge-encoded GDS
    # hole being mistaken for a filled source polygon by downstream selectors.
    ground_width = (die_side_um - opening_side) / 2
    ground_offset = (die_side_um + opening_side) / 4
    for center, size in (
        ((0, ground_offset), (die_side_um, ground_width)),
        ((0, -ground_offset), (die_side_um, ground_width)),
        ((ground_offset, 0), (ground_width, opening_side)),
        ((-ground_offset, 0), (ground_width, opening_side)),
    ):
        ground = component << gf.components.rectangle(
            size=size, centered=True, layer=LAYER.D0_TOP_M1_DRAW
        )
        ground.move(center)
    half_pad = pad_side_um / 2
    sheet_center = (half_pad + gap_um / 2, 0.0)
    # One source database unit lands the non-metal sheet on each terminal;
    # exact boundary contact otherwise separates after float/GDS conversion.
    sheet_overlap_um = component.kcl.dbu
    sheet = component << gf.components.rectangle(
        size=(gap_um + 2 * sheet_overlap_um, junction_width_um),
        centered=True,
        layer=LAYER.D0_TOP_SIM_BOUNDARY,
    )
    sheet.move(sheet_center)
    add_junction_lumped_port(
        component,
        name="o_junction_lumped",
        center=sheet_center,
        width=junction_width_um,
        orientation=0.0,
        layer=LAYER.D0_TOP_SIM_BOUNDARY,
    )
    component.info["component_semantics"] = {
        "schema_version": 2,
        "conductor_regions": [
            {
                "semantic_id": "PAD",
                "level": "D0_TOP_M1",
                "gds_layer": tuple(LAYER.D0_TOP_M1_DRAW),
                "geometry": {
                    "geometry_source": "gds_polygon",
                    "selector_point_um": (0.0, 0.0),
                },
            },
            {
                "semantic_id": "GROUND",
                "level": "D0_TOP_M1",
                "gds_layer": tuple(LAYER.D0_TOP_GROUND_MASK),
            },
        ],
        "ports": [
            {
                "name": "o_junction_lumped",
                "layer": tuple(LAYER.D0_TOP_SIM_BOUNDARY),
                "target_layer": "D0_TOP_M1",
            }
        ],
    }
    component.info["model_source"] = "Synthetic public single-die LC teaching geometry"
    component.info["junction_sheet_overlap_um"] = sheet_overlap_um
    return component


__all__ = ["square_pad_capacitor"]
