"""Public flip-chip Xmon preview cell.

Independent parametric adaptation inspired by Kosen et al., *PRX Quantum* 5,
030350 (2024), https://doi.org/10.1103/PRXQuantum.5.030350 (CC BY 4.0).
This is not an author-supplied mask. The neutral preview dimensions below are
not paper mask authority; the paper's 8 um die gap and 25 um pre-compression
indium diameter are retained as provenance metadata only.
"""

from math import isfinite

import gdsfactory as gf

from orpen_sc_pdk.cells.indium import indium_bump
from orpen_sc_pdk.tech import D0_D1_METAL_FACE_GAP_UM, LAYER, Layer


def _check_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive, got {value!r}.")


@gf.cell
def _xmon_coupling_electrode(
    qubit_arm_length: float,
    qubit_arm_width: float,
    coupling_gap: float,
    electrode_width: float,
    electrode_wrap_depth: float,
    port_lead_length: float,
    layer: Layer,
) -> gf.Component:
    """Return the north-facing U electrode used on each side of the Xmon."""

    c = gf.Component()
    half_arm_width = qubit_arm_width / 2
    inner_x = half_arm_width + coupling_gap
    outer_x = inner_x + electrode_width
    bar_y = qubit_arm_length + coupling_gap

    top_bar = c << gf.components.rectangle(size=(2 * outer_x, electrode_width), layer=layer)
    top_bar.dmove((-outer_x, bar_y))

    for x in (-outer_x, inner_x):
        leg = c << gf.components.rectangle(
            size=(electrode_width, electrode_wrap_depth + coupling_gap + electrode_width),
            layer=layer,
        )
        leg.dmove((x, qubit_arm_length - electrode_wrap_depth))

    lead = c << gf.components.rectangle(size=(electrode_width, port_lead_length), layer=layer)
    lead.dmove((-electrode_width / 2, bar_y + electrode_width))
    c.add_port(
        name="o1",
        center=(0, bar_y + electrode_width + port_lead_length),
        width=electrode_width,
        orientation=90,
        layer=layer,
        port_type="electrical",
    )
    return c


@gf.cell(tags=["qubits", "flip_chip"])
def kosen2024_flip_chip_xmon_qubit(
    qubit_arm_length: float = 160.0,
    qubit_arm_width: float = 40.0,
    coupling_gap: float = 20.0,
    electrode_width: float = 16.0,
    electrode_wrap_depth: float = 80.0,
    port_lead_length: float = 80.0,
    bump_ring_offset: float = 60.0,
    bump_ring_count_per_side: int = 4,
    indium_bump_size: float = 20.0,
    under_bump_size: float = 40.0,
    include_under_bump: bool = True,
    # Layers
    q_chip_draw_layer: Layer = LAYER.D1_BOTTOM_M1_DRAW,
    c_chip_draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    indium_bump_layer: Layer = LAYER.D0_D1_INDIUM_BUMP,
    under_bump_layer: Layer = LAYER.D0_D1_UNDER_BUMP,
) -> gf.Component:
    """Return a neutral-preview, four-port flip-chip Xmon coupling topology.

    ``qubit_arm_length`` is the center-to-end extent of each cross arm. All
    dimensions except the reused PDK bump stack are neutral preview defaults,
    not fabrication dimensions or paper-mask authority.
    """

    for name, value in (
        ("qubit_arm_length", qubit_arm_length),
        ("qubit_arm_width", qubit_arm_width),
        ("coupling_gap", coupling_gap),
        ("electrode_width", electrode_width),
        ("electrode_wrap_depth", electrode_wrap_depth),
        ("port_lead_length", port_lead_length),
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

    half_arm_width = qubit_arm_width / 2
    if qubit_arm_length <= half_arm_width:
        raise ValueError("qubit_arm_length must exceed qubit_arm_width / 2.")
    if electrode_wrap_depth >= (qubit_arm_length - half_arm_width - coupling_gap - electrode_width):
        raise ValueError(
            "electrode_wrap_depth leaves insufficient corner clearance between electrodes."
        )

    c = gf.Component()
    qubit_cross = [
        (-half_arm_width, -qubit_arm_length),
        (half_arm_width, -qubit_arm_length),
        (half_arm_width, -half_arm_width),
        (qubit_arm_length, -half_arm_width),
        (qubit_arm_length, half_arm_width),
        (half_arm_width, half_arm_width),
        (half_arm_width, qubit_arm_length),
        (-half_arm_width, qubit_arm_length),
        (-half_arm_width, half_arm_width),
        (-qubit_arm_length, half_arm_width),
        (-qubit_arm_length, -half_arm_width),
        (-half_arm_width, -half_arm_width),
    ]
    c.add_polygon(qubit_cross, layer=q_chip_draw_layer)

    electrode = _xmon_coupling_electrode(
        qubit_arm_length=qubit_arm_length,
        qubit_arm_width=qubit_arm_width,
        coupling_gap=coupling_gap,
        electrode_width=electrode_width,
        electrode_wrap_depth=electrode_wrap_depth,
        port_lead_length=port_lead_length,
        layer=c_chip_draw_layer,
    )
    for name, angle in (("o1", 0), ("o2", -90), ("o3", 180), ("o4", 90)):
        electrode_ref = c << electrode
        electrode_ref.rotate(angle)
        c.add_port(name=name, port=electrode_ref.ports["o1"])

    outer_edge = qubit_arm_length + coupling_gap + electrode_width + port_lead_length
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

    c.info["topology"] = "D1 Xmon cross with four independent D0 U electrodes and bump ring"
    c.info["source_doi"] = "10.1103/PRXQuantum.5.030350"
    c.info["source_license"] = "CC BY 4.0"
    c.info["source_attribution"] = "Independent parametric adaptation; not an author-supplied mask."
    c.info["preview_default_provenance"] = (
        "Neutral public preview defaults; not paper mask authority."
    )
    c.info["paper_reported_die_gap_um"] = 8.0
    c.info["pdk_nominal_d0_d1_metal_face_gap_um"] = float(D0_D1_METAL_FACE_GAP_UM)
    c.info["paper_reported_indium_precompression_diameter_um"] = 25.0
    c.info["instantiated_indium_bump_size_um"] = float(indium_bump_size)
    c.info["instantiated_under_bump_size_um"] = float(under_bump_size)
    c.info["bump_count"] = 4 * bump_ring_count_per_side
    c.info["ordered_port_names"] = ("o1", "o2", "o3", "o4")
    c.info["port_orientations_deg"] = {"o1": 90, "o2": 0, "o3": 270, "o4": 180}
    c.info["layers"] = {
        "q_chip_draw": tuple(int(value) for value in q_chip_draw_layer),
        "c_chip_draw": tuple(int(value) for value in c_chip_draw_layer),
    }

    return c


__all__ = ["kosen2024_flip_chip_xmon_qubit"]
