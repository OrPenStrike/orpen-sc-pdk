"""Public flip-chip Xmon preview cell.

Independent parametric adaptation inspired by Kosen et al., *PRX Quantum* 5,
030350 (2024), https://doi.org/10.1103/PRXQuantum.5.030350, used under
CC BY 4.0, https://creativecommons.org/licenses/by/4.0/.
This is not an author-supplied mask. The neutral preview dimensions below are
not paper mask authority; the paper's 8 um die gap and 25 um pre-compression
indium diameter are retained as provenance metadata only.
"""

from math import isfinite

import gdsfactory as gf

from orpen_sc_pdk.cells.indium import indium_bump
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
    etch_layer: Layer,
    ground_mask_layer: Layer,
) -> gf.Component:
    """Return two equal crossed bars and their surrounding ground gap."""

    c = gf.Component()
    for size in ((length, width), (width, length)):
        c << gf.components.rectangle(size=size, layer=draw_layer, centered=True)
    for size in ((length + 2 * gap, width + 2 * gap), (width + 2 * gap, length + 2 * gap)):
        c << gf.components.rectangle(size=size, layer=ground_mask_layer, centered=True)
    return add_etch_for_component(
        component=c,
        draw_layer=draw_layer,
        mask_layer=ground_mask_layer,
        etch_layer=etch_layer,
    )


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
    etch_layer: Layer,
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
    return add_etch_for_component(
        component=c,
        draw_layer=draw_layer,
        mask_layer=ground_mask_layer,
        etch_layer=etch_layer,
    )


@gf.cell(tags=["qubits", "flip_chip"])
def kosen2024_flip_chip_xmon_qubit(
    qubit_pad_length: float = 320.0,
    qubit_pad_width: float = 40.0,
    qubit_gap: float = 20.0,
    coupling_electrode_to_qubit_distance: float = 20.0,
    coupling_electrode_gap: float = 10.0,
    coupling_electrode_insertion_length: float = 80.0,
    coupling_electrode_width: float = 16.0,
    coupling_electrode_port_length: float = 80.0,
    bump_ring_offset: float = 60.0,
    bump_ring_count_per_side: int = 4,
    indium_bump_size: float = 20.0,
    under_bump_size: float = 40.0,
    include_under_bump: bool = True,
    # Layers
    q_chip_draw_layer: Layer = LAYER.D1_BOTTOM_M1_DRAW,
    q_chip_etch_layer: Layer = LAYER.D1_BOTTOM_M1_ETCH,
    q_chip_ground_mask_layer: Layer = LAYER.D1_BOTTOM_GROUND_MASK,
    indium_bump_layer: Layer = LAYER.D0_D1_INDIUM_BUMP,
    under_bump_layer: Layer = LAYER.D0_D1_UNDER_BUMP,
) -> gf.Component:
    """Return a neutral-preview, four-port flip-chip Xmon coupling topology.

    ``qubit_pad_length`` and ``qubit_pad_width`` size both crossed bars together.
    The pad and four independent qubit-coupling electrodes share the Q-chip
    metal face. XY drive and readout geometry belong to the facing C-chip and
    are intentionally excluded. Defaults are neutral previews, not paper-mask
    authority.
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
        ("bump_ring_offset", bump_ring_offset),
        ("indium_bump_size", indium_bump_size),
        ("under_bump_size", under_bump_size),
    ):
        _check_positive(name, value)
    if (
        isinstance(bump_ring_count_per_side, bool)
        or not isinstance(bump_ring_count_per_side, int)
        or bump_ring_count_per_side < 2
    ):
        raise ValueError("bump_ring_count_per_side must be an integer of at least two.")
    if bump_ring_count_per_side % 2:
        raise ValueError(
            "bump_ring_count_per_side must be even to keep cardinal port corridors clear."
        )

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
        etch_layer=q_chip_etch_layer,
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
        etch_layer=q_chip_etch_layer,
        ground_mask_layer=q_chip_ground_mask_layer,
    )
    for name, angle in (("o1", 0), ("o2", -90), ("o3", 180), ("o4", 90)):
        electrode_ref = c << electrode
        electrode_ref.rotate(angle)
        c.add_port(name=name, port=electrode_ref.ports["o1"])

    outer_edge = (
        qubit_pad_length / 2
        + coupling_electrode_to_qubit_distance
        + coupling_electrode_width
        + coupling_electrode_port_length
    )
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

    c.info["topology"] = (
        "D1 Xmon cross with four independent D1 qubit-coupling electrodes and bump ring"
    )
    c.info["source_doi"] = "10.1103/PRXQuantum.5.030350"
    c.info["source_license"] = "CC BY 4.0"
    c.info["source_license_url"] = "https://creativecommons.org/licenses/by/4.0/"
    c.info["source_attribution"] = (
        "Independent parametric adaptation from Kosen et al.; "
        "not an author-supplied mask or endorsed implementation."
    )
    c.info["preview_default_provenance"] = (
        "Neutral public preview defaults; not paper mask authority."
    )
    c.info["paper_reported_die_gap_um"] = 8.0
    c.info["pdk_nominal_d0_d1_metal_face_gap_um"] = float(D0_D1_METAL_FACE_GAP_UM)
    c.info["paper_reported_indium_precompression_diameter_um"] = 25.0
    c.info["instantiated_indium_bump_size_um"] = float(indium_bump_size)
    c.info["instantiated_under_bump_size_um"] = float(under_bump_size)
    c.info["bump_count"] = 4 * bump_ring_count_per_side
    c.info["projected_q_chip_ground_between_pad_and_electrode_um"] = max(
        coupling_electrode_to_qubit_distance - qubit_gap, 0.0
    )
    c.info["ordered_port_names"] = ("o1", "o2", "o3", "o4")
    c.info["port_orientations_deg"] = {"o1": 90, "o2": 0, "o3": 270, "o4": 180}
    c.info["layers"] = {
        "q_chip_draw": tuple(int(value) for value in q_chip_draw_layer),
        "q_chip_etch": tuple(int(value) for value in q_chip_etch_layer),
        "q_chip_ground_mask": tuple(int(value) for value in q_chip_ground_mask_layer),
    }

    return c


__all__ = ["kosen2024_flip_chip_xmon_qubit"]
