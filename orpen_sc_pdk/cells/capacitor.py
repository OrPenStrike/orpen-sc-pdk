"""Public capacitor primitives."""

from __future__ import annotations

from itertools import chain
from math import ceil, cos, isfinite, radians, sin

import gdsfactory as gf
from gdsfactory import kdb
from gdsfactory.typings import CrossSectionSpec, Layer

from orpen_sc_pdk.helpers.layout import add_etch_for_component
from orpen_sc_pdk.tech import LAYER

# These GDS layers identify Q3D coupon conductors only.  They are not process
# layers and must not be used in fabrication layout.
IDC_Q3D_SIGNAL_1_LAYER: Layer = (901, 0)
IDC_Q3D_SIGNAL_2_LAYER: Layer = (902, 0)
IDC_Q3D_GROUND_LAYER: Layer = (903, 0)
IDC_Q3D_SUBSTRATE_FOOTPRINT_LAYER: Layer = (904, 0)


@gf.cell(tags=["elements"])
def interdigital_capacitor(
    fingers: int = 20,
    finger_length: float = 100.0,
    finger_gap: float = 3.3,
    finger_width: float = 3.3,
    taper_length: float = 150.0,
    terminal_extension_length_um: float = 100.0,
    capacitor_ground_gap: float = 85.0,
    cpw_xs: CrossSectionSpec = "coplanar_waveguide",
    half: bool = False,
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Return an IDC with symmetric CPW terminal extensions and derived etch.

    The public ports are the outer CPW cut planes: standalone terminals remain
    open for Q3D extraction, while assembled CPW routes connect at those planes.
    """

    xs = gf.get_cross_section(cpw_xs)
    cpw_width = xs["cpw_draw"].width
    cpw_gap = xs["cpw_etch_pos"].width

    component = gf.Component()
    core_capacitor_temp = gf.Component()
    if fingers < 1:
        raise ValueError("fingers must be at least 1.")
    if not isfinite(terminal_extension_length_um) or terminal_extension_length_um <= 0:
        raise ValueError(
            "terminal_extension_length_um must be finite and positive, "
            f"got {terminal_extension_length_um!r}."
        )

    width = finger_length + finger_gap if not half else finger_length
    height = fingers * finger_width + (fingers - 1) * finger_gap

    points_1 = [
        (0, 0),
        (0, height),
        (finger_length, height),
        (finger_length, height - finger_width),
        (0, height - finger_width),
        *chain.from_iterable(
            (
                (0, height - (2 * index) * (finger_width + finger_gap)),
                (
                    finger_length,
                    height - (2 * index) * (finger_width + finger_gap),
                ),
                (
                    finger_length,
                    height - (2 * index) * (finger_width + finger_gap) - finger_width,
                ),
                (
                    0,
                    height - (2 * index) * (finger_width + finger_gap) - finger_width,
                ),
            )
            for index in range(ceil(fingers / 2))
        ),
        (0, 0),
    ]
    core_capacitor_temp.add_polygon(points=points_1, layer=draw_layer)

    if not half:
        points_2 = [
            (width, 0),
            (width, height),
            *chain.from_iterable(
                (
                    (width, height - (2 * index + 1) * (finger_width + finger_gap)),
                    (
                        width - finger_length,
                        height - (2 * index + 1) * (finger_width + finger_gap),
                    ),
                    (
                        width - finger_length,
                        height - (2 * index + 1) * (finger_width + finger_gap) - finger_width,
                    ),
                    (
                        width,
                        height - (2 * index + 1) * (finger_width + finger_gap) - finger_width,
                    ),
                )
                for index in range(fingers // 2)
            ),
        ]
        core_capacitor_temp.add_polygon(points=points_2, layer=draw_layer)

    core_capacitor = component << core_capacitor_temp
    core_capacitor.move((-core_capacitor_temp.x, -core_capacitor_temp.y))

    in_taper = component << gf.components.taper(
        length=taper_length,
        width1=cpw_width,
        width2=height,
        layer=draw_layer,
    )
    in_taper.movex(-(taper_length + core_capacitor_temp.x))
    out_taper = component << gf.components.taper(
        length=taper_length,
        width1=height,
        width2=cpw_width,
        layer=draw_layer,
    )
    out_taper.movex(core_capacitor_temp.x)

    terminal_extension = gf.path.extrude(
        gf.path.straight(terminal_extension_length_um),
        width=cpw_width,
        layer=draw_layer,
    )
    in_extension = component << terminal_extension
    in_extension.dmovex(in_taper.xmin - in_extension.xmax)
    out_extension = component << terminal_extension
    out_extension.dmovex(out_taper.xmax - out_extension.xmin)

    component.add_port(
        name="o_capacitor_in",
        center=(component.xmin, 0),
        width=cpw_width,
        orientation=180,
        layer=draw_layer,
    )
    component.add_port(
        name="o_capacitor_out",
        center=(component.xmax, 0),
        width=cpw_width,
        orientation=0,
        layer=draw_layer,
    )

    mask_points = [
        (component.xmin, cpw_width / 2 + cpw_gap),
        (in_taper.xmin, cpw_width / 2 + cpw_gap),
        (core_capacitor.xmin, height / 2 + capacitor_ground_gap),
        (core_capacitor.xmax, height / 2 + capacitor_ground_gap),
        (out_taper.xmax, cpw_width / 2 + cpw_gap),
        (component.xmax, cpw_width / 2 + cpw_gap),
        (component.xmax, -cpw_width / 2 - cpw_gap),
        (out_taper.xmax, -cpw_width / 2 - cpw_gap),
        (core_capacitor.xmax, -height / 2 - capacitor_ground_gap),
        (core_capacitor.xmin, -height / 2 - capacitor_ground_gap),
        (in_taper.xmin, -cpw_width / 2 - cpw_gap),
        (component.xmin, -cpw_width / 2 - cpw_gap),
    ]
    component.add_polygon(points=mask_points, layer=ground_mask_layer)

    result = add_etch_for_component(
        component=component,
        draw_layer=draw_layer,
        mask_layer=ground_mask_layer,
        etch_layer=etch_layer,
    )
    result.info["cpw_gap_um"] = float(cpw_gap)
    return result


def prepare_interdigital_capacitor_q3d_geometry(
    component: gf.Component,
    *,
    terminal_open_clearance_um: float,
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Return an IDC copy whose two public terminals are open to coupon ground."""

    if not isfinite(terminal_open_clearance_um) or terminal_open_clearance_um <= 0:
        raise ValueError(
            "terminal_open_clearance_um must be finite and positive, "
            f"got {terminal_open_clearance_um!r}."
        )

    required_ports = {"o_capacitor_in": 180, "o_capacitor_out": 0}
    if {port.name for port in component.ports} != set(required_ports):
        raise ValueError("component must expose only o_capacitor_in and o_capacitor_out.")
    for name, orientation in required_ports.items():
        if component.ports[name].orientation != orientation:
            raise ValueError(f"{name} must have orientation {orientation} degrees.")

    cpw_gap_um = float(component.info.get("cpw_gap_um", 0.0))
    if not isfinite(cpw_gap_um) or cpw_gap_um <= 0:
        raise ValueError("component must record a finite positive cpw_gap_um.")
    if component.get_region(draw_layer, merge=True).count() != 2:
        raise ValueError("component must contain exactly two IDC signal conductors.")
    if component.get_region(ground_mask_layer, merge=True).is_empty():
        raise ValueError("component must contain an IDC ground-mask opening.")

    prepared = gf.Component()
    idc_ref = prepared << component
    prepared.add_ports(idc_ref.ports)
    for name, direction in (("o_capacitor_in", -1.0), ("o_capacitor_out", 1.0)):
        port = idc_ref.ports[name]
        clearance = prepared << gf.components.rectangle(
            size=(terminal_open_clearance_um, float(port.width) + 2 * cpw_gap_um),
            centered=True,
            layer=ground_mask_layer,
        )
        clearance.dmove((float(port.x) + direction * terminal_open_clearance_um / 2, float(port.y)))

    prepared.flatten(merge=False)
    result = add_etch_for_component(
        component=prepared,
        draw_layer=draw_layer,
        mask_layer=ground_mask_layer,
        etch_layer=etch_layer,
    )
    result.flatten(merge=True)
    result.info.update(component.info.model_dump())
    result.info["q3d_terminal_open_clearance_um"] = float(terminal_open_clearance_um)
    return result


def _signal_polygon_at_port(
    signal_region: kdb.Region,
    *,
    port: gf.Port,
    dbu_um: float,
) -> kdb.Polygon:
    """Return the unique signal polygon connected just inside one named IDC port."""

    orientation = port.orientation
    if orientation is None:
        raise ValueError(f"{port.name} must have an orientation.")
    probe_distance_um = max(dbu_um, float(port.width) / 4)
    angle = radians(float(orientation))
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
def interdigital_capacitor_q3d_coupon(
    fingers: int = 20,
    finger_length: float = 100.0,
    finger_gap: float = 3.3,
    finger_width: float = 3.3,
    taper_length: float = 150.0,
    terminal_extension_length_um: float = 100.0,
    capacitor_ground_gap: float = 85.0,
    terminal_open_clearance_um: float = 25.0,
    coupon_margin_um: float = 100.0,
    cpw_xs: CrossSectionSpec = "coplanar_waveguide",
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    signal_1_layer: Layer = IDC_Q3D_SIGNAL_1_LAYER,
    signal_2_layer: Layer = IDC_Q3D_SIGNAL_2_LAYER,
    ground_layer: Layer = IDC_Q3D_GROUND_LAYER,
    substrate_footprint_layer: Layer = IDC_Q3D_SUBSTRATE_FOOTPRINT_LAYER,
) -> gf.Component:
    """Return a planar Q3D IDC coupon with port-bound signal conductor layers.

    ``signal_1`` is bound to ``o_capacitor_in`` and ``signal_2`` to
    ``o_capacitor_out``.  The substrate footprint is present in GDS and its
    layer mapping extrudes it into the finite dielectric volume.  Only the
    enclosing vacuum is a PyAEDT Region and is intentionally absent from GDS.
    """

    if not isfinite(coupon_margin_um) or coupon_margin_um <= 0:
        raise ValueError(f"coupon_margin_um must be finite and positive, got {coupon_margin_um!r}.")
    if len({signal_1_layer, signal_2_layer, ground_layer, substrate_footprint_layer}) != 4:
        raise ValueError("Q3D signal, ground, and substrate-footprint layers must be distinct.")

    idc = interdigital_capacitor(
        fingers=fingers,
        finger_length=finger_length,
        finger_gap=finger_gap,
        finger_width=finger_width,
        taper_length=taper_length,
        terminal_extension_length_um=terminal_extension_length_um,
        capacitor_ground_gap=capacitor_ground_gap,
        cpw_xs=cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    prepared = prepare_interdigital_capacitor_q3d_geometry(
        idc,
        terminal_open_clearance_um=terminal_open_clearance_um,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    signals = prepared.get_region(draw_layer, merge=True)
    ground_opening = prepared.get_region(ground_mask_layer, merge=True)
    if signals.count() != 2 or ground_opening.is_empty():
        raise ValueError("Prepared IDC must contain two signals and a non-empty ground opening.")

    signal_1 = _signal_polygon_at_port(
        signals,
        port=prepared.ports["o_capacitor_in"],
        dbu_um=prepared.kcl.dbu,
    )
    signal_2 = _signal_polygon_at_port(
        signals,
        port=prepared.ports["o_capacitor_out"],
        dbu_um=prepared.kcl.dbu,
    )
    if signal_1 == signal_2:
        raise ValueError("IDC public ports must bind distinct signal conductors.")

    bounds = (signals + ground_opening).bbox()
    margin_dbu = round(coupon_margin_um / prepared.kcl.dbu)
    coupon_box = kdb.Box(
        bounds.left - margin_dbu,
        bounds.bottom - margin_dbu,
        bounds.right + margin_dbu,
        bounds.top + margin_dbu,
    )
    domain = gf.Component()
    domain.add_polygon(kdb.Region(coupon_box), layer=ground_layer)
    ground = gf.boolean(
        A=domain,
        B=prepared,
        operation="A-B",
        layer=ground_layer,
        layer1=ground_layer,
        layer2=ground_mask_layer,
    )
    if ground.get_region(ground_layer, merge=True).is_empty():
        raise ValueError("Coupon ground is empty after subtracting the ground-mask opening.")

    coupon = gf.Component()
    coupon.add_polygon(kdb.Region(signal_1), layer=signal_1_layer)
    coupon.add_polygon(kdb.Region(signal_2), layer=signal_2_layer)
    coupon << ground
    coupon.add_polygon(kdb.Region(coupon_box), layer=substrate_footprint_layer)
    coupon.flatten(merge=True)

    coupon.add_port(
        name="o_capacitor_in",
        port=prepared.ports["o_capacitor_in"],
        layer=signal_1_layer,
    )
    coupon.add_port(
        name="o_capacitor_out",
        port=prepared.ports["o_capacitor_out"],
        layer=signal_2_layer,
    )
    bbox_um = {
        "xmin": coupon_box.left * prepared.kcl.dbu,
        "ymin": coupon_box.bottom * prepared.kcl.dbu,
        "xmax": coupon_box.right * prepared.kcl.dbu,
        "ymax": coupon_box.top * prepared.kcl.dbu,
    }
    coupon.info["q3d_coupon"] = {
        "schema": "orpen-idc-q3d-planar-coupon.v1",
        "node_ports": {
            "signal_1": "o_capacitor_in",
            "signal_2": "o_capacitor_out",
            "ground": None,
        },
        "layers": {
            "signal_1": signal_1_layer,
            "signal_2": signal_2_layer,
            "finite_ground": ground_layer,
            "substrate_footprint": substrate_footprint_layer,
        },
        "coupon_bbox_um": bbox_um,
        "substrate_footprint_bbox_um": bbox_um,
        "terminal_open_clearance_um": float(terminal_open_clearance_um),
        "coupon_margin_um": float(coupon_margin_um),
        "vacuum_geometry": "PyAEDT Region; intentionally absent from GDS",
    }
    return coupon
