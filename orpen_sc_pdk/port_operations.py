"""Reusable GDSFactory port operations for layout-authored metadata."""

from typing import Literal

import gdsfactory as gf
from gdsfactory.typings import LayerSpec

from orpen_sc_pdk.helpers.layout.geometry import Point
from orpen_sc_pdk.port_metadata import (
    AxisDirection,
    CoordinateSystem,
    MeshPortInfo,
    MeshProfile,
    PalaceLumpedPort,
    Q2dConductorPortInfo,
    Q2dConductorType,
    SimulationPortType,
)


def add_mesh_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    mesh_profile: MeshProfile | str,
    feature_width_um: float | None = None,
    elements_per_width: float | None = None,
    curve_min_elements: float | None = None,
    curve_element_count_enabled: bool | None = None,
    width: float = 1.0,
    orientation: float = 0.0,
) -> gf.Port:
    """Add a named mesh marker port to component-owned layout geometry.

    Use when a cell already knows which polygon should receive a reusable mesh
    profile; scene builders consume this metadata later.

    Example:
        add_mesh_port(
            c,
            name="o_mesh_island",
            center=(0.0, 0.0),
            layer=draw_layer,
            mesh_profile=MeshProfile.METAL_ISLAND,
        )
    """

    port = component.add_port(
        name=name,
        center=center,
        width=width,
        orientation=orientation,
        layer=layer,
        port_type=SimulationPortType.MESH,
    )
    port.info.update(
        MeshPortInfo(
            mesh_profile=mesh_profile,
            feature_width_um=feature_width_um,
            elements_per_width=elements_per_width,
            curve_min_elements=curve_min_elements,
            curve_element_count_enabled=curve_element_count_enabled,
        ).to_info()
    )
    return port


def add_q2d_conductor_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    conductor_type: Q2dConductorType | str,
    assignment_name: str | None = None,
    width: float = 1.0,
    orientation: float = 0.0,
) -> gf.Port:
    """Add a Q2D conductor marker port to component-owned layout geometry.

    Use when a component already knows the AEDT Q2D conductor role for an
    imported conductor. The marker name identifies the marker itself;
    ``assignment_name`` is the Q2D conductor name and grouping key.

    Example:
        add_q2d_conductor_port(
            c,
            name="q2d_center_signal",
            center=(0.0, 0.0),
            layer=draw_layer,
            conductor_type=Q2dConductorType.SIGNAL_LINE,
            assignment_name="Signal",
        )
    """

    port = component.add_port(
        name=name,
        center=center,
        width=width,
        orientation=orientation,
        layer=layer,
        port_type=SimulationPortType.Q2D_CONDUCTOR,
    )
    port.info.update(
        Q2dConductorPortInfo(
            conductor_type=conductor_type,
            assignment_name=assignment_name,
        ).to_info()
    )
    return port


def add_junction_lumped_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    direction: AxisDirection | str | list[float] | None = None,
    width: float = 1.0,
    orientation: float = 0.0,
    coordinate_system: CoordinateSystem | Literal["Cartesian", "Cylindrical"] | None = None,
    mesh_profile: MeshProfile | str = MeshProfile.SOLVER_BOUNDARY_SHEET,
    feature_width_um: float | None = None,
    elements_per_width: float | None = None,
    curve_min_elements: float | None = None,
    curve_element_count_enabled: bool | None = None,
    L: float | None = None,
    C: float | None = None,
    R: float | None = None,
    Ls: float | None = None,
    Cs: float | None = None,
    Rs: float | None = None,
    active: bool | None = None,
) -> gf.Port:
    """Add a non-excited junction lumped port locator to layout geometry.

    Use when a cell authors a Josephson-junction sheet that Palace should treat
    as a lumped element but not as a driven excitation source.

    Example:
        add_junction_lumped_port(
            c,
            name="o_junction_lumped",
            center=(0.0, 0.0),
            layer=jj_sim_layer,
            direction=AxisDirection.POS_X,
        )
    """

    port = component.add_port(
        name=name,
        center=center,
        width=width,
        orientation=orientation,
        layer=layer,
        port_type=SimulationPortType.JUNCTION_LUMPED,
    )
    port.info.update(
        MeshPortInfo(
            mesh_profile=mesh_profile,
            feature_width_um=feature_width_um,
            elements_per_width=elements_per_width,
            curve_min_elements=curve_min_elements,
            curve_element_count_enabled=curve_element_count_enabled,
        ).to_info()
    )
    port.info.update(
        PalaceLumpedPort(
            direction=direction,
            coordinate_system=coordinate_system,
            L=L,
            C=C,
            R=R,
            Ls=Ls,
            Cs=Cs,
            Rs=Rs,
            excitation=False,
            active=active,
        ).to_info()
    )
    return port


def add_driven_lumped_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    direction: AxisDirection | str | list[float] | None = None,
    width: float = 1.0,
    orientation: float = 0.0,
    coordinate_system: CoordinateSystem | Literal["Cartesian", "Cylindrical"] | None = None,
    mesh_profile: MeshProfile | str = MeshProfile.SOLVER_BOUNDARY_SHEET,
    feature_width_um: float | None = None,
    elements_per_width: float | None = None,
    curve_min_elements: float | None = None,
    curve_element_count_enabled: bool | None = None,
    L: float | None = None,
    C: float | None = None,
    R: float | None = None,
    Ls: float | None = None,
    Cs: float | None = None,
    Rs: float | None = None,
    excitation: bool | int = True,
    active: bool | None = True,
) -> gf.Port:
    """Add a driven Palace lumped port locator to layout geometry.

    Use when a chip or launcher cell authors an external excitation/damping
    sheet for driven or transient Palace workflows.

    Example:
        add_driven_lumped_port(
            c,
            name="o_lumped_readout_in",
            center=launcher.ports["o_lumped"].center,
            layer=sim_boundary_layer,
            direction=AxisDirection.POS_X,
        )
    """

    port = component.add_port(
        name=name,
        center=center,
        width=width,
        orientation=orientation,
        layer=layer,
        port_type=SimulationPortType.PALACE_LUMPED,
    )
    port.info.update(
        MeshPortInfo(
            mesh_profile=mesh_profile,
            feature_width_um=feature_width_um,
            elements_per_width=elements_per_width,
            curve_min_elements=curve_min_elements,
            curve_element_count_enabled=curve_element_count_enabled,
        ).to_info()
    )
    port.info.update(
        PalaceLumpedPort(
            direction=direction,
            coordinate_system=coordinate_system,
            L=L,
            C=C,
            R=R,
            Ls=Ls,
            Cs=Cs,
            Rs=Rs,
            excitation=excitation,
            active=active,
        ).to_info()
    )
    return port


__all__ = [
    "add_driven_lumped_port",
    "add_junction_lumped_port",
    "add_mesh_port",
    "add_q2d_conductor_port",
]
