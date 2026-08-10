"""Notebook-side AEDT geometry preparation helpers."""

from __future__ import annotations

from math import isfinite

import gdsfactory as gf
from gdsfactory.typings import Layer

from orpen_sc_pdk.helpers.layout import add_etch_for_component
from orpen_sc_pdk.tech import LAYER


def prepare_interdigital_capacitor_q3d_geometry(
    component: gf.Component,
    *,
    terminal_open_clearance_um: float,
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Return a flattened IDC copy with Q3D-open terminal clearances.

    The signal and public cut-plane ports are unchanged. Only the ground-mask
    opening extends beyond each signal end before ETCH is derived again.
    """

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
        mask_width_um = float(port.width) + 2 * cpw_gap_um
        clearance = prepared << gf.components.rectangle(
            size=(terminal_open_clearance_um, mask_width_um),
            centered=True,
            layer=ground_mask_layer,
        )
        clearance.dmove(
            (
                float(port.x) + direction * terminal_open_clearance_um / 2,
                float(port.y),
            )
        )

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


__all__ = ["prepare_interdigital_capacitor_q3d_geometry"]
