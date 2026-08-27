"""Public flip-chip Xmon preview cell.

Independent parametric adaptation inspired by Kosen et al., *PRX Quantum* 5,
030350 (2024), https://doi.org/10.1103/PRXQuantum.5.030350, used under
CC BY 4.0, https://creativecommons.org/licenses/by/4.0/.
This is not an author-supplied mask. The simulation-informed public preview
dimensions below are not paper-mask authority. The 8 um metal-face gap is a
nominal public design value rather than a process validation limit; the paper's
8 um die gap and 25 um pre-compression indium diameter remain provenance.
"""

from math import cos, isfinite, radians, sin

import gdsfactory as gf

from orpen_sc_pdk.cells.indium import indium_bump
from orpen_sc_pdk.cells.junction import manhattan_style_junction
from orpen_sc_pdk.helpers.layout import add_etch_for_component
from orpen_sc_pdk.tech import D0_D1_METAL_FACE_GAP_UM, LAYER, Layer


def _check_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive, got {value!r}.")


@gf.cell
def _xmon_qubit_pad(
    length: float,
    width: float,
    gap: float,
    draw_layer: Layer,
    ground_mask_layer: Layer,
) -> gf.Component:
    """Return two equal crossed bars and their surrounding ground-gap mask."""

    c = gf.Component()
    for size in ((length, width), (width, length)):
        c << gf.components.rectangle(size=size, layer=draw_layer, centered=True)
    for size in ((length + 2 * gap, width + 2 * gap), (width + 2 * gap, length + 2 * gap)):
        c << gf.components.rectangle(size=size, layer=ground_mask_layer, centered=True)
    return c


@gf.cell
def _xmon_coupling_electrode(
    qubit_pad_length: float,
    qubit_pad_width: float,
    distance_to_qubit: float,
    gap: float,
    width: float,
    insertion_length: float,
    port_length: float,
    draw_layer: Layer,
    ground_mask_layer: Layer,
) -> gf.Component:
    """Return the north-facing U electrode used on each side of the Xmon."""

    c = gf.Component()
    half_pad_length = qubit_pad_length / 2
    half_pad_width = qubit_pad_width / 2
    inner_x = half_pad_width + distance_to_qubit
    outer_x = inner_x + width
    bar_y = half_pad_length + distance_to_qubit
    leg_y = half_pad_length - insertion_length
    outer_edge = bar_y + width + port_length

    top_bar = c << gf.components.rectangle(size=(2 * outer_x, width), layer=draw_layer)
    top_bar.dmove((-outer_x, bar_y))
    for x in (-outer_x, inner_x):
        leg = c << gf.components.rectangle(
            size=(width, insertion_length + distance_to_qubit + width),
            layer=draw_layer,
        )
        leg.dmove((x, leg_y))
    lead = c << gf.components.rectangle(size=(width, port_length), layer=draw_layer)
    lead.dmove((-width / 2, bar_y + width))

    # The qubit gap owns the U opening.  The electrode gap clears only the
    # outside of the U and its outgoing coupler line.
    top_mask = c << gf.components.rectangle(
        size=(2 * (outer_x + gap), width + gap), layer=ground_mask_layer
    )
    top_mask.dmove((-outer_x - gap, bar_y))
    left_leg_mask = c << gf.components.rectangle(
        size=(width + gap, insertion_length + distance_to_qubit + width + 2 * gap),
        layer=ground_mask_layer,
    )
    left_leg_mask.dmove((-outer_x - gap, leg_y - gap))
    right_leg_mask = c << gf.components.rectangle(
        size=(width + gap, insertion_length + distance_to_qubit + width + 2 * gap),
        layer=ground_mask_layer,
    )
    right_leg_mask.dmove((inner_x, leg_y - gap))
    lead_mask = c << gf.components.rectangle(
        size=(width + 2 * gap, port_length), layer=ground_mask_layer
    )
    lead_mask.dmove((-width / 2 - gap, bar_y + width))

    c.add_port(
        name="o1",
        center=(0, outer_edge),
        width=width,
        orientation=90,
        layer=draw_layer,
        port_type="electrical",
    )
    return c


@gf.cell(tags=["qubits", "flip_chip"])
def kosen2024_flip_chip_xmon_qubit(
    qubit_pad_length: float = 300.0,
    qubit_pad_width: float = 24.65,
    qubit_gap: float = 20.0,
    coupling_electrode_to_qubit_distance: float = 20.0,
    coupling_electrode_gap: float = 10.0,
    coupling_electrode_insertion_length: float = 60.0,
    coupling_electrode_width: float = 16.0,
    coupling_electrode_port_length: float = 80.0,
    junction_width: float = 0.09,
    junction_length: float = 5.0,
    junction_arm_width: float = 2.0,
    bump_ring_offset: float = 60.0,
    bump_ring_count_per_side: int = 4,
    indium_bump_size: float = 20.0,
    under_bump_size: float = 40.0,
    include_under_bump: bool = True,
    # Layers
    q_chip_draw_layer: Layer = LAYER.D1_BOTTOM_M1_DRAW,
    q_chip_etch_layer: Layer = LAYER.D1_BOTTOM_M1_ETCH,
    q_chip_ground_mask_layer: Layer = LAYER.D1_BOTTOM_GROUND_MASK,
    junction_draw_layer: Layer = LAYER.D1_BOTTOM_JJ_DRAW,
    junction_sim_port_layer: Layer = LAYER.D1_BOTTOM_SIM_BOUNDARY,
    indium_bump_layer: Layer = LAYER.D0_D1_INDIUM_BUMP,
    under_bump_layer: Layer = LAYER.D0_D1_UNDER_BUMP,
) -> gf.Component:
    """Return a public-preview, four-port flip-chip Xmon coupling topology.

    ``qubit_pad_length`` and ``qubit_pad_width`` size both crossed bars together.
    The pad and four independent qubit-coupling electrodes share the Q-chip
    metal face. XY drive and readout geometry belong to the facing C-chip and
    are intentionally excluded.
    The default fixed-frequency topology has one lower-left D1 Manhattan
    junction joining pad to ground through two short M1 arms.
    A centered D0 ground-mask opening is derived from the four coupler-port
    extents. Routing attached to those ports owns continuation of that opening.

    Source: S. Kosen et al., "Signal Crosstalk in a Flip-Chip Quantum
    Processor," PRX Quantum 5, 030350 (2024),
    https://doi.org/10.1103/PRXQuantum.5.030350. The published work is available
    under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), which
    requires attribution and identification of changes. This cell is an
    independent parametric adaptation, not an author-supplied mask or an
    endorsed implementation. Its defaults are public simulation-informed
    preview values, not paper-mask dimensions.
    """

    for name, value in (
        ("qubit_pad_length", qubit_pad_length),
        ("qubit_pad_width", qubit_pad_width),
        ("qubit_gap", qubit_gap),
        ("coupling_electrode_to_qubit_distance", coupling_electrode_to_qubit_distance),
        ("coupling_electrode_gap", coupling_electrode_gap),
        ("coupling_electrode_insertion_length", coupling_electrode_insertion_length),
        ("coupling_electrode_width", coupling_electrode_width),
        ("coupling_electrode_port_length", coupling_electrode_port_length),
        ("junction_width", junction_width),
        ("junction_length", junction_length),
        ("junction_arm_width", junction_arm_width),
        ("bump_ring_offset", bump_ring_offset),
        ("indium_bump_size", indium_bump_size),
        ("under_bump_size", under_bump_size),
    ):
        _check_positive(name, value)
    if isinstance(bump_ring_count_per_side, bool) or not isinstance(bump_ring_count_per_side, int):
        raise ValueError("bump_ring_count_per_side must be an integer.")
    if bump_ring_count_per_side < 0:
        raise ValueError("bump_ring_count_per_side must be non-negative.")
    if bump_ring_count_per_side not in {0} and (
        bump_ring_count_per_side < 2 or bump_ring_count_per_side % 2
    ):
        raise ValueError("bump_ring_count_per_side must be 0 or an even integer of at least two.")

    if qubit_pad_length <= qubit_pad_width:
        raise ValueError("qubit_pad_length must exceed qubit_pad_width.")
    if coupling_electrode_insertion_length >= (
        (qubit_pad_length - qubit_pad_width) / 2
        - coupling_electrode_to_qubit_distance
        - coupling_electrode_width
    ):
        raise ValueError(
            "coupling_electrode_insertion_length leaves insufficient corner clearance."
        )
    c = gf.Component()
    c << _xmon_qubit_pad(
        length=qubit_pad_length,
        width=qubit_pad_width,
        gap=qubit_gap,
        draw_layer=q_chip_draw_layer,
        ground_mask_layer=q_chip_ground_mask_layer,
    )

    electrode = _xmon_coupling_electrode(
        qubit_pad_length=qubit_pad_length,
        qubit_pad_width=qubit_pad_width,
        distance_to_qubit=coupling_electrode_to_qubit_distance,
        gap=coupling_electrode_gap,
        width=coupling_electrode_width,
        insertion_length=coupling_electrode_insertion_length,
        port_length=coupling_electrode_port_length,
        draw_layer=q_chip_draw_layer,
        ground_mask_layer=q_chip_ground_mask_layer,
    )
    for name, angle in (("o1", 0), ("o2", -90), ("o3", 180), ("o4", 90)):
        electrode_ref = c << electrode
        electrode_ref.rotate(angle)
        c.add_port(name=name, port=electrode_ref.ports["o1"])

    half_pad_length = qubit_pad_length / 2
    half_pad_width = qubit_pad_width / 2
    left_inner_segment_start = -half_pad_length + coupling_electrode_insertion_length
    central_cross_edge = -half_pad_width
    pad_lower_edge = -half_pad_width
    outer_gap_lower_edge = pad_lower_edge - qubit_gap
    junction_lumped_center = (
        (left_inner_segment_start + central_cross_edge) / 2,
        (pad_lower_edge + outer_gap_lower_edge) / 2,
    )
    junction = manhattan_style_junction(
        width=junction_width,
        length=junction_length,
        open_side="left-bottom",
        draw_layer=junction_draw_layer,
        sim_port_layer=junction_sim_port_layer,
    )
    junction_ref = c << junction
    junction_ref.dmirror_y(0)
    junction_ref.dmove(
        (
            junction_lumped_center[0] - junction_ref.ports["o_junction_lumped"].center[0],
            junction_lumped_center[1] - junction_ref.ports["o_junction_lumped"].center[1],
        )
    )
    c.add_port(name="o_junction_lumped", port=junction_ref.ports["o_junction_lumped"])

    up_arm_start = junction_ref.ports["o_arm2"].center
    up_arm_head = c << gf.components.circle(
        radius=junction_arm_width / 2,
        layer=q_chip_draw_layer,
    )
    up_arm_head.dmove(up_arm_start)
    up_arm_end = pad_lower_edge + junction_arm_width
    c.add_polygon(
        [
            (up_arm_start[0] - junction_arm_width / 2, up_arm_start[1]),
            (up_arm_start[0] + junction_arm_width / 2, up_arm_start[1]),
            (up_arm_start[0] + junction_arm_width / 2, up_arm_end),
            (up_arm_start[0] - junction_arm_width / 2, up_arm_end),
        ],
        layer=q_chip_draw_layer,
    )
    lower_arm_start = junction_ref.ports["o_arm1"].center
    lower_arm_head = c << gf.components.circle(
        radius=junction_arm_width / 2,
        layer=q_chip_draw_layer,
    )
    lower_arm_head.dmove(lower_arm_start)
    lower_arm_end = outer_gap_lower_edge - junction_arm_width
    c.add_polygon(
        [
            (lower_arm_start[0] - junction_arm_width / 2, lower_arm_end),
            (lower_arm_start[0] + junction_arm_width / 2, lower_arm_end),
            (lower_arm_start[0] + junction_arm_width / 2, lower_arm_start[1]),
            (lower_arm_start[0] - junction_arm_width / 2, lower_arm_start[1]),
        ],
        layer=q_chip_draw_layer,
    )

    c = add_etch_for_component(
        component=c,
        draw_layer=q_chip_draw_layer,
        mask_layer=q_chip_ground_mask_layer,
        etch_layer=q_chip_etch_layer,
    )

    outer_edge = (
        qubit_pad_length / 2
        + coupling_electrode_to_qubit_distance
        + coupling_electrode_width
        + coupling_electrode_port_length
    )
    d0_ground_opening_side = 2 * outer_edge
    c << gf.components.rectangle(
        size=(d0_ground_opening_side, d0_ground_opening_side),
        layer=LAYER.D0_TOP_GROUND_MASK,
        centered=True,
    )
    if bump_ring_count_per_side:
        bump_footprint_size = (
            max(indium_bump_size, under_bump_size) if include_under_bump else indium_bump_size
        )
        bump_center_offset = outer_edge + bump_ring_offset + bump_footprint_size / 2
        if bump_center_offset / bump_ring_count_per_side <= bump_footprint_size:
            raise ValueError("bump ring is too dense for its offset and bump footprint.")
        bump = indium_bump(
            indium_bump_size=indium_bump_size,
            under_bump_size=under_bump_size,
            indium_bump_layer=indium_bump_layer,
            under_bump_layer=under_bump_layer,
            include_under_bump=include_under_bump,
        )
        side_positions = tuple(
            bump_center_offset * (-1 + (2 * index + 1) / bump_ring_count_per_side)
            for index in range(bump_ring_count_per_side)
        )
        for coordinate in side_positions:
            for center in (
                (coordinate, bump_center_offset),
                (bump_center_offset, coordinate),
                (coordinate, -bump_center_offset),
                (-bump_center_offset, coordinate),
            ):
                bump_ref = c << bump
                bump_ref.dmove(center)

    # Keep the paper provenance on the exported component as well as in the
    # docstring so downstream GDSFactory consumers do not lose the attribution.
    topology_suffix = "and bump ring" if bump_ring_count_per_side else "without a bump ring"
    c.info["topology"] = (
        "D1 Xmon cross with four independent D1 qubit-coupling electrodes, "
        f"one Manhattan junction, {topology_suffix}"
    )
    c.info["source_doi"] = "10.1103/PRXQuantum.5.030350"
    c.info["source_license"] = "CC BY 4.0"
    c.info["source_license_url"] = "https://creativecommons.org/licenses/by/4.0/"
    c.info["source_attribution"] = (
        "Independent parametric adaptation from Kosen et al.; "
        "not an author-supplied mask or endorsed implementation."
    )
    c.info["preview_default_provenance"] = (
        "Public simulation-informed preview defaults; not paper mask authority."
    )
    c.info["d0_top_ground_opening_side_um"] = float(d0_ground_opening_side)
    c.info["paper_reported_die_gap_um"] = 8.0
    c.info["pdk_nominal_d0_d1_metal_face_gap_um"] = float(D0_D1_METAL_FACE_GAP_UM)
    c.info["paper_reported_indium_precompression_diameter_um"] = 25.0
    c.info["instantiated_indium_bump_size_um"] = float(indium_bump_size)
    c.info["instantiated_under_bump_size_um"] = float(under_bump_size)
    c.info["bump_count"] = 4 * bump_ring_count_per_side
    c.info["junction_topology"] = "single fixed-frequency lower-left Manhattan junction"
    c.info["junction_lumped_center_um"] = tuple(float(value) for value in junction_lumped_center)
    c.info["junction_width_um"] = float(junction_width)
    c.info["junction_length_um"] = float(junction_length)
    c.info["junction_arm_width_um"] = float(junction_arm_width)
    c.info["junction_lumped_port_name"] = "o_junction_lumped"
    c.info["projected_q_chip_ground_between_pad_and_electrode_um"] = max(
        coupling_electrode_to_qubit_distance - qubit_gap, 0.0
    )
    c.info["ordered_port_names"] = ("o1", "o2", "o3", "o4", "o_junction_lumped")
    c.info["port_orientations_deg"] = {
        "o1": 90,
        "o2": 0,
        "o3": 270,
        "o4": 180,
        "o_junction_lumped": float(c.ports["o_junction_lumped"].orientation),
    }
    c.info["layers"] = {
        "q_chip_draw": tuple(int(value) for value in q_chip_draw_layer),
        "q_chip_etch": tuple(int(value) for value in q_chip_etch_layer),
        "q_chip_ground_mask": tuple(int(value) for value in q_chip_ground_mask_layer),
        "c_chip_ground_mask": tuple(int(value) for value in LAYER.D0_TOP_GROUND_MASK),
        "junction_draw": tuple(int(value) for value in junction_draw_layer),
        "junction_sim_port": tuple(int(value) for value in junction_sim_port_layer),
    }
    # Component semantics describe nets and topology only. Material, layer,
    # fabrication, host-volume, and 3D-integration facts remain in the PDK stack.
    d1_draw_layer = tuple(int(value) for value in q_chip_draw_layer)
    d1_ground_mask_layer = tuple(int(value) for value in q_chip_ground_mask_layer)
    coupler_selectors = []
    for index, port_name in enumerate(("o1", "o2", "o3", "o4"), 1):
        port = c.ports[port_name]
        angle = radians(float(port.orientation))
        distance = float(port.width) / 2
        coupler_selectors.append(
            (
                f"D1_COUPLER_{index}",
                f"coupler_{index}",
                (
                    float(port.center[0]) - distance * cos(angle),
                    float(port.center[1]) - distance * sin(angle),
                ),
                f"authored component port {port_name}",
            )
        )
    c.info["component_semantics"] = {
        "schema_version": 1,
        "conductor_regions": [
            {
                "semantic_id": "D0_TOP_GROUND_PLANE",
                "level": "D0_TOP_M1",
                "gds_layer": tuple(int(value) for value in LAYER.D0_TOP_GROUND_MASK),
                "net_id": "Ground",
                "metadata": {
                    "equipotential_id": "Ground",
                },
            },
            {
                "semantic_id": "D1_BOTTOM_GROUND_PLANE",
                "level": "D1_BOTTOM_M1",
                "gds_layer": d1_ground_mask_layer,
                "net_id": "Ground",
                "geometry": {
                    "mask_layer": d1_ground_mask_layer,
                    "include_layer": d1_draw_layer,
                    "include_selector_points_um": [
                        (
                            float(lower_arm_start[0]),
                            float((lower_arm_start[1] + lower_arm_end) / 2),
                        )
                    ],
                },
                "metadata": {
                    "source_selector": "authored lower junction ground-arm interior",
                    "equipotential_id": "Ground",
                },
            },
            *[
                {
                    "semantic_id": semantic_id,
                    "level": "D1_BOTTOM_M1",
                    "gds_layer": d1_draw_layer,
                    "net_id": net_id,
                    "geometry": {
                        "geometry_source": "gds_polygon",
                        "selector_point_um": point,
                    },
                    "metadata": {
                        "semantic_group_id": "D1_BOTTOM_SIGNAL_GROUP",
                        "source_selector": source,
                    },
                }
                for semantic_id, net_id, point, source in [
                    (
                        "D1_XMON_PAD",
                        "xmon_pad",
                        (0.0, 0.0),
                        "public topology anchor (0, 0)",
                    ),
                    *coupler_selectors,
                ]
            ],
            {
                "semantic_id": "D0_D1_INDIUM_BUMP",
                "level": "D0_D1_INDIUM_BUMP",
                "gds_layer": tuple(int(value) for value in indium_bump_layer),
                "net_id": "Ground",
                "metadata": {
                    "semantic_group_id": "D0_D1_INDIUM_BUMP",
                    "source_kind": "authored",
                    "source_semantic_id": "D0_D1_INDIUM_BUMP",
                    "equipotential_id": "Ground",
                    "owner_semantic_ids": (
                        "D0_TOP_GROUND_PLANE",
                        "D1_BOTTOM_GROUND_PLANE",
                    ),
                },
            },
        ],
        "metadata": {
            "component_contract": ("kosen2024_flip_chip_xmon_qubit public zero-argument cell"),
            "signal_group": "D1_BOTTOM_SIGNAL_GROUP",
        },
    }

    return c


__all__ = ["kosen2024_flip_chip_xmon_qubit"]
