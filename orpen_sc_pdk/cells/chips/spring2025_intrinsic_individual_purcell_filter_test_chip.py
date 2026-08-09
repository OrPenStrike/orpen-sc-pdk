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
    cpw_xs: CrossSectionSpec = "cpw_6_7_6",
    cpw_radius: float = 100.0,
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    sim_boundary_layer: Layer = LAYER.D0_TOP_SIM_BOUNDARY,
    t_branch_length: float = 100.0,
) -> gf.Component:
    """Return a 5000x5000 preview test chip with one Purcell-filter pair and feedline."""

    dicing_edge_width = 50.0

    for name, value in (
        ("chip_width", chip_width),
        ("chip_height", chip_height),
        ("cpw_radius", cpw_radius),
        ("t_branch_length", t_branch_length),
    ):
        if not isfinite(value):
            raise ValueError(f"{name} must be finite, got {value!r}.")
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value!r}.")

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
    t = c << gf.get_component(
        "cpw_t_junction",
        trunk_length=200.0,
        branch_length=t_branch_length,
        cross_section=cpw_xs,
    )
    pair.connect("o_feedline_coupling", t.ports["o_branch"])

    launcher = gf.get_component(
        "launcher",
        cpw_xs=cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        sim_boundary_layer=sim_boundary_layer,
    )

    left_launcher = c << launcher
    left_launcher.movex(-chip_width / 2 + dicing_edge_width - left_launcher.xmin)
    left_launcher.movey(-left_launcher.ports["o_pad"].y)
    right_launcher = c << launcher
    right_launcher.rotate(180)
    right_launcher.movex(chip_width / 2 - dicing_edge_width - right_launcher.xmax)
    right_launcher.movey(-right_launcher.ports["o_pad"].y)

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

    if (
        abs(pair.ports["o_feedline_coupling"].x - t.ports["o_branch"].x) > 1e-6
        or abs(pair.ports["o_feedline_coupling"].y - t.ports["o_branch"].y) > 1e-6
    ):
        raise ValueError("Pair IDC-to-T o_branch connection is not coincident.")
    if abs(left_route_length - right_route_length) > 1e-6:
        raise ValueError(
            "Launcher-to-T feed route lengths are not symmetric. "
            f"Got left={left_route_length!r}, right={right_route_length!r}."
        )

    chip_half_x = chip_width / 2
    chip_half_y = chip_height / 2
    functional_bbox = pair.bbox() + t.bbox() + left_launcher.bbox() + right_launcher.bbox()
    functional_bbox += left_route.bbox()
    functional_bbox += right_route.bbox()
    if (
        functional_bbox.left < -chip_half_x - 1e-6
        or functional_bbox.right > chip_half_x + 1e-6
        or functional_bbox.bottom < -chip_half_y - 1e-6
        or functional_bbox.top > chip_half_y + 1e-6
    ):
        raise ValueError("Functional chip geometry extends beyond the 5000x5000 inner opening.")

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
    c.info["chip_inner_size_um"] = (float(chip_width), float(chip_height))
    c.info["dicing_edge_width_um"] = float(dicing_edge_width)
    c.info["launcher_positions"] = {
        "left_bbox_left_um": float(left_launcher.xmin),
        "right_bbox_right_um": float(right_launcher.xmax),
        "left_clearance_to_inner_left_um": float(left_launcher.xmin + chip_width / 2),
        "right_clearance_to_inner_right_um": float(chip_width / 2 - right_launcher.xmax),
    }
    c.info["launch_routes_um"] = {
        "left_route_length": float(left_route_length),
        "right_route_length": float(right_route_length),
        "route_length_delta_um": float(left_route_length - right_route_length),
    }
    c.info["junction_ports"] = {
        "junction_center": ((t.ports["o1"].x + t.ports["o2"].x) / 2, t.ports["o1"].y),
        "o1": t.ports["o1"].center,
        "o2": t.ports["o2"].center,
        "o_branch": t.ports["o_branch"].center,
    }
    c.info["pair_t_connection"] = {
        "pair_feed_coupler": pair.ports["o_feedline_coupling"].center,
        "t_branch": t.ports["o_branch"].center,
        "declared_t_branch_length_um": float(t_branch_length),
        "delta_um": (
            float(pair.ports["o_feedline_coupling"].x - t.ports["o_branch"].x),
            float(pair.ports["o_feedline_coupling"].y - t.ports["o_branch"].y),
        ),
    }
    c.info["pair_bbox_um"] = {
        "width": float(pair.bbox().width()),
        "height": float(pair.bbox().height()),
    }
    c.info["pair_geometry_receipt"] = pair_comp.info.get("path_geometry")
    if abs(left_launcher.ports["o_pad"].y) > 1e-6 or abs(right_launcher.ports["o_pad"].y) > 1e-6:
        raise ValueError("Launcher pad ports must be y=0.")
    if abs(t.ports["o1"].y - t.ports["o2"].y) > 1e-6:
        raise ValueError("T-junction is not level on feedline axis.")
    if abs((t.ports["o1"].x + t.ports["o2"].x) / 2) > 1e-6 or abs(t.ports["o1"].y) > 1e-6:
        raise ValueError("T-junction center should be exactly (0,0).")
    if abs(t.ports["o_branch"].x) > 1e-6:
        raise ValueError("T-junction branch x should be 0.")

    return c


__all__ = ["spring2025_intrinsic_individual_purcell_filter_test_chip"]
