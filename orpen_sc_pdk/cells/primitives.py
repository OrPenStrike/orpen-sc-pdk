"""Project-scoped GF primitive adapters used by private layout routing."""

from __future__ import annotations

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec, LayerSpec


@gf.cell
def bend_circular(
    radius: float | None = None,
    angle: float = 90.0,
    npoints: int | None = None,
    angular_step: float | None = None,
    layer: LayerSpec | None = None,
    width: float | None = None,
    cross_section: CrossSectionSpec = "as_cpw_6_7_6",
    allow_min_radius_violation: bool = False,
) -> gf.Component:
    """Return a GF circular bend with a project CPW default cross-section."""

    return gf.components.bend_circular(
        radius=radius,
        angle=angle,
        npoints=npoints,
        angular_step=angular_step,
        layer=layer,
        width=width,
        cross_section=cross_section,
        allow_min_radius_violation=allow_min_radius_violation,
    )


@gf.cell
def bend_euler(
    radius: float | None = None,
    angle: float = 90.0,
    p: float = 0.5,
    with_arc_floorplan: bool = True,
    npoints: int | None = None,
    angular_step: float | None = None,
    layer: LayerSpec | None = None,
    width: float | None = None,
    cross_section: CrossSectionSpec = "as_cpw_6_7_6",
    allow_min_radius_violation: bool = False,
) -> gf.Component:
    """Return a GF Euler bend with a project CPW default cross-section."""

    return gf.components.bend_euler(
        radius=radius,
        angle=angle,
        p=p,
        with_arc_floorplan=with_arc_floorplan,
        npoints=npoints,
        angular_step=angular_step,
        layer=layer,
        width=width,
        cross_section=cross_section,
        allow_min_radius_violation=allow_min_radius_violation,
    )


@gf.cell
def straight(
    length: float = 10.0,
    npoints: int = 2,
    cross_section: CrossSectionSpec = "as_cpw_6_7_6",
    width: float | None = None,
) -> gf.Component:
    """Return a GF straight with a project CPW default cross-section."""

    return gf.components.straight(
        length=length,
        npoints=npoints,
        cross_section=cross_section,
        width=width,
    )


__all__ = [
    "bend_circular",
    "bend_euler",
    "straight",
]
