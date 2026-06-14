"""Simulation port metadata helpers authored during layout construction."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

import gdsfactory as gf
from gdsfactory.typings import LayerSpec

Point = tuple[float, float]

SIM_PORT_TYPES = (
    "sim_cpw",
    "sim_lumped",
    "sim_wave",
    "sim_mesh",
    "sim_junction_lumped",
    "sim_q2d_conductor",
)


class AxisDirection(StrEnum):
    """Axis-aligned solver direction metadata."""

    POS_X = "+X"
    NEG_X = "-X"
    POS_Y = "+Y"
    NEG_Y = "-Y"
    POS_Z = "+Z"
    NEG_Z = "-Z"


def register_sim_port_types() -> None:
    """Register public simulation port types with GDSFactory."""

    for port_type in SIM_PORT_TYPES:
        if port_type not in gf.CONF.port_types:
            gf.CONF.port_types += (port_type,)


def add_driven_lumped_port(
    component: gf.Component,
    *,
    name: str,
    center: Point,
    layer: LayerSpec,
    direction: AxisDirection | str | list[float] | None = None,
    width: float = 1.0,
    orientation: float = 0.0,
    coordinate_system: Literal["Cartesian", "Cylindrical"] | None = None,
    mesh_profile: str = "solver_boundary_sheet",
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
    """Add a driven lumped-port locator with public solver metadata keys."""

    port = component.add_port(
        name=name,
        center=center,
        width=width,
        orientation=orientation,
        layer=layer,
        port_type="sim_lumped",
    )
    port.info.update(
        _metadata_without_none(
            {
                "mesh_profile": mesh_profile,
                "mesh_feature_width_um": feature_width_um,
                "mesh_elements_per_width": elements_per_width,
                "mesh_curve_min_elements": curve_min_elements,
                "mesh_curve_element_count_enabled": curve_element_count_enabled,
                "palace_lumped_port_direction": _direction_value(direction),
                "palace_lumped_port_coordinate_system": coordinate_system,
                "palace_lumped_port_l": L,
                "palace_lumped_port_c": C,
                "palace_lumped_port_r": R,
                "palace_lumped_port_ls": Ls,
                "palace_lumped_port_cs": Cs,
                "palace_lumped_port_rs": Rs,
                "palace_lumped_port_excitation": excitation,
                "palace_lumped_port_active": active,
            }
        )
    )
    return port


def _direction_value(
    direction: AxisDirection | str | list[float] | None,
) -> str | list[float] | None:
    if isinstance(direction, AxisDirection):
        return direction.value
    return direction


def _metadata_without_none(values: dict[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}


__all__ = [
    "SIM_PORT_TYPES",
    "AxisDirection",
    "add_driven_lumped_port",
    "register_sim_port_types",
]
