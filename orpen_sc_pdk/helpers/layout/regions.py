"""KLayout region helpers for routing and keepout construction."""

from collections.abc import Sequence

import gdsfactory as gf
from gdsfactory.typings import LayerSpec
from klayout import db as kdb


def get_keepout_region(
    component: gf.Component,
    layers: Sequence[LayerSpec],
    clearance_um: float = 5.0,
) -> kdb.Region:
    """Build a merged expanded keepout Region from selected component layers."""

    if clearance_um < 0:
        raise ValueError(f"clearance_um must be non-negative, got {clearance_um!r}.")

    temp = component.copy()
    temp.flatten()

    keepout_region = kdb.Region()
    for layer in layers:
        keepout_region += temp.get_region(layer, merge=True)

    keepout_region = keepout_region.merged()
    if clearance_um > 0:
        keepout_region = keepout_region.size(d=round(clearance_um * 1e3))

    return keepout_region.merged()


def get_keepout_region_from_targets(
    targets: Sequence[gf.Component | gf.ComponentReference],
    layers: Sequence[LayerSpec],
    clearance_um: float = 5.0,
) -> kdb.Region:
    """Build one expanded keepout Region from many components or references."""

    temp = gf.Component()
    for target in targets:
        if isinstance(target, gf.Component):
            _ = temp << target
        else:
            ref = temp.add_ref(target.cell)
            ref.dtrans = target.dtrans

    return get_keepout_region(
        component=temp,
        layers=layers,
        clearance_um=clearance_um,
    )


__all__ = ["get_keepout_region", "get_keepout_region_from_targets"]
