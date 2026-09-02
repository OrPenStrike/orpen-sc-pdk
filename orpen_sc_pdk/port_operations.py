"""Reusable GDSFactory locators for layout-authored simulation ports."""

import gdsfactory as gf
from gdsfactory.typings import LayerSpec

from orpen_sc_pdk.helpers.layout.geometry import Point
from orpen_sc_pdk.port_metadata import SimulationPortType


def _add_locator_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    port_type: SimulationPortType,
    width: float = 1.0,
    orientation: float = 0.0,
) -> gf.Port:
    return component.add_port(
        name=name,
        center=center,
        width=width,
        orientation=orientation,
        layer=layer,
        port_type=port_type,
    )


def add_mesh_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    width: float = 1.0,
    orientation: float = 0.0,
) -> gf.Port:
    """Add a named mesh-region locator on component-owned geometry.

    The locator identifies a layout feature. Mesh numeric policy stays with the
    SCGSim notebook or runtime.

    Example:
        add_mesh_port(
            c,
            name="o_mesh_island",
            center=(0.0, 0.0),
            layer=draw_layer,
        )
    """

    return _add_locator_port(
        component,
        name=name,
        center=center,
        layer=layer,
        port_type=SimulationPortType.MESH,
        width=width,
        orientation=orientation,
    )


def add_junction_lumped_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    width: float = 1.0,
    orientation: float = 0.0,
) -> gf.Port:
    """Add a Josephson-junction sheet locator on layout geometry.

    Use when a cell authors a junction sheet that SCGSim should compile from
    this named port. Linearized inductance and mesh sizes stay notebook-local.

    Example:
        add_junction_lumped_port(
            c,
            name="o_junction_lumped",
            center=(0.0, 0.0),
            layer=jj_sim_layer,
        )
    """

    return _add_locator_port(
        component,
        name=name,
        center=center,
        layer=layer,
        port_type=SimulationPortType.JUNCTION_LUMPED,
        width=width,
        orientation=orientation,
    )


def add_driven_lumped_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    width: float = 1.0,
    orientation: float = 0.0,
) -> gf.Port:
    """Add a driven lumped-sheet locator on layout geometry.

    Use when a launcher or chip authors an excitation sheet. Palace R, excitation,
    and activity flags stay with the SCGSim problem, not with this locator.

    Example:
        add_driven_lumped_port(
            c,
            name="o_lumped_readout_in",
            center=launcher.ports["o_lumped"].center,
            layer=sim_boundary_layer,
        )
    """

    return _add_locator_port(
        component,
        name=name,
        center=center,
        layer=layer,
        port_type=SimulationPortType.PALACE_LUMPED,
        width=width,
        orientation=orientation,
    )


__all__ = [
    "add_driven_lumped_port",
    "add_junction_lumped_port",
    "add_mesh_port",
]
