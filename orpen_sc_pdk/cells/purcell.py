"""Public Purcell-filter cells."""

from __future__ import annotations

from math import isfinite, pi

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec, Layer

from orpen_sc_pdk.tech import LAYER


def _add_open_end_cap(
    component: gf.Component,
    end_port: gf.Port,
    etch_width: float,
    cpw_width: float,
    etch_layer: Layer,
    mask_layer: Layer,
    ground_mask_width: float,
) -> gf.ComponentReference:
    """Add OrPen-style open-end CPW cap aligned to ``end_port``."""

    open_etch_comp = gf.components.rectangle(
        size=(etch_width, cpw_width + 2 * etch_width),
        layer=etch_layer,
        centered=True,
        port_type="optical",
        port_orientations=(0, 180),
    )
    open_mask_comp = gf.components.rectangle(
        size=(etch_width, ground_mask_width),
        layer=mask_layer,
        centered=True,
        port_type="optical",
        port_orientations=(0, 180),
    )
    open_etch_ref = component << open_etch_comp
    open_mask_ref = component << open_mask_comp
    port_name = "o2" if end_port.orientation == 180 else "o1"
    open_etch_ref.connect(
        port_name,
        end_port,
        allow_width_mismatch=True,
        allow_layer_mismatch=True,
    )
    open_mask_ref.connect(
        port_name,
        end_port,
        allow_width_mismatch=True,
        allow_layer_mismatch=True,
    )
    return open_etch_ref


def _folded_path(
    component: gf.Component,
    start_port: gf.Port,
    cpw_length: float,
    arc_angles: tuple[float, ...],
    cpw_radius: float,
    cross_section: object,
    connection_authoring: str = "MTL_to_IDC",
) -> tuple[gf.Port, dict[str, object]]:
    """Add a folded CPW arm and return its free/facing port plus simple geometry receipt."""

    if start_port.orientation not in {0, 180}:
        raise ValueError(
            "Start ports for folded arms must be oriented east or west. "
            f"Got {start_port.orientation!r}."
        )
    if len(arc_angles) == 0:
        raise ValueError("folded path requires at least one arc angle")
    if any(not isfinite(value) for value in (cpw_length, cpw_radius, *arc_angles)):
        raise ValueError("Path geometry values must be finite.")
    if cpw_radius <= 0:
        raise ValueError(f"cpw_radius must be positive, got {cpw_radius!r}.")
    if connection_authoring not in {"MTL_to_IDC", "IDC_to_MTL"}:
        raise ValueError(
            "connection_authoring must be 'MTL_to_IDC' or 'IDC_to_MTL', "
            f"got {connection_authoring!r}."
        )

    arc_total_length = sum(abs(angle) for angle in arc_angles) / 360.0 * 2 * pi * cpw_radius

    if len(arc_angles) == 2:
        expected_straight_segments = 2
    elif len(arc_angles) == 5:
        expected_straight_segments = 4
    else:
        raise ValueError("Unsupported path complexity for this cell. Use 2 or 5 bends only.")

    remaining_straight_length = cpw_length - arc_total_length
    if remaining_straight_length <= 0:
        raise ValueError(
            "Each folded arm requires positive straight segments. "
            f"Got cpw_length={cpw_length!r}, arc_total_length={arc_total_length!r}, "
            f"cpw_radius={cpw_radius!r}."
        )

    max_transverse = 2 * cpw_radius
    if len(arc_angles) == 2:
        transverse_length = min(max_transverse, remaining_straight_length * 0.5)
        longitudinal_length = remaining_straight_length - transverse_length
        if longitudinal_length <= 0:
            raise ValueError(
                "Each folded short path requires a non-zero terminal straight segment. "
                f"Got cpw_length={cpw_length!r}, arc_total_length={arc_total_length!r}, "
                f"cpw_radius={cpw_radius!r}."
            )
        straight_lengths = [transverse_length, longitudinal_length]
    else:
        transverse_length = min(max_transverse, remaining_straight_length / 4)
        longitudinal_length = (remaining_straight_length - 2 * transverse_length) / 2
        if longitudinal_length <= 0:
            raise ValueError(
                "Each folded open path requires non-zero longitudinal straight segments. "
                f"Got cpw_length={cpw_length!r}, arc_total_length={arc_total_length!r}, "
                f"cpw_radius={cpw_radius!r}."
            )
        if connection_authoring == "IDC_to_MTL":
            straight_lengths = [
                longitudinal_length,
                transverse_length,
                longitudinal_length,
                transverse_length,
            ]
        else:
            straight_lengths = [
                transverse_length,
                longitudinal_length,
                transverse_length,
                longitudinal_length,
            ]

    if any(straight <= 0 for straight in straight_lengths):
        raise ValueError(
            "Each folded path requires positive straight segments after compact allocation. "
            f"Computed segments={straight_lengths!r}."
        )

    if len(straight_lengths) != expected_straight_segments:
        raise AssertionError("Internal straight-segment accounting is broken.")

    arm_path = gf.Path()
    for index, angle in enumerate(arc_angles):
        arm_path += gf.path.arc(radius=cpw_radius, angle=angle)
        if index < len(straight_lengths):
            arm_path += gf.path.straight(straight_lengths[index])

    arm_realized_length = float(arm_path.length())
    arm_ref = component << gf.path.extrude(arm_path, cross_section=cross_section)
    if connection_authoring == "MTL_to_IDC":
        connect_port_name = "o1"
        free_port_name = "o2"
    else:
        connect_port_name = "o2"
        free_port_name = "o1"
    arm_ref.connect(connect_port_name, start_port)
    free_port = arm_ref.ports[free_port_name]
    return free_port, {
        "declared_length_um": float(cpw_length),
        "realized_length_um": arm_realized_length,
        "straight_segment_length_um": tuple(float(value) for value in straight_lengths),
        "authored_direction": connection_authoring,
        "local_turn_sequence": tuple("L" if value > 0 else "R" for value in arc_angles),
        "bend_count": len(arc_angles),
        "bend_angles_deg": tuple(float(value) for value in arc_angles),
        "connection_port": {
            "name": str(connect_port_name),
            "x": float(arm_ref.ports[connect_port_name].x),
            "y": float(arm_ref.ports[connect_port_name].y),
            "orientation": float(arm_ref.ports[connect_port_name].orientation),
        },
        "free_port": {
            "name": str(free_port_name),
            "x": float(free_port.x),
            "y": float(free_port.y),
            "orientation": float(free_port.orientation),
        },
        "connected_to": str(start_port.name),
    }


@gf.cell(tags=["elements"])
def capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators(
    readout_open_length: float = 2539.512388,
    shared_short_length: float = 2270.302789,
    coupled_length: float = 311.256590,
    filter_open_length: float = 2319.359517,
    cpw_radius: float = 100.0,
    single_cpw_xs: CrossSectionSpec = "cpw_6_7_6",
    coupled_cpw_xs: CrossSectionSpec = "coupled_cpw_w7_s6_d3",
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    idc_finger_length: float = 59.924760,
) -> gf.Component:
    """Return an individual readout/coupled Purcell-filter topology sharing one coupled MTL section.

    Public preview defaults:
    readout_open_length=2539.512388, shared_short_length=2270.302789,
    coupled_length=311.256590,
    filter_open_length=2319.359517, idc_finger_length=59.924760.
    """

    for name, value in (
        ("readout_open_length", readout_open_length),
        ("shared_short_length", shared_short_length),
        ("coupled_length", coupled_length),
        ("filter_open_length", filter_open_length),
        ("idc_finger_length", idc_finger_length),
        ("cpw_radius", cpw_radius),
    ):
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive, got {value!r}.")

    single_xs = gf.get_cross_section(
        single_cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=cpw_radius,
    )
    coupled_xs = gf.get_cross_section(
        coupled_cpw_xs,
        trace_names=("p", "r"),
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=cpw_radius,
    )

    c = gf.Component()
    c.info["topology"] = (
        "capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators"
    )
    c.info["readout_open_length_um"] = float(readout_open_length)
    c.info["shared_short_length_um"] = float(shared_short_length)
    c.info["coupled_length_um"] = float(coupled_length)
    c.info["filter_open_length_um"] = float(filter_open_length)
    c.info["idc_finger_length_um"] = float(idc_finger_length)
    c.info["cpw_radius_um"] = float(cpw_radius)
    c.info["ordered_port_names"] = ("o_readout_open", "o_feedline_coupling")

    shared_short_length = float(shared_short_length)

    cpw_width = float(single_xs.width)
    etch_section = single_xs["cpw_etch_pos"]
    ground_mask_section = single_xs["cpw_ground_mask"]
    c.info["draw_layer"] = tuple(int(value) for value in single_xs["cpw_draw"].layer)
    c.info["etch_layer"] = tuple(int(value) for value in etch_section.layer)
    c.info["ground_mask_layer"] = tuple(int(value) for value in ground_mask_section.layer)
    c.info["ground_mask_width"] = float(ground_mask_section.width)

    c.info["readout_trace"] = "r"
    c.info["filter_trace"] = "p"

    shared_coupled_length = float(coupled_length)
    coupled = c << gf.get_component(
        "n_trace_mtl_section",
        length=shared_coupled_length,
        cross_section=coupled_xs,
    )

    readout_short, readout_short_info = _folded_path(
        component=c,
        start_port=coupled.ports["r_o2"],
        cpw_length=shared_short_length,
        arc_angles=(90.0, -90.0),
        cpw_radius=cpw_radius,
        cross_section=single_xs,
    )
    filter_short, filter_short_info = _folded_path(
        component=c,
        start_port=coupled.ports["p_o2"],
        cpw_length=shared_short_length,
        arc_angles=(-90.0, 90.0),
        cpw_radius=cpw_radius,
        cross_section=single_xs,
    )
    filter_open, filter_open_info = _folded_path(
        component=c,
        start_port=coupled.ports["p_o1"],
        cpw_length=filter_open_length,
        arc_angles=(90.0, -90.0, -90.0, 90.0, -90.0),
        cpw_radius=cpw_radius,
        cross_section=single_xs,
        connection_authoring="IDC_to_MTL",
    )
    readout_open, readout_open_info = _folded_path(
        component=c,
        start_port=coupled.ports["r_o1"],
        cpw_length=readout_open_length,
        arc_angles=(-90.0, 90.0, 90.0, -90.0, 90.0),
        cpw_radius=cpw_radius,
        cross_section=single_xs,
        connection_authoring="IDC_to_MTL",
    )

    c.info["short_termination"] = "cpw_gap_stop"
    c.info["path_geometry"] = {
        "mtl_instance": {
            "length_um": shared_coupled_length,
            "r_ports": ("r_o1", "r_o2"),
            "p_ports": ("p_o1", "p_o2"),
            "ports": {
                "r_o1": tuple(coupled.ports["r_o1"].center),
                "r_o2": tuple(coupled.ports["r_o2"].center),
                "p_o1": tuple(coupled.ports["p_o1"].center),
                "p_o2": tuple(coupled.ports["p_o2"].center),
            },
        },
        "readout_short": readout_short_info,
        "filter_short": filter_short_info,
        "readout_open": readout_open_info,
        "filter_open": filter_open_info,
        "short_length_um": shared_short_length,
        "idc_outer_port": {
            "name": "o_feedline_coupling",
            "orientation": 270,
        },
    }

    readout_open_cap = _add_open_end_cap(
        component=c,
        end_port=readout_open,
        etch_width=float(etch_section.width),
        cpw_width=cpw_width,
        etch_layer=etch_layer,
        mask_layer=ground_mask_layer,
        ground_mask_width=float(ground_mask_section.width),
    )

    capacitor = c << gf.get_component(
        "interdigital_capacitor",
        finger_length=idc_finger_length,
        cpw_xs=single_cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    capacitor.connect("o_capacitor_in", filter_open)
    if capacitor.ports["o_capacitor_out"].orientation != 270:
        raise ValueError(
            "IDC cap outer port orientation must be 270 for this preview topology. "
            f"Got {capacitor.ports['o_capacitor_out'].orientation!r}."
        )
    c.info["filter_capacitor_instance"] = "interdigital_capacitor"
    c.info["path_geometry"]["idc_outer_port"]["orientation"] = int(
        capacitor.ports["o_capacitor_out"].orientation
    )

    c.add_port(port=readout_open_cap.ports["o2"], name="o_readout_open")
    c.add_port(port=capacitor.ports["o_capacitor_out"], name="o_feedline_coupling")
    pair_bbox = c.bbox()
    c.info["pair_bbox_um"] = {
        "width": float(pair_bbox.width()),
        "height": float(pair_bbox.height()),
    }
    c.info["path_geometry"]["idc_outer_port"]["center_um"] = tuple(
        capacitor.ports["o_capacitor_out"].center
    )

    return c


__all__ = [
    "capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators",
]
