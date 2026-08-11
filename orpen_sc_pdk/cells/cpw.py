"""Public CPW primitives."""

from __future__ import annotations

from math import cos, isfinite, pi, sin

import gdsfactory as gf
from gdsfactory import kdb
from gdsfactory.typings import CrossSectionSpec, Layer, LayerSpec

from orpen_sc_pdk.helpers.layout import add_etch_for_component
from orpen_sc_pdk.ports import AxisDirection, add_driven_lumped_port
from orpen_sc_pdk.tech import (
    CPW_DRAW,
    CPW_ETCH_NEG,
    CPW_ETCH_POS,
    CPW_GROUND_MASK,
    LAYER,
    SUBSTRATE_THICKNESS_UM,
)

# These GDS layers identify an HFSS Driven Terminal coupon only. They are not
# process layers and must not be used in fabrication layout.
MTL_SB_HFSS_SIGNAL_P_LAYER: Layer = (905, 0)
MTL_SB_HFSS_SIGNAL_R_LAYER: Layer = (906, 0)
MTL_SB_HFSS_GROUND_LAYER: Layer = (907, 0)
MTL_SB_HFSS_SUBSTRATE_FOOTPRINT_LAYER: Layer = (908, 0)


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
        radius=bend_radius,
    )

    component = gf.Component()
    coupled_ref = component << n_trace_mtl_section(
        length=coupled_length,
        cross_section=mtl_xs,
    )
    coupled_ref.dmovex(-coupled_length / 2)

    bend = gf.path.extrude(
        gf.path.euler(radius=bend_radius, angle=90, use_eff=True),
        cross_section=xs,
    )
    p_left = component << bend
    p_left.connect("o1", coupled_ref.ports["p_o1"])
    r_left = component << bend
    r_left.connect("o1", coupled_ref.ports["r_o1"], mirror=True)
    p_right = component << bend
    p_right.connect("o1", coupled_ref.ports["p_o2"], mirror=True)
    r_right = component << bend
    r_right.connect("o1", coupled_ref.ports["r_o2"])

    component.add_port(name="r_left", port=r_left.ports["o2"])
    component.add_port(name="r_right", port=r_right.ports["o2"])
    component.add_port(name="p_left", port=p_left.ports["o2"])
    component.add_port(name="p_right", port=p_right.ports["o2"])

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
        "draw": tuple(int(value) for value in gf.get_layer_tuple(draw_section.layer)),
        "etch": tuple(int(value) for value in etch_neg_layer),
        "ground_mask": tuple(int(value) for value in gf.get_layer_tuple(ground_mask_section.layer)),
    }
    return component


@gf.cell(tags=["elements"])
def mtl_straight_bend_coupling_section(
    coupled_length: float = 500.0,
    inter_trace_ground_width: float = 3.0,
    bend_radius: float = 100.0,
    cross_section: CrossSectionSpec = "cpw_6_7_6",
) -> gf.Component:
    """Return one full four-port straight--bend coupled-MTL geometry.

    The lower ``p`` trace extends straight at both sides. The upper ``r``
    trace leaves each side through a directly attached 90-degree Euler bend.
    This is one layout/EM block, not a cascade of separate bend and MTL cells.
    """

    for name, value in (
        ("coupled_length", coupled_length),
        ("inter_trace_ground_width", inter_trace_ground_width),
        ("bend_radius", bend_radius),
    ):
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive, got {value!r}.")

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
        radius=bend_radius,
    )

    component = gf.Component()
    coupled_ref = component << n_trace_mtl_section(
        length=coupled_length,
        cross_section=mtl_xs,
    )
    coupled_ref.dmovex(-coupled_length / 2)

    straight = gf.path.extrude(gf.path.straight(bend_radius), cross_section=xs)
    p_left = component << straight
    p_left.connect("o2", coupled_ref.ports["p_o1"])
    p_right = component << straight
    p_right.connect("o1", coupled_ref.ports["p_o2"])

    bend = gf.path.extrude(
        gf.path.euler(radius=bend_radius, angle=90, use_eff=True),
        cross_section=xs,
    )
    r_left = component << bend
    r_left.connect("o1", coupled_ref.ports["r_o1"], mirror=True)
    r_right = component << bend
    r_right.connect("o1", coupled_ref.ports["r_o2"])

    component.add_port(name="r_left", port=r_left.ports["o2"])
    component.add_port(name="r_right", port=r_right.ports["o2"])
    component.add_port(name="p_left", port=p_left.ports["o1"])
    component.add_port(name="p_right", port=p_right.ports["o2"])

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
        "draw": tuple(int(value) for value in gf.get_layer_tuple(draw_section.layer)),
        "etch": tuple(int(value) for value in etch_neg_layer),
        "ground_mask": tuple(int(value) for value in gf.get_layer_tuple(ground_mask_section.layer)),
    }
    return component


def _signal_polygon_at_port(
    signal_region: kdb.Region,
    *,
    port: gf.Port,
    dbu_um: float,
) -> kdb.Polygon:
    """Return the unique signal polygon connected just inside one CPW port."""

    if port.orientation is None:
        raise ValueError(f"{port.name} must have an orientation.")
    probe_distance_um = max(dbu_um, float(port.width) / 4)
    angle = float(port.orientation) * pi / 180
    probe = kdb.Point(
        round((float(port.x) - probe_distance_um * cos(angle)) / dbu_um),
        round((float(port.y) - probe_distance_um * sin(angle)) / dbu_um),
    )
    matches = [polygon for polygon in signal_region.each() if polygon.inside(probe)]
    if len(matches) != 1:
        raise ValueError(
            f"{port.name} must identify exactly one connected signal conductor, got {len(matches)}."
        )
    return matches[0]


@gf.cell(tags=["simulation"])
def mtl_straight_bend_coupling_section_hfss_coupon(
    coupled_length: float = 500.0,
    inter_trace_ground_width: float = 3.0,
    bend_radius: float = 100.0,
    terminal_open_clearance_um: float | None = None,
    coupon_margin_um: float = 100.0,
    cross_section: CrossSectionSpec = "cpw_6_7_6",
    signal_p_layer: Layer = MTL_SB_HFSS_SIGNAL_P_LAYER,
    signal_r_layer: Layer = MTL_SB_HFSS_SIGNAL_R_LAYER,
    ground_layer: Layer = MTL_SB_HFSS_GROUND_LAYER,
    substrate_footprint_layer: Layer = MTL_SB_HFSS_SUBSTRATE_FOOTPRINT_LAYER,
    port_sheet_layer: Layer = LAYER.D0_TOP_SIM_BOUNDARY,
) -> gf.Component:
    """Return the whole four-terminal straight--bend block as an HFSS coupon.

    The two physical signal conductors, finite ground, four terminal boundary
    sheets, and substrate footprint are in GDS. HFSS imports the metal and port
    geometry as zero-thickness sheets; the enclosing vacuum remains a solver
    Region and is intentionally absent from GDS.
    """

    xs = gf.get_cross_section(cross_section)
    resolved_terminal_clearance_um = (
        float(xs[CPW_ETCH_NEG].width)
        if terminal_open_clearance_um is None
        else float(terminal_open_clearance_um)
    )
    for name, value in (
        ("terminal_open_clearance_um", resolved_terminal_clearance_um),
        ("coupon_margin_um", coupon_margin_um),
    ):
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive, got {value!r}.")
    if (
        len(
            {
                signal_p_layer,
                signal_r_layer,
                ground_layer,
                substrate_footprint_layer,
                port_sheet_layer,
            }
        )
        != 5
    ):
        raise ValueError("HFSS signal, ground, substrate, and port-sheet layers must be distinct.")

    geometry = mtl_straight_bend_coupling_section(
        coupled_length=coupled_length,
        inter_trace_ground_width=inter_trace_ground_width,
        bend_radius=bend_radius,
        cross_section=cross_section,
    )
    layers = geometry.info["layers"]
    draw_layer = tuple(layers["draw"])
    ground_mask_layer = tuple(layers["ground_mask"])
    signals = geometry.get_region(draw_layer, merge=True)
    ground_opening = geometry.get_region(ground_mask_layer, merge=True)
    if signals.count() != 2 or ground_opening.is_empty():
        raise ValueError("SB geometry must contain two signals and its ground-mask opening.")

    signal_polygons = {
        "signal_p": _signal_polygon_at_port(
            signals,
            port=geometry.ports["p_left"],
            dbu_um=geometry.kcl.dbu,
        ),
        "signal_r": _signal_polygon_at_port(
            signals,
            port=geometry.ports["r_left"],
            dbu_um=geometry.kcl.dbu,
        ),
    }
    if signal_polygons["signal_p"] == signal_polygons["signal_r"]:
        raise ValueError("SB traces must remain separate conductors.")

    terminal_opening_width_um = float(xs[CPW_GROUND_MASK].width)
    clearance_rectangle = gf.components.rectangle(
        size=(resolved_terminal_clearance_um, terminal_opening_width_um),
        centered=True,
        layer=ground_mask_layer,
    )
    clearances = gf.Component()
    for name in geometry.info["ordered_port_names"]:
        port = geometry.ports[name]
        angle = float(port.orientation) * pi / 180
        clearance = clearances << clearance_rectangle
        clearance.drotate(float(port.orientation))
        clearance.dmove(
            (
                float(port.x) + resolved_terminal_clearance_um / 2 * cos(angle),
                float(port.y) + resolved_terminal_clearance_um / 2 * sin(angle),
            )
        )
    ground_opening += clearances.get_region(ground_mask_layer, merge=True)
    ground_opening.merge()

    bounds = ground_opening.bbox()
    margin_dbu = round(coupon_margin_um / geometry.kcl.dbu)
    coupon_box = kdb.Box(
        bounds.left - margin_dbu,
        bounds.bottom - margin_dbu,
        bounds.right + margin_dbu,
        bounds.top + margin_dbu,
    )
    ground = kdb.Region(coupon_box) - ground_opening
    if ground.is_empty():
        raise ValueError("Coupon ground is empty after subtracting the ground-mask opening.")

    coupon = gf.Component()
    signal_layers = {"signal_p": signal_p_layer, "signal_r": signal_r_layer}
    for name, polygon in signal_polygons.items():
        coupon.add_polygon(kdb.Region(polygon), layer=signal_layers[name])
    coupon.add_polygon(ground, layer=ground_layer)
    coupon.add_polygon(kdb.Region(coupon_box), layer=substrate_footprint_layer)
    coupon.add_polygon(clearances.get_region(ground_mask_layer), layer=port_sheet_layer)
    coupon.flatten(merge=True)
    port_signals = {
        "r_left": "signal_r",
        "r_right": "signal_r",
        "p_left": "signal_p",
        "p_right": "signal_p",
    }
    for name in geometry.info["ordered_port_names"]:
        coupon.add_port(
            name=name, port=geometry.ports[name], layer=signal_layers[port_signals[name]]
        )

    bbox_um = {
        "xmin": coupon_box.left * geometry.kcl.dbu,
        "ymin": coupon_box.bottom * geometry.kcl.dbu,
        "xmax": coupon_box.right * geometry.kcl.dbu,
        "ymax": coupon_box.top * geometry.kcl.dbu,
    }
    terminal_ports = {}
    for name in geometry.info["ordered_port_names"]:
        port = geometry.ports[name]
        angle = float(port.orientation) * pi / 180
        dx = resolved_terminal_clearance_um * cos(angle)
        dy = resolved_terminal_clearance_um * sin(angle)
        terminal_ports[name] = {
            "signal": port_signals[name],
            "reference": "finite_ground",
            "sheet": "port_sheets",
            "sheet_center_um": (
                float(port.x) + dx / 2,
                float(port.y) + dy / 2,
                0.0,
            ),
            "integration_line_um": (
                (float(port.x), float(port.y), 0.0),
                (float(port.x) + dx, float(port.y) + dy, 0.0),
            ),
            "center_um": tuple(float(value) for value in port.center),
            "orientation_deg": int(port.orientation),
        }
    coupon.info["hfss_coupon"] = {
        "schema": "orpen-mtl-straight-bend-coupling-section-hfss-coupon.v1",
        "topology": "mtl_straight_bend_coupling_section",
        "terminal_order": geometry.info["ordered_port_names"],
        "layers": {
            "signal_p": {
                "layer": signal_p_layer,
                "material_role": "metal",
                "zmin": 0.0,
                "thickness": 0.0,
            },
            "signal_r": {
                "layer": signal_r_layer,
                "material_role": "metal",
                "zmin": 0.0,
                "thickness": 0.0,
            },
            "finite_ground": {
                "layer": ground_layer,
                "material_role": "metal",
                "zmin": 0.0,
                "thickness": 0.0,
            },
            "substrate": {
                "layer": substrate_footprint_layer,
                "material_role": "substrate",
                "zmin": -SUBSTRATE_THICKNESS_UM,
                "thickness": SUBSTRATE_THICKNESS_UM,
            },
            "port_sheets": {
                "layer": tuple(int(value) for value in gf.get_layer_tuple(port_sheet_layer)),
                "material_role": "boundary",
                "zmin": 0.0,
                "thickness": 0.0,
            },
        },
        "terminal_ports": terminal_ports,
        "coupon_bbox_um": bbox_um,
        "substrate_footprint_bbox_um": bbox_um,
        "coupon_margin_um": float(coupon_margin_um),
        "terminal_open_clearance_um": resolved_terminal_clearance_um,
        "vacuum_geometry": "PyAEDT Region; intentionally absent from GDS",
    }
    return coupon


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
