"""Public CPW primitives."""

from __future__ import annotations

from math import isfinite

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec, Layer, LayerSpec

from orpen_sc_pdk.helpers.layout import add_etch_for_component
from orpen_sc_pdk.ports import AxisDirection, add_driven_lumped_port
from orpen_sc_pdk.tech import (
    CPW_DRAW,
    CPW_ETCH_NEG,
    CPW_ETCH_POS,
    CPW_GROUND_MASK,
    LAYER,
)


@gf.cell
def cpw_straight(
    length: float = 500.0,
    signal_width: float = 10.0,
    gap: float = 6.0,
    ground_width: float = 50.0,
    layer: LayerSpec = LAYER.D0_TOP_M1_DRAW,
) -> gf.Component:
    """Return a public CPW straight section with two simulation ports."""

    component = gf.Component()
    component << gf.components.rectangle(
        size=(length, signal_width),
        centered=True,
        layer=layer,
    )
    top_ground = component << gf.components.rectangle(
        size=(length, ground_width),
        centered=True,
        layer=layer,
    )
    top_ground.movey((signal_width + ground_width) / 2 + gap)
    bottom_ground = component << gf.components.rectangle(
        size=(length, ground_width),
        centered=True,
        layer=layer,
    )
    bottom_ground.movey(-((signal_width + ground_width) / 2 + gap))
    component.add_port(
        name="o1",
        center=(-length / 2, 0),
        width=signal_width,
        orientation=180,
        layer=layer,
        port_type="sim_cpw",
    )
    component.add_port(
        name="o2",
        center=(length / 2, 0),
        width=signal_width,
        orientation=0,
        layer=layer,
        port_type="sim_cpw",
    )
    return component


@gf.cell(tags=["elements"])
def cpw_t_junction(
    trunk_length: float = 200.0,
    branch_length: float = 100.0,
    cross_section: CrossSectionSpec = "coplanar_waveguide",
) -> gf.Component:
    """Return a CPW T-junction with two trunk ports and one branch port."""

    if not isfinite(trunk_length) or trunk_length <= 0:
        raise ValueError(f"trunk_length must be finite and positive, got {trunk_length!r}.")
    if not isfinite(branch_length) or branch_length <= 0:
        raise ValueError(f"branch_length must be finite and positive, got {branch_length!r}.")

    xs = gf.get_cross_section(cross_section)
    required_sections = (CPW_DRAW, CPW_ETCH_NEG, CPW_ETCH_POS, CPW_GROUND_MASK)
    section_names = {section.name for section in xs.sections}
    missing_sections = [name for name in required_sections if name not in section_names]
    if missing_sections:
        raise ValueError(
            "cross_section must use OrPen CPW sections "
            f"{', '.join(required_sections)}, missing {', '.join(missing_sections)}."
        )

    trunk_center_x = trunk_length / 2
    component = gf.Component()
    trunk_ref = component << gf.path.extrude(
        gf.path.straight(trunk_length),
        cross_section=xs,
    )
    trunk_ref.dmovex(-trunk_center_x)

    branch_ref = component << gf.path.extrude(
        gf.path.straight(branch_length),
        cross_section=xs,
    )
    branch_ref.drotate(90)

    component.add_port(
        name="o1",
        port=trunk_ref.ports["o1"],
    )
    component.add_port(
        name="o2",
        port=trunk_ref.ports["o2"],
    )
    component.add_port(
        name="o_branch",
        port=branch_ref.ports["o2"],
    )

    component.info["topology"] = "cpw_t_junction"
    component.info["trunk_length_um"] = float(trunk_length)
    component.info["branch_length_um"] = float(branch_length)
    component.info["junction_center_um"] = (0.0, 0.0)
    component.info["branch_bends"] = 0
    component.info["ordered_port_names"] = ("o1", "o2", "o_branch")
    component.info["cross_section_name"] = xs.name
    component.info["layers"] = {
        "draw": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_DRAW].layer)),
        "etch": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_ETCH_NEG].layer)),
        "ground_mask": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_GROUND_MASK].layer)),
    }

    component.flatten(merge=False)

    return component


@gf.cell
def n_trace_mtl_section(
    length: float = 500.0,
    cross_section: CrossSectionSpec = "coupled_cpw_w7_s6_d3",
) -> gf.Component:
    """Return a cross-section-driven N-trace straight section."""

    if not isfinite(length) or length <= 0:
        raise ValueError(f"length must be positive, got {length!r}.")

    xs = gf.get_cross_section(cross_section)
    path = gf.path.straight(length)
    return gf.path.extrude(path, cross_section=xs)


def _coupled_mtl_cross_section(
    cross_section: CrossSectionSpec,
    inter_trace_ground_width: float,
) -> tuple:
    """Return the single-CPW and matching two-trace MTL cross-sections."""
    xs = gf.get_cross_section(cross_section)
    required_sections = (CPW_DRAW, CPW_ETCH_NEG, CPW_ETCH_POS, CPW_GROUND_MASK)
    section_names = {section.name for section in xs.sections}
    missing_sections = [name for name in required_sections if name not in section_names]
    if missing_sections:
        raise ValueError(
            "cross_section must use OrPen CPW sections "
            f"{', '.join(required_sections)}, missing {', '.join(missing_sections)}."
        )

    draw_section = xs[CPW_DRAW]
    etch_neg_section = xs[CPW_ETCH_NEG]
    etch_pos_section = xs[CPW_ETCH_POS]
    ground_mask_section = xs[CPW_GROUND_MASK]

    cpw_width = float(draw_section.width)
    neg_gap = float(etch_neg_section.width)
    pos_gap = float(etch_pos_section.width)
    if not all(isfinite(value) and value > 0 for value in (cpw_width, neg_gap, pos_gap)):
        raise ValueError(
            "cross_section CPW draw width and etch gap widths must be finite and positive."
        )
    if neg_gap != pos_gap:
        raise ValueError(
            f"cross_section must have symmetric CPW etch gaps, got {neg_gap!r} and {pos_gap!r}."
        )

    etch_neg_layer = gf.get_layer_tuple(etch_neg_section.layer)
    etch_pos_layer = gf.get_layer_tuple(etch_pos_section.layer)
    if etch_neg_layer != etch_pos_layer:
        raise ValueError(
            "cross_section CPW etch sections must share one layer, "
            f"got {etch_neg_layer!r} and {etch_pos_layer!r}."
        )

    mtl_xs = gf.get_cross_section(
        "n_trace_coplanar_waveguide",
        trace_widths=(cpw_width, cpw_width),
        trace_gaps=(neg_gap, neg_gap),
        inter_trace_ground_widths=(float(inter_trace_ground_width),),
        trace_names=("p", "r"),
        draw_layer=draw_section.layer,
        etch_layer=etch_neg_section.layer,
        ground_mask_layer=ground_mask_section.layer,
    )
    return xs, mtl_xs


@gf.cell(tags=["elements"])
def mtl_bend_coupling_section(
    coupled_length: float = 500.0,
    inter_trace_ground_width: float = 3.0,
    bend_radius: float = 100.0,
    cross_section: CrossSectionSpec = "cpw_6_7_6",
) -> gf.Component:
    """Return two coupled CPW traces with four directly attached Euler bends.

    Defaults are public GDSFactory+ preview settings, not design-target authority.
    """

    for name, value in (
        ("coupled_length", coupled_length),
        ("inter_trace_ground_width", inter_trace_ground_width),
        ("bend_radius", bend_radius),
    ):
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive, got {value!r}.")

    xs, mtl_xs = _coupled_mtl_cross_section(cross_section, inter_trace_ground_width)

    component = gf.Component()
    coupled_ref = component << n_trace_mtl_section(
        length=coupled_length,
        cross_section=mtl_xs,
    )
    coupled_ref.dmovex(-coupled_length / 2)

    left_transition = component << mtl_bend_bend_transition(
        bend_radius=bend_radius,
        inter_trace_ground_width=inter_trace_ground_width,
        cross_section=cross_section,
    )
    left_transition.connect("p_mtl", coupled_ref.ports["p_o1"], mirror=True)

    right_transition = component << mtl_bend_bend_transition(
        bend_radius=bend_radius,
        inter_trace_ground_width=inter_trace_ground_width,
        cross_section=cross_section,
    )
    right_transition.connect("p_mtl", coupled_ref.ports["p_o2"])

    component.add_port(name="r_left", port=left_transition.ports["r_outer"])
    component.add_port(name="r_right", port=right_transition.ports["r_outer"])
    component.add_port(name="p_left", port=left_transition.ports["p_outer"])
    component.add_port(name="p_right", port=right_transition.ports["p_outer"])

    component.info["topology"] = "mtl_bend_coupling_section"
    component.info["coupled_length_um"] = float(coupled_length)
    component.info["inter_trace_ground_width_um"] = float(inter_trace_ground_width)
    component.info["bend_radius_um"] = float(bend_radius)
    component.info["cross_section_name"] = xs.name
    component.info["trace_order_bottom_to_top"] = ("p", "r")
    component.info["ordered_port_names"] = ("r_left", "r_right", "p_left", "p_right")
    component.info["port_orientations_deg"] = {
        "r_left": 90,
        "r_right": 90,
        "p_left": 270,
        "p_right": 270,
    }
    component.info["central_x_span_um"] = (-float(coupled_length) / 2, float(coupled_length) / 2)
    component.info["layers"] = {
        "draw": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_DRAW].layer)),
        "etch": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_ETCH_NEG].layer)),
        "ground_mask": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_GROUND_MASK].layer)),
    }
    return component


@gf.cell(tags=["elements"])
def mtl_straight_bend_coupling_section(
    coupled_length: float = 500.0,
    inter_trace_ground_width: float = 3.0,
    bend_radius: float = 100.0,
    cross_section: CrossSectionSpec = "cpw_6_7_6",
) -> gf.Component:
    """Return a four-port straight--bend pair around a uniform MTL section.

    The lower ``p`` trace extends straight at both sides. The upper ``r``
    trace leaves each side through a directly attached 90-degree Euler bend.
    """

    for name, value in (
        ("coupled_length", coupled_length),
        ("inter_trace_ground_width", inter_trace_ground_width),
        ("bend_radius", bend_radius),
    ):
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive, got {value!r}.")

    xs, mtl_xs = _coupled_mtl_cross_section(cross_section, inter_trace_ground_width)

    component = gf.Component()
    coupled_ref = component << n_trace_mtl_section(
        length=coupled_length,
        cross_section=mtl_xs,
    )
    coupled_ref.dmovex(-coupled_length / 2)

    left_transition = component << mtl_straight_bend_transition(
        straight_length=bend_radius,
        bend_radius=bend_radius,
        inter_trace_ground_width=inter_trace_ground_width,
        cross_section=cross_section,
    )
    left_transition.connect("p_mtl", coupled_ref.ports["p_o1"], mirror=True)

    right_transition = component << mtl_straight_bend_transition(
        straight_length=bend_radius,
        bend_radius=bend_radius,
        inter_trace_ground_width=inter_trace_ground_width,
        cross_section=cross_section,
    )
    right_transition.connect("p_mtl", coupled_ref.ports["p_o2"])

    component.add_port(name="r_left", port=left_transition.ports["r_outer"])
    component.add_port(name="r_right", port=right_transition.ports["r_outer"])
    component.add_port(name="p_left", port=left_transition.ports["p_outer"])
    component.add_port(name="p_right", port=right_transition.ports["p_outer"])

    component.info["topology"] = "mtl_straight_bend_coupling_section"
    component.info["coupled_length_um"] = float(coupled_length)
    component.info["inter_trace_ground_width_um"] = float(inter_trace_ground_width)
    component.info["bend_radius_um"] = float(bend_radius)
    component.info["straight_extension_length_um"] = float(bend_radius)
    component.info["cross_section_name"] = xs.name
    component.info["trace_order_bottom_to_top"] = ("p", "r")
    component.info["terminal_paths"] = {
        "p_left": "straight",
        "p_right": "straight",
        "r_left": "euler_90",
        "r_right": "euler_90",
    }
    component.info["ordered_port_names"] = ("r_left", "r_right", "p_left", "p_right")
    component.info["port_orientations_deg"] = {
        name: int(component.ports[name].orientation)
        for name in component.info["ordered_port_names"]
    }
    component.info["central_x_span_um"] = (-float(coupled_length) / 2, float(coupled_length) / 2)
    component.info["layers"] = {
        "draw": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_DRAW].layer)),
        "etch": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_ETCH_NEG].layer)),
        "ground_mask": tuple(int(value) for value in gf.get_layer_tuple(xs[CPW_GROUND_MASK].layer)),
    }
    return component


@gf.cell(tags=["elements"])
def mtl_straight_bend_transition(
    straight_length: float = 100.0,
    inter_trace_ground_width: float = 3.0,
    bend_radius: float = 100.0,
    lead_length: float = 0.0,
    cross_section: CrossSectionSpec = "cpw_6_7_6",
) -> gf.Component:
    """Return a four-port MTL-seam-to-straight-and-bend transition.

    EM coupon simulations should use ``lead_length >= 50.0`` for test
    fidelity. A value of ``0.0`` preserves existing transition geometry for
    existing coupling-section composition; positive values add shared MTL leads on
    the seam and CPW leads on both outers.
    """
    for name, value in (
        ("straight_length", straight_length),
        ("inter_trace_ground_width", inter_trace_ground_width),
        ("bend_radius", bend_radius),
    ):
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive, got {value!r}.")
    if not isfinite(lead_length) or lead_length < 0:
        raise ValueError(
            "lead_length must be finite and greater than or equal to 0, "
            f"got {lead_length!r}."
        )

    xs, mtl_xs = _coupled_mtl_cross_section(cross_section, inter_trace_ground_width)
    seam = n_trace_mtl_section(length=1.0, cross_section=mtl_xs)
    component = gf.Component()

    p_straight = component << gf.path.extrude(
        gf.path.straight(straight_length),
        cross_section=xs,
    )
    r_bend = component << gf.path.extrude(
        gf.path.euler(radius=bend_radius, angle=90, use_eff=True),
        cross_section=xs,
    )
    p_straight.dmovey(seam.ports["p_o1"].center[1])
    r_bend.dmovey(seam.ports["r_o1"].center[1])

    p_mtl_body = p_straight.ports["o1"]
    r_mtl_body = r_bend.ports["o1"]
    p_outer_body = p_straight.ports["o2"]
    r_outer_body = r_bend.ports["o2"]

    if lead_length > 0:
        seam_lead = component << n_trace_mtl_section(length=lead_length, cross_section=mtl_xs)
        seam_lead.connect("p_o2", p_mtl_body)

        p_outer = component << gf.path.extrude(
            gf.path.straight(lead_length),
            cross_section=xs,
        )
        p_outer.connect("o1", p_outer_body)
        r_outer = component << gf.path.extrude(
            gf.path.straight(lead_length),
            cross_section=xs,
        )
        r_outer.connect("o1", r_outer_body)

        p_mtl_port = seam_lead.ports["p_o1"]
        r_mtl_port = seam_lead.ports["r_o1"]
        p_outer_port = p_outer.ports["o2"]
        r_outer_port = r_outer.ports["o2"]
    else:
        p_mtl_port = p_mtl_body
        r_mtl_port = r_mtl_body
        p_outer_port = p_outer_body
        r_outer_port = r_outer_body

    component.add_port(name="p_mtl", port=p_mtl_port)
    component.add_port(name="r_mtl", port=r_mtl_port)
    component.add_port(name="p_outer", port=p_outer_port)
    component.add_port(name="r_outer", port=r_outer_port)

    component.info["topology"] = "mtl_straight_bend_transition"
    component.info["lead_length_um"] = float(lead_length)
    component.info["cross_section_name"] = xs.name
    component.info["trace_order_bottom_to_top"] = ("p", "r")
    component.info["transition_seam_facing_deg"] = 180.0
    component.info["discontinuity_seam_centers_um"] = {
        "p": tuple(float(value) for value in seam.ports["p_o1"].center),
        "r": tuple(float(value) for value in seam.ports["r_o1"].center),
    }
    component.info["ordered_port_names"] = ("p_mtl", "r_mtl", "p_outer", "r_outer")
    component.info["ordered_orientation_deg"] = {
        "p_mtl": int(component.ports["p_mtl"].orientation),
        "r_mtl": int(component.ports["r_mtl"].orientation),
        "p_outer": int(component.ports["p_outer"].orientation),
        "r_outer": int(component.ports["r_outer"].orientation),
    }
    return component


@gf.cell(tags=["elements"])
def mtl_bend_bend_transition(
    bend_radius: float = 100.0,
    inter_trace_ground_width: float = 3.0,
    lead_length: float = 0.0,
    cross_section: CrossSectionSpec = "cpw_6_7_6",
) -> gf.Component:
    """Return a four-port MTL-seam to opposing-bend transition."""
    if not isfinite(bend_radius) or bend_radius <= 0:
        raise ValueError(f"bend_radius must be finite and positive, got {bend_radius!r}.")
    if not isfinite(lead_length) or lead_length < 0:
        raise ValueError(
            "lead_length must be finite and greater than or equal to 0, "
            f"got {lead_length!r}."
        )

    xs, mtl_xs = _coupled_mtl_cross_section(cross_section, inter_trace_ground_width)
    seam = n_trace_mtl_section(length=1.0, cross_section=mtl_xs)
    component = gf.Component()

    p_bend = component << gf.path.extrude(
        gf.path.euler(radius=bend_radius, angle=-90, use_eff=True),
        cross_section=xs,
    )
    r_bend = component << gf.path.extrude(
        gf.path.euler(radius=bend_radius, angle=90, use_eff=True),
        cross_section=xs,
    )
    p_bend.dmovey(seam.ports["p_o1"].center[1])
    r_bend.dmovey(seam.ports["r_o1"].center[1])

    p_mtl_body = p_bend.ports["o1"]
    r_mtl_body = r_bend.ports["o1"]
    p_outer_body = p_bend.ports["o2"]
    r_outer_body = r_bend.ports["o2"]

    if lead_length > 0:
        seam_lead = component << n_trace_mtl_section(length=lead_length, cross_section=mtl_xs)
        seam_lead.connect("p_o2", p_mtl_body)

        p_outer = component << gf.path.extrude(
            gf.path.straight(lead_length),
            cross_section=xs,
        )
        p_outer.connect("o1", p_outer_body)
        r_outer = component << gf.path.extrude(
            gf.path.straight(lead_length),
            cross_section=xs,
        )
        r_outer.connect("o1", r_outer_body)

        p_mtl_port = seam_lead.ports["p_o1"]
        r_mtl_port = seam_lead.ports["r_o1"]
        p_outer_port = p_outer.ports["o2"]
        r_outer_port = r_outer.ports["o2"]
    else:
        p_mtl_port = p_mtl_body
        r_mtl_port = r_mtl_body
        p_outer_port = p_outer_body
        r_outer_port = r_outer_body

    component.add_port(name="p_mtl", port=p_mtl_port)
    component.add_port(name="r_mtl", port=r_mtl_port)
    component.add_port(name="p_outer", port=p_outer_port)
    component.add_port(name="r_outer", port=r_outer_port)

    component.info["topology"] = "mtl_bend_bend_transition"
    component.info["lead_length_um"] = float(lead_length)
    component.info["cross_section_name"] = xs.name
    component.info["trace_order_bottom_to_top"] = ("p", "r")
    component.info["transition_seam_facing_deg"] = 180.0
    component.info["discontinuity_seam_centers_um"] = {
        "p": tuple(float(value) for value in seam.ports["p_o1"].center),
        "r": tuple(float(value) for value in seam.ports["r_o1"].center),
    }
    component.info["ordered_port_names"] = ("p_mtl", "r_mtl", "p_outer", "r_outer")
    component.info["ordered_orientation_deg"] = {
        "p_mtl": int(component.ports["p_mtl"].orientation),
        "r_mtl": int(component.ports["r_mtl"].orientation),
        "p_outer": int(component.ports["p_outer"].orientation),
        "r_outer": int(component.ports["r_outer"].orientation),
    }
    return component


@gf.cell(tags=["elements"])
def launcher(
    pad_width: float = 150.0,
    pad_length: float = 150.0,
    taper_length: float = 150.0,
    side_gap_height: float = 85.0,
    end_gap_width: float = 85.0,
    cpw_xs: CrossSectionSpec = "coplanar_waveguide",
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    sim_boundary_layer: Layer = LAYER.D0_TOP_SIM_BOUNDARY,
) -> gf.Component:
    """Return a tapered CPW launcher from a large pad to a CPW neck."""

    xs = gf.get_cross_section(cpw_xs)
    cpw_width = xs["cpw_draw"].width
    cpw_gap = xs["cpw_etch_pos"].width

    component = gf.Component()

    pad_half = pad_width / 2
    neck_half = cpw_width / 2
    x_pad_end = pad_length
    x_tip = pad_length + taper_length

    component.add_polygon(
        [
            (0, pad_half),
            (x_pad_end, pad_half),
            (x_tip, neck_half),
            (x_tip, -neck_half),
            (x_pad_end, -pad_half),
            (0, -pad_half),
        ],
        layer=draw_layer,
    )

    mask_region = [
        (component.xmin - end_gap_width, component.ymax + side_gap_height),
        (pad_length, component.ymax + side_gap_height),
        (component.xmax, neck_half + cpw_gap),
        (component.xmax, -(neck_half + cpw_gap)),
        (pad_length, component.ymin - side_gap_height),
        (component.xmin - end_gap_width, component.ymin - side_gap_height),
    ]
    component.add_polygon(mask_region, layer=ground_mask_layer)

    sheet_region = [
        (component.xmin, pad_half),
        (0.0, pad_half),
        (0.0, -pad_half),
        (component.xmin, -pad_half),
    ]
    component.add_polygon(sheet_region, layer=sim_boundary_layer)

    component = add_etch_for_component(
        component=component,
        draw_layer=draw_layer,
        mask_layer=ground_mask_layer,
        etch_layer=etch_layer,
    )

    component.add_port(
        name="o_neck",
        center=(x_tip, 0),
        width=cpw_width,
        orientation=0,
        layer=draw_layer,
    )
    component.add_port(
        name="o_pad",
        center=(0, 0),
        width=pad_width,
        orientation=180,
        layer=draw_layer,
    )
    add_driven_lumped_port(
        component,
        name="o_lumped",
        center=(component.xmin / 2, 0),
        width=1,
        orientation=0,
        layer=sim_boundary_layer,
        direction=AxisDirection.POS_X,
    )

    return component
