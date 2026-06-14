"""Small helper functions for PDK tests and docs examples."""

from __future__ import annotations

from gdsfactory.technology import LayerViews
from gdsfactory.typings import Layer


def layer_views_to_tuples(layer_views: LayerViews) -> dict[str, Layer]:
    """Return layer-view names mapped to concrete ``(layer, datatype)`` tuples."""

    def _flatten(items: dict) -> dict[str, Layer]:
        layers: dict[str, Layer] = {}
        for name, layer_view in items.items():
            if layer_view.group_members:
                layers.update(_flatten(layer_view.group_members))
            elif layer_view.layer is not None:
                layers[name] = layer_view.layer
        return layers

    return _flatten(layer_views.layer_views)
