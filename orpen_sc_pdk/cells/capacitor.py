"""Public capacitor primitives."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import chain
from math import ceil, cos, isfinite, radians, sin

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec, Layer

from orpen_sc_pdk.helpers.layout import add_etch_for_component
from orpen_sc_pdk.tech import LAYER

# These GDS layers identify Q3D coupon conductors only.  They are not process
# layers and must not be used in fabrication layout.
IDC_Q3D_SIGNAL_1_LAYER: Layer = (901, 0)
IDC_Q3D_SIGNAL_2_LAYER: Layer = (902, 0)
IDC_Q3D_GROUND_LAYER: Layer = (903, 0)
IDC_Q3D_SUBSTRATE_FOOTPRINT_LAYER: Layer = (904, 0)
_Q3D_BBOX_LAYER: Layer = (9701, 0)
_PORT_PROBE_LAYER: Layer = (9702, 0)


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
    source = component.copy() if getattr(component, "locked", False) else component
    signal_polygons_by_layer = source.get_polygons_points(
        merge=True,
        by="tuple",
        layers=[draw_layer],
    )
    signal_polygon_count = sum(len(polygons) for polygons in signal_polygons_by_layer.values())
    if signal_polygon_count != 2:
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
    signal_polygons: list[Sequence[tuple[float, float]]],
    *,
    port: gf.Port,
    bind_layer: Layer,
    dbu_um: float,
) -> list[tuple[float, float]]:
    """Return the unique signal polygon connected just inside one named IDC port."""

    orientation = port.orientation
    if orientation is None:
        raise ValueError(f"{port.name} must have an orientation.")
    if not signal_polygons:
        raise ValueError("signal_polygons must contain at least one polygon.")
    probe_distance_um = max(dbu_um, float(port.width) / 4)
    angle = radians(float(orientation))
    probe = (
        float(port.x) - probe_distance_um * cos(angle),
        float(port.y) - probe_distance_um * sin(angle),
    )
    probe_shape = gf.components.rectangle(
        size=(dbu_um, dbu_um),
        centered=True,
        layer=bind_layer,
    )
    matches = []
    for polygon in signal_polygons:
        polygon_shape = gf.Component()
        polygon_shape.add_polygon(points=polygon, layer=bind_layer)

        probe_component = gf.Component()
        probe_ref = probe_component << probe_shape
        probe_ref.dmove(probe)

        # `gf.boolean` is used only as a boolean probe; keep the temporary
        # construction local so no intermediate artifacts are retained.
        overlap = gf.boolean(
            A=polygon_shape,
            B=probe_ref,
            operation="and",
            layer=bind_layer,
            layer1=bind_layer,
            layer2=bind_layer,
        )
        if not overlap.get_region(bind_layer, merge=True).is_empty():
            matches.append([(float(point[0]), float(point[1])) for point in polygon])
    if len(matches) != 1:
        raise ValueError(
            f"{port.name} must identify exactly one connected signal conductor, got {len(matches)}."
        )
    return [(float(point[0]), float(point[1])) for point in matches[0]]


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
    signal_polygons_by_layer = prepared.get_polygons_points(
        merge=True,
        by="tuple",
        layers=[draw_layer],
    )
    signal_polygons = [
        polygon for polygons in signal_polygons_by_layer.values() for polygon in polygons
    ]
    ground_opening = prepared.get_region(ground_mask_layer, merge=True)
    if len(signal_polygons) != 2 or ground_opening.is_empty():
        raise ValueError("Prepared IDC must contain two signals and a non-empty ground opening.")

    signal_1 = _signal_polygon_at_port(
        signal_polygons,
        port=prepared.ports["o_capacitor_in"],
        bind_layer=_PORT_PROBE_LAYER,
        dbu_um=prepared.kcl.dbu,
    )
    signal_2 = _signal_polygon_at_port(
        signal_polygons,
        port=prepared.ports["o_capacitor_out"],
        bind_layer=_PORT_PROBE_LAYER,
        dbu_um=prepared.kcl.dbu,
    )
    if signal_1 == signal_2:
        raise ValueError("IDC public ports must bind distinct signal conductors.")

    footprint = gf.Component()
    for polygons in prepared.get_polygons_points(
        merge=True,
        by="tuple",
        layers=[draw_layer, ground_mask_layer],
    ).values():
        for polygon in polygons:
            footprint.add_polygon(points=polygon, layer=_Q3D_BBOX_LAYER)
    bbox_um = footprint.dbbox()
    if bbox_um is None:
        raise ValueError("Failed to evaluate capacitor footprint for Q3D coupon bounds.")
    dbu = prepared.kcl.dbu
    margin_dbu = round(coupon_margin_um / dbu)
    coupon_box_snapped = {
        "left": (round(bbox_um.left / dbu) - margin_dbu) * dbu,
        "bottom": (round(bbox_um.bottom / dbu) - margin_dbu) * dbu,
        "right": (round(bbox_um.right / dbu) + margin_dbu) * dbu,
        "top": (round(bbox_um.top / dbu) + margin_dbu) * dbu,
    }
    coupon_box_width = coupon_box_snapped["right"] - coupon_box_snapped["left"]
    coupon_box_height = coupon_box_snapped["top"] - coupon_box_snapped["bottom"]

    domain = gf.Component()
    domain_shape = gf.components.rectangle(
        size=(coupon_box_width, coupon_box_height),
        centered=False,
        layer=ground_layer,
    )
    domain_ref = domain << domain_shape
    domain_ref.dmove((coupon_box_snapped["left"], coupon_box_snapped["bottom"]))
    domain_box = domain.dbbox()
    if domain_box is None:
        raise ValueError("Failed to compute domain physical dbbox during Q3D coupon assembly.")
    domain_expected = {
        "xmin": coupon_box_snapped["left"],
        "ymin": coupon_box_snapped["bottom"],
        "xmax": coupon_box_snapped["right"],
        "ymax": coupon_box_snapped["top"],
    }
    domain_actual = {
        "xmin": domain_box.left,
        "ymin": domain_box.bottom,
        "xmax": domain_box.right,
        "ymax": domain_box.top,
    }
    if any(
        abs(domain_actual[key] - domain_expected[key]) > prepared.kcl.dbu for key in domain_expected
    ):
        raise ValueError("Q3D domain dbbox deviates from requested physical coupon box.")
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
    coupon.add_polygon(points=signal_1, layer=signal_1_layer)
    coupon.add_polygon(points=signal_2, layer=signal_2_layer)
    coupon << ground
    substrate_footprint = gf.components.rectangle(
        size=(coupon_box_width, coupon_box_height),
        centered=False,
        layer=substrate_footprint_layer,
    )
    substrate_ref = coupon << substrate_footprint
    substrate_ref.dmove((coupon_box_snapped["left"], coupon_box_snapped["bottom"]))
    substrate_box = substrate_ref.dbbox()
    if substrate_box is None:
        raise ValueError(
            "Failed to compute substrate reference physical dbbox during Q3D coupon assembly."
        )
    substrate_actual = {
        "xmin": substrate_box.left,
        "ymin": substrate_box.bottom,
        "xmax": substrate_box.right,
        "ymax": substrate_box.top,
    }
    if any(
        abs(substrate_actual[key] - domain_actual[key]) > prepared.kcl.dbu
        for key in domain_expected
    ):
        raise ValueError(
            "Q3D substrate reference dbbox deviates from requested physical coupon box."
        )
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
    coupon_box_check = coupon.dbbox()
    if coupon_box_check is None:
        raise ValueError("Failed to compute final Q3D coupon dbbox.")
    coupon_actual = {
        "xmin": coupon_box_check.left,
        "ymin": coupon_box_check.bottom,
        "xmax": coupon_box_check.right,
        "ymax": coupon_box_check.top,
    }
    coupon_box_um = {
        "xmin": domain_actual["xmin"],
        "ymin": domain_actual["ymin"],
        "xmax": domain_actual["xmax"],
        "ymax": domain_actual["ymax"],
    }
    if any(abs(coupon_actual[key] - coupon_box_um[key]) > coupon.kcl.dbu for key in coupon_box_um):
        raise ValueError("Q3D final coupon dbbox deviates from requested physical coupon box.")
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
        "coupon_bbox_um": coupon_box_um,
        "substrate_footprint_bbox_um": coupon_box_um,
        "terminal_open_clearance_um": float(terminal_open_clearance_um),
        "coupon_margin_um": float(coupon_margin_um),
        "vacuum_geometry": "PyAEDT Region; intentionally absent from GDS",
    }
    return coupon
