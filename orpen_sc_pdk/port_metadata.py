"""Layout locator port types registered with GDSFactory.

These strings identify sheet and marker ports on the cell. Mesh sizes, Palace
L/C/R, excitation, and AEDT assignment labels belong to SCGSim or the notebook,
not to PDK port metadata.
"""

from enum import StrEnum
from typing import Final


class SimulationPortType(StrEnum):
    """Named layout locator roles that GDSFactory accepts as ``port_type``.

    Use when a cell authors a sheet or marker that SCGSim should later select by
    name and compile from geometry. The ``sim_*`` strings are locator roles, not
    Palace or AEDT config keys.

    Example:
        component.add_port("o_jj", port_type=SimulationPortType.JUNCTION_LUMPED)
    """

    CPW = "sim_cpw"
    MESH = "sim_mesh"
    PALACE_TERMINAL = "sim_terminal"
    PALACE_LUMPED = "sim_lumped"
    JUNCTION_LUMPED = "sim_junction_lumped"
    PALACE_WAVE = "sim_wave"
    PALACE_CURRENT = "sim_current"


SIMULATION_PORT_TYPES: Final[tuple[str, ...]] = tuple(
    str(port_type) for port_type in SimulationPortType
)


def register_sim_port_types() -> None:
    """Register repository simulation port types with GDSFactory.

    Use from PDK setup so GDSFactory accepts ``SimulationPortType`` values such
    as ``sim_mesh`` or ``sim_junction_lumped`` without warning. Component code
    should not call this directly; ``orpen_sc_pdk.pdk.get_pdk()`` already does.

    Example:
        from orpen_sc_pdk.pdk import get_pdk

        pdk = get_pdk()
    """

    import gdsfactory as gf

    for port_type in SIMULATION_PORT_TYPES:
        if port_type not in gf.CONF.port_types:
            if hasattr(gf.CONF.port_types, "append"):
                gf.CONF.port_types.append(port_type)
            else:
                gf.CONF.port_types += (port_type,)


__all__ = [
    "SIMULATION_PORT_TYPES",
    "SimulationPortType",
    "register_sim_port_types",
]
