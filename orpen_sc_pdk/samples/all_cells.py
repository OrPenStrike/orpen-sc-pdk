"""Sample that places every public PDK cell."""

from __future__ import annotations

import gdsfactory as gf

from orpen_sc_pdk import PDK, activate

PUBLIC_SAMPLE_CELLS = (
    "as_interdigital_capacitor",
    "as_launcher",
    "cpw_straight",
    "interdigital_capacitor",
    "quarter_wave_resonator",
)


@gf.cell
def all_public_cells(spacing: float = 80.0) -> gf.Component:
    """Return a component containing one instance of each public PDK cell."""

    activate()
    component = gf.Component()
    x = 0.0
    for name in PUBLIC_SAMPLE_CELLS:
        reference = component << PDK.cells[name]()
        reference.movex(x - reference.xmin)
        x = reference.xmax + spacing
    return component
