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


def _quarter_wave_arm(
    component: gf.Component,
    start_port: gf.Port,
    first_arc_angle: float,
    second_arc_angle: float,
    cpw_length: float,
    arm_horizontal_length: float,
    cpw_radius: float,
    cross_section: object,
) -> gf.Port:
    """Add a three-straight, two-arc U-turn arm and return its output port."""

    if start_port.orientation not in {0, 180}:
        raise ValueError(
            "Start ports for quarter-wave arms must be oriented east or west. "
            f"Got {start_port.orientation!r}."
        )
    straight_vertical = cpw_length - 2 * arm_horizontal_length - pi * cpw_radius
    if straight_vertical <= 0:
        raise ValueError(
            "Each quarter-wave arm must leave a positive vertical remainder. "
            f"Got {straight_vertical!r}."
        )

    arm_path = (
        gf.path.straight(arm_horizontal_length)
        + gf.path.arc(radius=cpw_radius, angle=first_arc_angle)
        + gf.path.straight(straight_vertical)
        + gf.path.arc(radius=cpw_radius, angle=second_arc_angle)
        + gf.path.straight(arm_horizontal_length)
    )
    arm_ref = component << gf.path.extrude(arm_path, cross_section=cross_section)
    if start_port.orientation == 180:
        arm_ref.connect("o2", start_port)
        return arm_ref.ports["o1"]
    arm_ref.connect("o1", start_port)
    return arm_ref.ports["o2"]


@gf.cell(tags=["elements"])
def capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators(
    readout_open_length: float = 3014.87,
    readout_short_length: float = 2100.74,
    coupled_length: float = 645.30,
    filter_open_length: float = 3014.87,
    filter_short_length: float = 2100.74,
    cpw_radius: float = 100.0,
    arm_horizontal_length: float = 500.0,
    single_cpw_xs: CrossSectionSpec = "cpw_6_7_6",
    coupled_cpw_xs: CrossSectionSpec = "coupled_cpw_w7_s6_d3",
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Return an individual readout/coupled Purcell-filter topology sharing one coupled MTL section.

    Public preview defaults:
    readout_open_length=3014.87, readout_short_length=2100.74,
    coupled_length=645.30, filter_open_length=3014.87, filter_short_length=2100.74.
    """

    for name, value in (
        ("readout_open_length", readout_open_length),
        ("readout_short_length", readout_short_length),
        ("coupled_length", coupled_length),
        ("filter_open_length", filter_open_length),
        ("filter_short_length", filter_short_length),
        ("cpw_radius", cpw_radius),
        ("arm_horizontal_length", arm_horizontal_length),
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
    c.info["readout_short_length_um"] = float(readout_short_length)
    c.info["coupled_length_um"] = float(coupled_length)
    c.info["filter_open_length_um"] = float(filter_open_length)
    c.info["filter_short_length_um"] = float(filter_short_length)
    c.info["cpw_radius_um"] = float(cpw_radius)
    c.info["arm_horizontal_length_um"] = float(arm_horizontal_length)
    c.info["ordered_port_names"] = ("o_readout_open", "o_feedline_coupling")

    cpw_width = float(single_xs.width)
    etch_section = single_xs["cpw_etch_pos"]
    ground_mask_section = single_xs["cpw_ground_mask"]
    c.info["draw_layer"] = tuple(int(value) for value in single_xs["cpw_draw"].layer)
    c.info["etch_layer"] = tuple(int(value) for value in etch_section.layer)
    c.info["ground_mask_layer"] = tuple(int(value) for value in ground_mask_section.layer)
    c.info["ground_mask_width"] = float(ground_mask_section.width)

    c.info["readout_trace"] = "r"
    c.info["filter_trace"] = "p"

    coupled = c << gf.get_component(
        "n_trace_mtl_section",
        length=coupled_length,
        cross_section=coupled_xs,
    )

    _quarter_wave_arm(
        component=c,
        start_port=coupled.ports["r_o1"],
        first_arc_angle=-90.0,
        second_arc_angle=90.0,
        cpw_length=readout_short_length,
        arm_horizontal_length=arm_horizontal_length,
        cpw_radius=cpw_radius,
        cross_section=single_xs,
    )
    r_right_port = _quarter_wave_arm(
        component=c,
        start_port=coupled.ports["r_o2"],
        first_arc_angle=90.0,
        second_arc_angle=-90.0,
        cpw_length=readout_open_length,
        arm_horizontal_length=arm_horizontal_length,
        cpw_radius=cpw_radius,
        cross_section=single_xs,
    )
    _quarter_wave_arm(
        component=c,
        start_port=coupled.ports["p_o1"],
        first_arc_angle=90.0,
        second_arc_angle=-90.0,
        cpw_length=filter_short_length,
        arm_horizontal_length=arm_horizontal_length,
        cpw_radius=cpw_radius,
        cross_section=single_xs,
    )
    p_right_port = _quarter_wave_arm(
        component=c,
        start_port=coupled.ports["p_o2"],
        first_arc_angle=-90.0,
        second_arc_angle=90.0,
        cpw_length=filter_open_length,
        arm_horizontal_length=arm_horizontal_length,
        cpw_radius=cpw_radius,
        cross_section=single_xs,
    )

    c.info["short_termination"] = "cpw_gap_stop"

    readout_open_cap = _add_open_end_cap(
        component=c,
        end_port=r_right_port,
        etch_width=float(etch_section.width),
        cpw_width=cpw_width,
        etch_layer=etch_layer,
        mask_layer=ground_mask_layer,
        ground_mask_width=float(ground_mask_section.width),
    )

    capacitor = c << gf.get_component(
        "interdigital_capacitor",
        cpw_xs=single_cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    capacitor.connect("o_capacitor_in", p_right_port)
    c.info["filter_capacitor_instance"] = "interdigital_capacitor"

    c.add_port(
        "o_readout_open",
        center=readout_open_cap.ports["o2"].center,
        width=cpw_width,
        orientation=readout_open_cap.ports["o2"].orientation,
        layer=readout_open_cap.ports["o2"].layer,
        port_type="placement",
    )
    c.add_port(
        "o_feedline_coupling",
        center=capacitor.ports["o_capacitor_out"].center,
        width=cpw_width,
        orientation=270,
        layer=single_xs["cpw_draw"].layer,
        port_type="placement",
    )

    return c


__all__ = [
    "capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators",
]
