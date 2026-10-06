"""Public single-die capacitor geometry for the SCGSim beginner workflows."""

from math import sqrt

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


@gf.cell
def circular_pad_capacitor(
    outer_radius_um: float = 100.0,
    inner_radius_um: float = 0.0,
    gap_um: float = 20.0,
    die_side_um: float = 1000.0,
    junction_width_um: float = 2.0,
) -> gf.Component:
    """Return a public disk or annular electrode surrounded by Ground.

    An inner radius of zero selects a disk; 80 um selects the requested ring
    with the default 100 um outer radius. The inner hole is unmetalized, not
    an additional Ground conductor. These are synthetic electrical teaching
    inputs, not a mechanical drum or a measured qubit. Curve declarations use
    the CONVERGING SCGSim source-boundary contract; polygon witnesses remain
    ordinary GDS geometry. Linear L/C belongs to the Eigenmode problem only.
    """
    if not 0 <= inner_radius_um < outer_radius_um:
        raise ValueError("inner radius must be nonnegative and below outer radius")
    if gap_um <= 0 or not 0 < junction_width_um < 2 * outer_radius_um:
        raise ValueError("gap must be positive and junction width must fit the pad")
    opening_radius = outer_radius_um + gap_um
    if die_side_um <= 2 * opening_radius:
        raise ValueError("die side must exceed the ground opening diameter")

    component = gf.Component()
    if inner_radius_um == 0:
        pad = gf.components.circle(radius=outer_radius_um, layer=LAYER.D0_TOP_M1_DRAW)
        pad_selector = (0.0, 0.0)
    else:
        pad = gf.components.ring(
            radius=(outer_radius_um + inner_radius_um) / 2,
            width=outer_radius_um - inner_radius_um,
            layer=LAYER.D0_TOP_M1_DRAW,
        )
        pad_selector = ((outer_radius_um + inner_radius_um) / 2, 0.0)
    component << pad
    opening = gf.components.circle(radius=opening_radius, layer=LAYER.D0_TOP_GROUND_MASK)
    component << opening
    die = gf.components.rectangle(
        size=(die_side_um, die_side_um), centered=True, layer=LAYER.D0_SUBSTRATE_AREA
    )
    component << die
    # Preserve the circular opening in the actual positive source conductor;
    # the curve-aware consumer must decode its GDS cutline, not fill the hole.
    component << gf.boolean(
        die,
        opening,
        operation="not",
        layer=LAYER.D0_TOP_M1_DRAW,
        layer1=LAYER.D0_SUBSTRATE_AREA,
        layer2=LAYER.D0_TOP_GROUND_MASK,
    )

    half_width = junction_width_um / 2
    source_overlap = component.kcl.dbu
    # Land across the full rectangular width on the curved electrode: its
    # edge at y=+/-half_width is sqrt(R**2-half_width**2), not the east apex R.
    # One DBU extends that authored footprint into each terminal; it is not a
    # numerical acceptance tolerance or permission to infer connectivity.
    sheet_start = sqrt(outer_radius_um**2 - half_width**2) - source_overlap
    if sheet_start <= inner_radius_um:
        raise ValueError("junction pad-side landing must remain on the electrode, not its hole")
    sheet_end = opening_radius + source_overlap
    sheet_center = ((sheet_start + sheet_end) / 2, 0.0)
    sheet = component << gf.components.rectangle(
        size=(sheet_end - sheet_start, junction_width_um),
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
    ground_selector = ((opening_radius + die_side_um / 2) / 2, 0.0)
    half_die = die_side_um / 2
    square = [
        [-half_die, -half_die],
        [half_die, -half_die],
        [half_die, half_die],
        [-half_die, half_die],
    ]
    boundaries = [
        {
            "boundary_id": "PAD_OUTER",
            "entity_id": "PAD",
            "selector_point_um": pad_selector,
            "role": "outer",
            "curves": _circle_boundary(outer_radius_um),
        },
        {
            "boundary_id": "GROUND_OUTER",
            "entity_id": "GROUND",
            "selector_point_um": ground_selector,
            "role": "outer",
            "curves": [
                {"kind": "line_segment", "points_um": [point, square[(i + 1) % 4]]}
                for i, point in enumerate(square)
            ],
        },
        {
            "boundary_id": "GROUND_OPENING",
            "entity_id": "GROUND",
            "selector_point_um": ground_selector,
            "role": "hole",
            "hole_index": 0,
            "curves": _circle_boundary(opening_radius, clockwise=True),
        },
    ]
    if inner_radius_um > 0:
        boundaries.append(
            {
                "boundary_id": "PAD_INNER",
                "entity_id": "PAD",
                "selector_point_um": pad_selector,
                "role": "hole",
                "hole_index": 0,
                "curves": _circle_boundary(inner_radius_um, clockwise=True),
            }
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
                    "selector_point_um": pad_selector,
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
        "boundary_curves": boundaries,
    }
    component.info["model_source"] = "Synthetic public single-die curved LC geometry"
    component.info["junction_sheet_overlap_um"] = source_overlap
    return component


def _circle_boundary(radius: float, *, clockwise: bool = False) -> list[dict]:
    """Author two semicircles, with opposite orientation for an inner loop."""
    sign = -1 if clockwise else 1
    return [
        {
            "kind": "circular_arc",
            "points_um": [[radius, 0.0], [0.0, sign * radius], [-radius, 0.0]],
        },
        {
            "kind": "circular_arc",
            "points_um": [[-radius, 0.0], [0.0, -sign * radius], [radius, 0.0]],
        },
    ]


@gf.cell
def straight_to_circular_strip(
    straight_length_um: float = 100.0,
    bend_radius_um: float = 100.0,
    strip_width_um: float = 10.0,
    die_side_um: float = 1000.0,
) -> gf.Component:
    """Return a line-to-quarter-circle conductor with actual endpoint ports.

    This isolated strip demonstrates source anchors and rigid placement, not
    an additional resonator study. There is no Ground or implicit circuit Net.
    The final Notebook chooses Nets and registers actual transformed instances.
    """
    if straight_length_um <= 0 or not 0 < strip_width_um < 2 * bend_radius_um:
        raise ValueError("straight length and inner bend radius must be positive")
    half_width = strip_width_um / 2
    if die_side_um / 2 <= straight_length_um + bend_radius_um + half_width:
        raise ValueError("die must contain the curved strip")
    path = gf.path.Path()
    path.append(gf.path.straight(length=straight_length_um))
    path.append(gf.path.arc(radius=bend_radius_um, angle=90))
    strip = gf.path.extrude(path, width=strip_width_um, layer=LAYER.D0_TOP_M1_DRAW)
    component = gf.Component()
    component << strip
    component << gf.components.rectangle(
        size=(die_side_um, die_side_um), centered=True, layer=LAYER.D0_SUBSTRATE_AREA
    )
    # No background plane is requested for this isolated conductor observation.
    component << gf.components.rectangle(
        size=(die_side_um, die_side_um), centered=True, layer=LAYER.D0_TOP_GROUND_MASK
    )
    component.add_port(
        "o1",
        center=(0, 0),
        width=strip_width_um,
        orientation=180,
        layer=LAYER.D0_TOP_M1_DRAW,
        port_type="electrical",
    )
    component.add_port(
        "o2",
        center=(straight_length_um + bend_radius_um, bend_radius_um),
        width=strip_width_um,
        orientation=90,
        layer=LAYER.D0_TOP_M1_DRAW,
        port_type="electrical",
    )
    outer_radius = bend_radius_um + half_width
    inner_radius = bend_radius_um - half_width
    cx, cy = straight_length_um, bend_radius_um
    outer_start = [cx, -half_width]
    outer_end = [cx + outer_radius, cy]
    inner_start = [cx + inner_radius, cy]
    inner_end = [cx, half_width]
    component.info["component_semantics"] = {
        "schema_version": 2,
        "conductor_regions": [
            {
                "semantic_id": "TRACE",
                "level": "D0_TOP_M1",
                "gds_layer": tuple(LAYER.D0_TOP_M1_DRAW),
                "geometry": {
                    "geometry_source": "gds_polygon",
                    "selector_point_um": (straight_length_um / 2, 0),
                },
            }
        ],
        "boundary_curves": [
            {
                "boundary_id": "TRACE_OUTER",
                "entity_id": "TRACE",
                "selector_point_um": (straight_length_um / 2, 0),
                "role": "outer",
                "curves": [
                    {"kind": "line_segment", "points_um": [[0, -half_width], outer_start]},
                    {
                        "kind": "circular_arc",
                        "points_um": [
                            outer_start,
                            [cx + outer_radius / sqrt(2), cy - outer_radius / sqrt(2)],
                            outer_end,
                        ],
                    },
                    {"kind": "line_segment", "points_um": [outer_end, inner_start]},
                    {
                        "kind": "circular_arc",
                        "points_um": [
                            inner_start,
                            [cx + inner_radius / sqrt(2), cy - inner_radius / sqrt(2)],
                            inner_end,
                        ],
                    },
                    {"kind": "line_segment", "points_um": [inner_end, [0, half_width]]},
                    {"kind": "line_segment", "points_um": [[0, half_width], [0, -half_width]]},
                ],
            }
        ],
    }
    component.info["model_source"] = "Synthetic public straight-to-circular strip"
    return component


__all__ = ["square_pad_capacitor", "circular_pad_capacitor", "straight_to_circular_strip"]
