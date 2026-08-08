"""Spring 2025 intrinsic individual Purcell filter test chip."""

from __future__ import annotations

from math import isfinite

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec, Layer

from orpen_sc_pdk.tech import LAYER


@gf.cell(tags=["chips"])
def spring2025_intrinsic_individual_purcell_filter_test_chip(
    chip_width: float = 5000.0,
    chip_height: float = 5000.0,
    pad_reference_x: float = 2450.0,
    feedline_y: float = -2200.0,
    cpw_xs: CrossSectionSpec = "cpw_6_7_6",
    cpw_radius: float = 100.0,
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    sim_boundary_layer: Layer = LAYER.D0_TOP_SIM_BOUNDARY,
) -> gf.Component:
    """Return a 5000x5000 preview test chip with one Purcell-filter pair and feedline."""

    dicing_edge_width = 50.0

    for name, value in (
        ("chip_width", chip_width),
        ("chip_height", chip_height),
        ("pad_reference_x", pad_reference_x),
        ("feedline_y", feedline_y),
        ("cpw_radius", cpw_radius),
    ):
        if not isfinite(value):
            raise ValueError(f"{name} must be finite, got {value!r}.")
        if value <= 0 and name != "feedline_y":
            raise ValueError(f"{name} must be positive, got {value!r}.")

    if pad_reference_x >= chip_width / 2:
        raise ValueError(
            "pad_reference_x must leave room inside the dicing edge. "
            f"Got pad_reference_x={pad_reference_x!r}, chip_width={chip_width!r}."
        )
    if abs(feedline_y) > chip_height / 2:
        raise ValueError(
            "feedline_y must lie inside the chip bounds. "
            f"Got feedline_y={feedline_y!r}, chip_height={chip_height!r}."
        )

    c = gf.Component()
    c << gf.get_component(
        "dicing_edge",
        size=(chip_width, chip_height),
        width=dicing_edge_width,
        layer=etch_layer,
    )

    pair_comp = gf.get_component(
        "capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators"
    )
    pair = c << pair_comp
    pair.move(origin=(pair.center[0], pair.center[1]), destination=(0.0, 0.0))

    pair_port = pair.ports["o_feedline_coupling"]
    t = c << gf.get_component(
        "cpw_t_junction",
        trunk_length=200.0,
        branch_length=100.0,
        cross_section=cpw_xs,
    )
    t.move(
        origin=(t.center[0], t.center[1]),
        destination=(pair_port.x, feedline_y),
    )
    t.dmovey(feedline_y - t.ports["o1"].y)

    launcher = gf.get_component(
        "launcher",
        cpw_xs=cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        sim_boundary_layer=sim_boundary_layer,
    )

    left_launcher = c << launcher
    left_launcher.move(
        origin=left_launcher.ports["o_pad"].center,
        destination=(-pad_reference_x, feedline_y),
    )
    right_launcher = c << launcher
    right_launcher.rotate(180)
    right_launcher.move(
        origin=right_launcher.ports["o_pad"].center,
        destination=(pad_reference_x, feedline_y),
    )

    route_xs = gf.get_cross_section(
        cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=cpw_radius,
    )

    left_route_length = t.ports["o1"].x - left_launcher.ports["o_neck"].x
    if left_route_length <= 0:
        raise ValueError(
            f"Left launch-leg cannot be routed with non-positive length {left_route_length!r}."
        )
    left_route = c << gf.path.extrude(
        gf.path.straight(left_route_length),
        cross_section=route_xs,
    )
    left_route.connect("o1", left_launcher.ports["o_neck"])
    if (
        abs(left_route.ports["o2"].x - t.ports["o1"].x) > 1e-3
        or abs(left_route.ports["o2"].y - t.ports["o1"].y) > 1e-3
    ):
        raise ValueError("Left feed route does not land on T-junction o1.")

    right_route_length = right_launcher.ports["o_neck"].x - t.ports["o2"].x
    if right_route_length <= 0:
        raise ValueError(
            f"Right launch-leg cannot be routed with non-positive length {right_route_length!r}."
        )
    right_route = c << gf.path.extrude(
        gf.path.straight(right_route_length),
        cross_section=route_xs,
    )
    right_route.connect("o2", right_launcher.ports["o_neck"])
    if (
        abs(right_route.ports["o1"].x - t.ports["o2"].x) > 1e-3
        or abs(right_route.ports["o1"].y - t.ports["o2"].y) > 1e-3
    ):
        raise ValueError("Right feed route does not land on T-junction o2.")

    pair_branch_length = pair_port.y - t.ports["o_branch"].y
    if pair_branch_length <= 0:
        raise ValueError(
            "pair o_feedline_coupling must lie above T branch origin. "
            f"Got pair.y={pair_port.y!r}, branch_origin={t.ports['o_branch'].y!r}."
        )
    branch_route = c << gf.path.extrude(
        gf.path.straight(pair_branch_length),
        cross_section=route_xs,
    )
    branch_route.drotate(-90)
    branch_route.connect("o2", t.ports["o_branch"])
    if (
        abs(branch_route.ports["o1"].x - pair_port.x) > 1e-3
        or abs(branch_route.ports["o1"].y - pair_port.y) > 1e-3
    ):
        raise ValueError("Branch route does not land on pair o_feedline_coupling.")

    dicing_half_x = chip_width / 2 + dicing_edge_width
    dicing_half_y = chip_height / 2 + dicing_edge_width
    bbox = c.bbox()
    if (
        bbox.left < -dicing_half_x - 1e-6
        or bbox.right > dicing_half_x + 1e-6
        or bbox.bottom < -dicing_half_y - 1e-6
        or bbox.top > dicing_half_y + 1e-6
    ):
        raise ValueError("Functional chip geometry extends beyond the dicing-edge outer boundary.")

    c.add_port("o1", port=left_launcher.ports["o_pad"])
    c.add_port("o2", port=right_launcher.ports["o_pad"])
    if "o_lumped" in left_launcher.ports:
        c.add_port("o_lumped_left", port=left_launcher.ports["o_lumped"])
    if "o_lumped" in right_launcher.ports:
        c.add_port("o_lumped_right", port=right_launcher.ports["o_lumped"])

    c.info["topology"] = "spring2025_intrinsic_individual_purcell_filter_test_chip"
    c.info["ordered_port_names"] = ("o1", "o2")
    c.info["pair_topology"] = pair_comp.info.get("topology")
    c.info["pair_ports"] = tuple(port.name for port in pair.ports)
    c.info["pad_reference_x"] = float(pad_reference_x)
    c.info["feedline_y"] = float(feedline_y)
    c.info["junction_ports"] = {
        "o1": t.ports["o1"].center,
        "o2": t.ports["o2"].center,
        "o_branch": t.ports["o_branch"].center,
    }

    return c


__all__ = ["spring2025_intrinsic_individual_purcell_filter_test_chip"]
