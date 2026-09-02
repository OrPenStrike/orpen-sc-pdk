"""Public Martinis benchmark cells ported with AI assistance using GDSFactory+ MCP."""

import gdsfactory as gf

from orpen_sc_pdk.ports import add_mesh_port
from orpen_sc_pdk.tech import LAYER, Layer


def _check_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}.")


@gf.cell(tags=["capacitors", "benchmarks"])
def martinis2022_differential_ribbon_capacitor(
    a_um: float = 50.0,
    b_um: float = 100.0,
    ell_r_um: float = 1391.0,
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
) -> gf.Component:
    """Return the Martinis 2022 Fig. 7 differential ribbon capacitor layout."""

    _check_positive("a_um", a_um)
    if b_um <= a_um:
        raise ValueError(f"b_um must be greater than a_um, got b_um={b_um!r}, a_um={a_um!r}.")
    _check_positive("ell_r_um", ell_r_um)

    c = gf.Component()

    half_length_um = ell_r_um / 2
    ribbon_width_um = b_um - a_um

    positive_electrode = [
        (-b_um, -half_length_um),
        (-a_um, -half_length_um),
        (-a_um, half_length_um),
        (-b_um, half_length_um),
    ]
    negative_electrode = [
        (a_um, -half_length_um),
        (b_um, -half_length_um),
        (b_um, half_length_um),
        (a_um, half_length_um),
    ]

    c.add_polygon(points=positive_electrode, layer=draw_layer)
    c.add_polygon(points=negative_electrode, layer=draw_layer)

    pos_center = (-(a_um + b_um) / 2, 0)
    neg_center = ((a_um + b_um) / 2, 0)

    add_mesh_port(
        c,
        name="o_mesh_positive_electrode",
        center=pos_center,
        layer=draw_layer,
        width=ribbon_width_um,
        orientation=180,
    )
    add_mesh_port(
        c,
        name="o_mesh_negative_electrode",
        center=neg_center,
        layer=draw_layer,
        width=ribbon_width_um,
        orientation=0,
    )

    return c


__all__ = ["martinis2022_differential_ribbon_capacitor"]
