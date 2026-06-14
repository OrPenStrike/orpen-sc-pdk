"""Etch-layer construction helpers for public layout components."""

from __future__ import annotations

import gdsfactory as gf
from gdsfactory.typings import LayerSpec


def add_etch_for_component(
    component: gf.Component,
    draw_layer: LayerSpec | None = None,
    mask_layer: LayerSpec | None = None,
    etch_layer: LayerSpec | None = None,
    clean_etch_layer: bool = True,
) -> gf.Component:
    """Return a copy with ``ETCH = GROUND_MASK - DRAW`` geometry derived."""

    from orpen_sc_pdk.tech import LAYER

    draw_layer = LAYER.D0_TOP_M1_DRAW if draw_layer is None else draw_layer
    mask_layer = LAYER.D0_TOP_GROUND_MASK if mask_layer is None else mask_layer
    etch_layer = LAYER.D0_TOP_M1_ETCH if etch_layer is None else etch_layer

    result = component.copy()
    temp = component.copy()
    temp.flatten()

    draw_region = temp.get_region(draw_layer, merge=True)
    mask_region = temp.get_region(mask_layer, merge=True)
    etch_region = mask_region - draw_region

    if clean_etch_layer:
        result.remove_layers([etch_layer], recursive=False)

    if not etch_region.is_empty():
        result.add_polygon(points=etch_region, layer=etch_layer)

    return result


as_add_etch_for_component = add_etch_for_component

__all__ = ["add_etch_for_component", "as_add_etch_for_component"]
