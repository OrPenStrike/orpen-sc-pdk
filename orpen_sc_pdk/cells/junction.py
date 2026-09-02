"""Manhattan-style Josephson junction with a straight simulation port sheet."""

import math
from typing import Literal

import gdsfactory as gf

from orpen_sc_pdk.helpers.layout.geometry import Point, rotate_point
from orpen_sc_pdk.ports import add_junction_lumped_port
from orpen_sc_pdk.tech import LAYER, Layer


def _path_orientation(start: Point, end: Point) -> float:
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 360


@gf.cell(tags=["junctions", "elements"])
def manhattan_style_junction(
    width: float = 0.09,
    length: float = 5.0,
    cross_center: Point = (4.0, 4.0),
    open_side: Literal["left-bottom", "right-bottom", "right-top", "left-top"] = "left-bottom",
    sim_anchor_start: Point | None = None,
    sim_anchor_end: Point | None = None,
    draw_layer: Layer = LAYER.D0_TOP_JJ_DRAW,
    sim_port_layer: Layer = LAYER.D0_TOP_SIM_BOUNDARY,
    with_fabrication_geometry: bool = True,
) -> gf.Component:
    """Return a Manhattan junction plus a straight FEM lumped-port surrogate.

    The fabrication geometry is the Manhattan overlap cross on ``draw_layer``.
    The simulation geometry is the straight sheet on ``sim_port_layer`` with a
    junction lumped port. Palace should interpret that sheet as a branch between
    two circuit nodes, not as the microscopic tunnel-current path.

    The junction lumped port is the named sheet locator for SCGSim. Do not add a
    separate mesh marker for this junction: the fabrication cross and the
    simulation sheet are intentionally different semantic geometries.
    """

    if width <= 0:
        raise ValueError(f"width must be positive, got {width!r}.")
    if length <= 0:
        raise ValueError(f"length must be positive, got {length!r}.")

    open_side_rotation = {
        "left-bottom": 0.0,
        "right-bottom": 90.0,
        "right-top": 180.0,
        "left-top": 270.0,
    }[open_side]

    if sim_anchor_start is None:
        sim_anchor_start = (-float(cross_center[0]), 0.0)
    if sim_anchor_end is None:
        sim_anchor_end = (0.0, -float(cross_center[1]))
    sim_anchor_start = rotate_point(sim_anchor_start, open_side_rotation)
    sim_anchor_end = rotate_point(sim_anchor_end, open_side_rotation)

    c = gf.Component()

    if with_fabrication_geometry:
        horizontal = c << gf.components.rectangle(size=(length, width), layer=draw_layer)
        horizontal.move((-cross_center[0], -width / 2))
        horizontal.rotate(open_side_rotation)

        vertical = c << gf.components.rectangle(size=(width, length), layer=draw_layer)
        vertical.move((-width / 2, -cross_center[1]))
        vertical.rotate(open_side_rotation)

    sim_sheet = gf.Path([sim_anchor_start, sim_anchor_end]).extrude(
        width=width
        * 3,  # Otherwise the sheet is too narrow to reliably mesh with typical meshing settings.
        layer=sim_port_layer,
    )
    sim_sheet.flatten()
    _ = c << sim_sheet
    if sim_anchor_start == sim_anchor_end:
        raise ValueError("Simulation junction anchors must not coincide.")
    center = (
        (sim_anchor_start[0] + sim_anchor_end[0]) / 2,
        (sim_anchor_start[1] + sim_anchor_end[1]) / 2,
    )
    orientation = _path_orientation(sim_anchor_start, sim_anchor_end)

    add_junction_lumped_port(
        c,
        name="o_junction_lumped",
        center=center,
        width=width,
        orientation=orientation,
        layer=sim_port_layer,
    )

    c.add_port(
        name="o_arm1",
        center=sim_anchor_start,
        width=width,
        orientation=(orientation + 180) % 360,
        layer=draw_layer,
    )
    c.add_port(
        name="o_arm2",
        center=sim_anchor_end,
        width=width,
        orientation=orientation,
        layer=draw_layer,
    )

    return c


if __name__ == "__main__":
    from orpen_sc_pdk.pdk import PDK

    PDK.activate()

    c = manhattan_style_junction()
    c.show()
