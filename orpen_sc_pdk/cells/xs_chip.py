"""Single-trace CPW chip component for ANSYS Q2D cross-section extraction."""

from typing import Any

import gdsfactory as gf
from gdsfactory.cross_section import CrossSection
from gdsfactory.typings import CrossSectionSpec

from orpen_sc_pdk.cells.cpw import n_trace_mtl_section
from orpen_sc_pdk.ports import add_q2d_conductor_port
from orpen_sc_pdk.tech import (
    CPW_ETCH_NEG,
    CPW_ETCH_POS,
    CPW_GROUND_MASK,
    LAYER,
    LayerSpec,
    coplanar_waveguide,
    n_trace_coplanar_waveguide,
)


@gf.cell(tags=["chips", "q2d", "cross_section"])
def single_trace_xs_chip(
    length_um: float = 1000.0,
    cpw_xs: CrossSectionSpec = "cpw_6_10_6",
    cpw_gap_width_gap_um: tuple[float, float, float] | None = None,
    draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    signal_assignment_name: str = "Trace1",
) -> gf.Component:
    """Return a single straight CPW trace with Q2D conductor markers.

    The trace runs along +X. The generated Q2D package applies the notebook
    rotation convention before sectioning: rotate 90 deg about Y, then 90 deg
    about Z, so the final Q2D section lands on the XY plane.
    """

    if length_um <= 0:
        raise ValueError(f"length_um must be positive, got {length_um!r}.")

    xs = _resolve_symmetric_cpw_xs(
        cpw_xs,
        cpw_gap_width_gap_um=cpw_gap_width_gap_um,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    cpw_width = float(xs.width)
    cpw_gap = _symmetric_cpw_gap(xs)
    gap_outer_y = cpw_width / 2 + cpw_gap
    q2d_ground_marker_offset_um = cpw_gap / 2
    ground_marker_y = gap_outer_y + q2d_ground_marker_offset_um

    c = gf.Component()
    trace = c << gf.components.straight(length=length_um, cross_section=xs)
    c.add_ports(trace.ports)

    marker_x = length_um / 2
    add_q2d_conductor_port(
        c,
        name="q2d_left_ground",
        center=(marker_x, -ground_marker_y),
        layer=draw_layer,
        width=cpw_gap,
    )
    add_q2d_conductor_port(
        c,
        name="q2d_right_ground",
        center=(marker_x, ground_marker_y),
        layer=draw_layer,
        width=cpw_gap,
    )
    add_q2d_conductor_port(
        c,
        name="q2d_center_signal",
        center=(marker_x, 0.0),
        layer=draw_layer,
        width=cpw_width,
    )

    c.info["length_um"] = float(length_um)
    c.info["cpw_width_um"] = cpw_width
    c.info["cpw_gap_um"] = cpw_gap
    c.info["cpw_gap_width_gap_um"] = (cpw_gap, cpw_width, cpw_gap)
    c.info["trace_topology"] = "1-Trace"
    c.info["die_topology"] = "single_die"
    c.info["q2d_ground_marker_offset_um"] = q2d_ground_marker_offset_um
    c.info["q2d_ground_marker_y_um"] = ground_marker_y
    c.info["q2d_signal_assignment_name"] = signal_assignment_name
    c.info["q2d_ground_assignment_name"] = "Ground"
    c.info["layers"] = {
        "draw": _layer_spec_to_tuple(draw_layer),
        "etch": _layer_spec_to_tuple(etch_layer),
        "ground_mask": _layer_spec_to_tuple(ground_mask_layer),
    }
    c.info["q2d_rotations"] = (
        {"axis": "Y", "angle_deg": 90},
        {"axis": "Z", "angle_deg": 90},
    )
    return c


@gf.cell(tags=["chips", "q2d", "cross_section"])
def two_trace_xs_chip(
    length_um: float = 1000.0,
    cpw_gap_width_gap_um: tuple[float, float, float] = (6.0, 10.0, 6.0),
    trace_gap_um: float = 15.0,
    draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    signal_assignment_names: tuple[str, str] = ("Trace1", "Trace2"),
) -> gf.Component:
    """Return two same-die coupled CPW traces with Q2D conductor markers."""

    if length_um <= 0:
        raise ValueError(f"length_um must be positive, got {length_um!r}.")
    ground_gap_um, trace_width_um = _symmetric_gap_width_gap(cpw_gap_width_gap_um)
    inter_trace_ground_width_um = _two_trace_middle_ground_width(trace_gap_um, ground_gap_um)
    if len(signal_assignment_names) != 2 or any(
        not isinstance(name, str) or not name.strip() for name in signal_assignment_names
    ):
        raise ValueError("signal_assignment_names must contain two non-empty names.")

    c = gf.Component()
    trace_xs = n_trace_coplanar_waveguide(
        trace_widths=(trace_width_um, trace_width_um),
        trace_gaps=(ground_gap_um, ground_gap_um),
        inter_trace_ground_widths=(inter_trace_ground_width_um,),
        trace_names=signal_assignment_names,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    c << n_trace_mtl_section(length=length_um, cross_section=trace_xs)
    trace1_center_y = -(trace_width_um + trace_gap_um) / 2
    trace2_center_y = (trace_width_um + trace_gap_um) / 2
    _add_two_trace_markers(
        c,
        length_um=length_um,
        trace_width_um=trace_width_um,
        trace_gap_um=trace_gap_um,
        ground_gap_um=ground_gap_um,
        draw_layer=draw_layer,
        signal_assignment_names=signal_assignment_names,
        prefix="q2d_d0",
        y_offset_um=0.0,
    )

    c.info["length_um"] = float(length_um)
    c.info["cpw_width_um"] = trace_width_um
    c.info["cpw_gap_um"] = ground_gap_um
    c.info["cpw_gap_width_gap_um"] = (ground_gap_um, trace_width_um, ground_gap_um)
    c.info["trace_gap_um"] = float(trace_gap_um)
    c.info["middle_ground_width_um"] = inter_trace_ground_width_um
    c.info["minimum_middle_ground_width_um"] = _MIN_TWO_TRACE_MIDDLE_GROUND_WIDTH_UM
    c.info["trace_gap_process_note"] = (
        "trace_gap_um is signal-edge-to-signal-edge spacing; keep the gap-to-gap "
        "middle ground metal at least 3um for process margin."
    )
    c.info["signal_center_spacing_um"] = trace_width_um + trace_gap_um
    c.info["trace1_center_y_um"] = trace1_center_y
    c.info["trace2_center_y_um"] = trace2_center_y
    c.info["trace_topology"] = "2-Trace"
    c.info["die_topology"] = "single_die"
    c.info["q2d_signal_assignment_names"] = tuple(signal_assignment_names)
    c.info["q2d_ground_assignment_name"] = "Ground"
    c.info["layers"] = {
        "draw": _layer_spec_to_tuple(draw_layer),
        "etch": _layer_spec_to_tuple(etch_layer),
        "ground_mask": _layer_spec_to_tuple(ground_mask_layer),
    }
    c.info["q2d_rotations"] = _Q2D_SECTION_ROTATIONS
    return c


@gf.cell(tags=["chips", "q2d", "cross_section", "flip_chip"])
def single_trace_flip_chip_xs_chip(
    length_um: float = 1000.0,
    cpw_xs: CrossSectionSpec = "cpw_6_10_6",
    cpw_gap_width_gap_um: tuple[float, float, float] | None = None,
    d0_draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    d0_etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    d0_ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    d1_ground_marker_layer: LayerSpec = LAYER.D1_BOTTOM_M1_DRAW,
    d1_ground_mask_layer: LayerSpec = LAYER.D1_BOTTOM_GROUND_MASK,
    signal_assignment_name: str = "Trace1",
) -> gf.Component:
    """Return one D0 trace facing a D1 ground plane for Q2D extraction."""

    if length_um <= 0:
        raise ValueError(f"length_um must be positive, got {length_um!r}.")

    xs = _resolve_symmetric_cpw_xs(
        cpw_xs,
        cpw_gap_width_gap_um=cpw_gap_width_gap_um,
        draw_layer=d0_draw_layer,
        etch_layer=d0_etch_layer,
        ground_mask_layer=d0_ground_mask_layer,
    )
    cpw_width = float(xs.width)
    cpw_gap = _symmetric_cpw_gap(xs)
    gap_outer_y = cpw_width / 2 + cpw_gap
    ground_marker_y = gap_outer_y + cpw_gap / 2
    marker_x = length_um / 2

    c = gf.Component()
    trace = c << gf.components.straight(length=length_um, cross_section=xs)
    c.add_ports(trace.ports)
    _add_rect(
        c,
        x_min=0.0,
        x_max=length_um,
        y_min=-gap_outer_y,
        y_max=gap_outer_y,
        layer=d1_ground_mask_layer,
    )

    add_q2d_conductor_port(
        c,
        name="q2d_d0_left_ground",
        center=(marker_x, -ground_marker_y),
        layer=d0_draw_layer,
        width=cpw_gap,
    )
    add_q2d_conductor_port(
        c,
        name="q2d_d0_right_ground",
        center=(marker_x, ground_marker_y),
        layer=d0_draw_layer,
        width=cpw_gap,
    )
    add_q2d_conductor_port(
        c,
        name="q2d_d0_trace1_signal",
        center=(marker_x, 0.0),
        layer=d0_draw_layer,
        width=cpw_width,
    )
    add_q2d_conductor_port(
        c,
        name="q2d_d1_facing_ground",
        center=(marker_x, 0.0),
        layer=d1_ground_marker_layer,
        width=cpw_width,
    )

    c.info["length_um"] = float(length_um)
    c.info["cpw_width_um"] = cpw_width
    c.info["cpw_gap_um"] = cpw_gap
    c.info["cpw_gap_width_gap_um"] = (cpw_gap, cpw_width, cpw_gap)
    c.info["trace_topology"] = "1-Trace"
    c.info["die_topology"] = "flip_chip"
    c.info["q2d_signal_assignment_names"] = (signal_assignment_name,)
    c.info["q2d_ground_assignment_name"] = "Ground"
    c.info["required_active_dies"] = ("D0", "D1")
    c.info["required_ground_plane_layer_names"] = ("D0_TOP_M1", "D1_BOTTOM_M1")
    c.info["layers"] = {
        "d0_draw": _layer_spec_to_tuple(d0_draw_layer),
        "d0_etch": _layer_spec_to_tuple(d0_etch_layer),
        "d0_ground_mask": _layer_spec_to_tuple(d0_ground_mask_layer),
        "d1_ground_marker": _layer_spec_to_tuple(d1_ground_marker_layer),
        "d1_ground_mask": _layer_spec_to_tuple(d1_ground_mask_layer),
    }
    c.info["q2d_rotations"] = _Q2D_SECTION_ROTATIONS
    return c


@gf.cell(tags=["chips", "q2d", "cross_section", "flip_chip"])
def two_trace_flip_chip_xs_chip(
    length_um: float = 1000.0,
    cpw_gap_width_gap_um: tuple[float, float, float] = (6.0, 10.0, 6.0),
    horizontal_offset_um: float = 0.0,
    d0_draw_layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
    d0_etch_layer: LayerSpec = LAYER.D0_TOP_M1_ETCH,
    d0_ground_mask_layer: LayerSpec = LAYER.D0_TOP_GROUND_MASK,
    d1_draw_layer: LayerSpec = LAYER.D1_BOTTOM_M1_DRAW,
    d1_etch_layer: LayerSpec = LAYER.D1_BOTTOM_M1_ETCH,
    d1_ground_mask_layer: LayerSpec = LAYER.D1_BOTTOM_GROUND_MASK,
    signal_assignment_names: tuple[str, str] = ("Trace1", "Trace2"),
) -> gf.Component:
    """Return opposing D0/D1 traces for flip-chip MTL Q2D extraction."""

    if length_um <= 0:
        raise ValueError(f"length_um must be positive, got {length_um!r}.")
    cpw_gap, cpw_width = _symmetric_gap_width_gap(cpw_gap_width_gap_um)
    if len(signal_assignment_names) != 2 or any(
        not str(name).strip() for name in signal_assignment_names
    ):
        raise ValueError("signal_assignment_names must contain two non-empty names.")

    c = gf.Component()
    d0_xs = coplanar_waveguide(
        width=cpw_width,
        gap=cpw_gap,
        draw_layer=d0_draw_layer,
        etch_layer=d0_etch_layer,
        ground_mask_layer=d0_ground_mask_layer,
        radius=None,
    )
    d1_xs = coplanar_waveguide(
        width=cpw_width,
        gap=cpw_gap,
        draw_layer=d1_draw_layer,
        etch_layer=d1_etch_layer,
        ground_mask_layer=d1_ground_mask_layer,
        radius=None,
    )
    d0_trace = c << gf.components.straight(length=length_um, cross_section=d0_xs)
    d1_trace = c << gf.components.straight(length=length_um, cross_section=d1_xs)
    d1_trace.movey(horizontal_offset_um)
    c.add_ports(d0_trace.ports, prefix="d0_")
    c.add_ports(d1_trace.ports, prefix="d1_")

    marker_x = length_um / 2
    ground_marker_offset_y = cpw_width / 2 + cpw_gap + cpw_gap / 2
    for prefix, draw_layer, y_offset, assignment in (
        ("q2d_d0", d0_draw_layer, 0.0, signal_assignment_names[0]),
        ("q2d_d1", d1_draw_layer, float(horizontal_offset_um), signal_assignment_names[1]),
    ):
        add_q2d_conductor_port(
            c,
            name=f"{prefix}_left_ground",
            center=(marker_x, y_offset - ground_marker_offset_y),
            layer=draw_layer,
            width=cpw_gap,
        )
        add_q2d_conductor_port(
            c,
            name=f"{prefix}_right_ground",
            center=(marker_x, y_offset + ground_marker_offset_y),
            layer=draw_layer,
            width=cpw_gap,
        )
        add_q2d_conductor_port(
            c,
            name=f"{prefix}_{assignment.casefold()}_signal",
            center=(marker_x, y_offset),
            layer=draw_layer,
            width=cpw_width,
        )

    c.info["length_um"] = float(length_um)
    c.info["cpw_width_um"] = cpw_width
    c.info["cpw_gap_um"] = cpw_gap
    c.info["cpw_gap_width_gap_um"] = (cpw_gap, cpw_width, cpw_gap)
    c.info["horizontal_offset_um"] = float(horizontal_offset_um)
    c.info["trace_topology"] = "2-Trace"
    c.info["die_topology"] = "flip_chip"
    c.info["q2d_signal_assignment_names"] = tuple(signal_assignment_names)
    c.info["q2d_ground_assignment_name"] = "Ground"
    c.info["required_active_dies"] = ("D0", "D1")
    c.info["required_ground_plane_layer_names"] = ("D0_TOP_M1", "D1_BOTTOM_M1")
    c.info["layers"] = {
        "d0_draw": _layer_spec_to_tuple(d0_draw_layer),
        "d0_etch": _layer_spec_to_tuple(d0_etch_layer),
        "d0_ground_mask": _layer_spec_to_tuple(d0_ground_mask_layer),
        "d1_draw": _layer_spec_to_tuple(d1_draw_layer),
        "d1_etch": _layer_spec_to_tuple(d1_etch_layer),
        "d1_ground_mask": _layer_spec_to_tuple(d1_ground_mask_layer),
    }
    c.info["q2d_rotations"] = _Q2D_SECTION_ROTATIONS
    return c


_Q2D_SECTION_ROTATIONS = (
    {"axis": "Y", "angle_deg": 90},
    {"axis": "Z", "angle_deg": 90},
)
_MIN_TWO_TRACE_MIDDLE_GROUND_WIDTH_UM = 3.0


def _resolve_symmetric_cpw_xs(
    cpw_xs: CrossSectionSpec,
    *,
    cpw_gap_width_gap_um: tuple[float, float, float] | None,
    draw_layer: LayerSpec,
    etch_layer: LayerSpec,
    ground_mask_layer: LayerSpec,
) -> CrossSection:
    if cpw_gap_width_gap_um is None:
        return gf.get_cross_section(
            cpw_xs,
            draw_layer=draw_layer,
            etch_layer=etch_layer,
            ground_mask_layer=ground_mask_layer,
        )
    gap_um, width_um = _symmetric_gap_width_gap(cpw_gap_width_gap_um)
    return coplanar_waveguide(
        width=width_um,
        gap=gap_um,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=None,
    )


def _symmetric_gap_width_gap(
    cpw_gap_width_gap_um: tuple[float, float, float],
) -> tuple[float, float]:
    if len(cpw_gap_width_gap_um) != 3:
        raise ValueError("cpw_gap_width_gap_um must be a (left_gap, width, right_gap) tuple.")
    left_gap_um, width_um, right_gap_um = (float(value) for value in cpw_gap_width_gap_um)
    if left_gap_um <= 0 or width_um <= 0 or right_gap_um <= 0:
        raise ValueError(
            f"cpw_gap_width_gap_um entries must be positive, got {cpw_gap_width_gap_um!r}."
        )
    if left_gap_um != right_gap_um:
        raise ValueError(
            f"Q2D CPW cross-section helpers require symmetric gaps, got {cpw_gap_width_gap_um!r}."
        )
    return left_gap_um, width_um


def _two_trace_middle_ground_width(trace_gap_um: float, cpw_gap_um: float) -> float:
    trace_gap_um = float(trace_gap_um)
    cpw_gap_um = float(cpw_gap_um)
    if trace_gap_um <= 0:
        raise ValueError(f"trace_gap_um must be positive, got {trace_gap_um!r}.")
    middle_ground_width_um = trace_gap_um - 2 * cpw_gap_um
    if middle_ground_width_um < _MIN_TWO_TRACE_MIDDLE_GROUND_WIDTH_UM:
        minimum_trace_gap_um = 2 * cpw_gap_um + _MIN_TWO_TRACE_MIDDLE_GROUND_WIDTH_UM
        raise ValueError(
            "two_trace_xs_chip requires non-overlapping CPW gaps and at least "
            f"{_MIN_TWO_TRACE_MIDDLE_GROUND_WIDTH_UM:g}um gap-to-gap middle ground metal; "
            f"trace_gap_um must be >= {minimum_trace_gap_um:g}um for cpw_gap_um={cpw_gap_um:g}um, "
            f"got {trace_gap_um:g}um."
        )
    return middle_ground_width_um


def _add_two_trace_markers(
    component: gf.Component,
    *,
    length_um: float,
    trace_width_um: float,
    ground_gap_um: float,
    trace_gap_um: float,
    draw_layer: LayerSpec,
    signal_assignment_names: tuple[str, str],
    prefix: str,
    y_offset_um: float,
) -> None:
    marker_x = length_um / 2
    trace1_center_y = y_offset_um - (trace_width_um + trace_gap_um) / 2
    trace2_center_y = y_offset_um + (trace_width_um + trace_gap_um) / 2
    middle_ground_width_um = _two_trace_middle_ground_width(trace_gap_um, ground_gap_um)
    left_ground_y = trace1_center_y - trace_width_um / 2 - ground_gap_um - ground_gap_um / 2
    right_ground_y = trace2_center_y + trace_width_um / 2 + ground_gap_um + ground_gap_um / 2
    add_q2d_conductor_port(
        component,
        name=f"{prefix}_left_ground",
        center=(marker_x, left_ground_y),
        layer=draw_layer,
        width=ground_gap_um,
    )
    add_q2d_conductor_port(
        component,
        name=f"{prefix}_middle_ground",
        center=(marker_x, y_offset_um),
        layer=draw_layer,
        width=middle_ground_width_um,
    )
    add_q2d_conductor_port(
        component,
        name=f"{prefix}_right_ground",
        center=(marker_x, right_ground_y),
        layer=draw_layer,
        width=ground_gap_um,
    )
    add_q2d_conductor_port(
        component,
        name=f"{prefix}_trace1_signal",
        center=(marker_x, trace1_center_y),
        layer=draw_layer,
        width=trace_width_um,
    )
    add_q2d_conductor_port(
        component,
        name=f"{prefix}_trace2_signal",
        center=(marker_x, trace2_center_y),
        layer=draw_layer,
        width=trace_width_um,
    )


def _add_rect(
    component: gf.Component,
    *,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    layer: LayerSpec,
) -> None:
    component.add_polygon(
        points=((x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)),
        layer=layer,
    )


def _symmetric_cpw_gap(xs: CrossSection) -> float:
    gaps = [
        float(section.width)
        for section in xs.sections
        if section.name in {CPW_ETCH_NEG, CPW_ETCH_POS}
    ]
    if len(gaps) != 2 or gaps[0] != gaps[1]:
        raise ValueError(
            "single_trace_xs_chip requires a symmetric CPW cross-section "
            f"with {CPW_ETCH_NEG!r} and {CPW_ETCH_POS!r} sections."
        )
    if not any(section.name == CPW_GROUND_MASK for section in xs.sections):
        raise ValueError(
            f"single_trace_xs_chip requires a CPW cross-section with {CPW_GROUND_MASK!r}."
        )
    return gaps[0]


def _layer_spec_to_tuple(layer: Any) -> tuple[int, int]:
    if isinstance(layer, tuple):
        layer_index, datatype = layer
        return int(layer_index), int(datatype)
    if hasattr(layer, "layer") and hasattr(layer, "datatype"):
        return int(layer.layer), int(layer.datatype)

    layer_index, datatype = gf.get_layer_tuple(layer)
    return int(layer_index), int(datatype)


__all__ = [
    "single_trace_flip_chip_xs_chip",
    "single_trace_xs_chip",
    "two_trace_flip_chip_xs_chip",
    "two_trace_xs_chip",
]
