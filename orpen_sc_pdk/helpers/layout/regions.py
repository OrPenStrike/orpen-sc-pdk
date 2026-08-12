"""KLayout region helpers for routing and keepout construction."""

from collections.abc import Sequence

import gdsfactory as gf
from gdsfactory.typings import LayerSpec


def get_keepout_region(
    component: gf.Component,
    layers: Sequence[LayerSpec],
    clearance_um: float = 5.0,
) -> gf.Region:
    """Build a merged expanded keepout Region from selected component layers."""

    if clearance_um < 0:
        raise ValueError(f"clearance_um must be non-negative, got {clearance_um!r}.")

    temp = component.copy()
    temp.flatten()

    keepout_region = gf.Region()
    for layer in layers:
        keepout_region += temp.get_region(layer, merge=True)

    keepout_region = keepout_region.merged()
    if clearance_um > 0:
        keepout_region = keepout_region.size(d=round(clearance_um / component.kcl.dbu))

    return keepout_region.merged()


def _layer_spec_to_tuple(layer: LayerSpec) -> tuple[int, int]:
    if isinstance(layer, tuple):
        layer_index, datatype = layer
        return int(layer_index), int(datatype)
    if hasattr(layer, "layer") and hasattr(layer, "datatype"):
        return int(layer.layer), int(layer.datatype)

    resolved_layer = gf.get_layer(layer)
    if isinstance(resolved_layer, tuple):
        layer_index, datatype = resolved_layer
        return int(layer_index), int(datatype)
    if hasattr(resolved_layer, "layer") and hasattr(resolved_layer, "datatype"):
        return int(resolved_layer.layer), int(resolved_layer.datatype)
    if isinstance(resolved_layer, int):
        layer_info = gf.kcl.get_info(resolved_layer)
        return int(layer_info.layer), int(layer_info.datatype)

    raise TypeError(f"Cannot resolve layer spec {layer!r} to a layer tuple.")


def merge_component_layers(
    components: Sequence[gf.Component],
    *,
    layers: Sequence[LayerSpec],
    include_unmerged_layers: bool = True,
) -> gf.Component:
    """Merge selected layers across components while preserving other polygons."""

    merged = gf.Component()
    if not components:
        return merged

    merged_layer_tuples = {_layer_spec_to_tuple(layer) for layer in layers}
    processed_layer_tuples: set[tuple[int, int]] = set()

    for layer in layers:
        layer_tuple = _layer_spec_to_tuple(layer)
        if layer_tuple in processed_layer_tuples:
            continue
        processed_layer_tuples.add(layer_tuple)

        region = components[0].get_region(layer_tuple, merge=True)
        for component in components[1:]:
            region += component.get_region(layer_tuple, merge=True)
        if not region.is_empty():
            region.merge()
            merged.add_polygon(points=region, layer=layer_tuple)

    if include_unmerged_layers:
        for component in components:
            for layer_tuple, polygons in component.get_polygons(merge=False, by="tuple").items():
                if layer_tuple in merged_layer_tuples:
                    continue
                for polygon in polygons:
                    merged.add_polygon(points=polygon, layer=layer_tuple)

    merged.flatten()
    return merged


def get_keepout_region_from_targets(
    targets: Sequence[gf.Component | gf.ComponentReference],
    layers: Sequence[LayerSpec],
    clearance_um: float = 5.0,
) -> gf.Region:
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


__all__ = [
    "get_keepout_region",
    "get_keepout_region_from_targets",
    "merge_component_layers",
]
