"""Chip launcher placement helpers."""

from dataclasses import dataclass

import gdsfactory as gf
from gdsfactory.typings import ComponentSpec, CrossSectionSpec

from orpen_sc_pdk.tech import LAYER, Layer


@dataclass
class LauncherRefs:
    """Group launcher references by chip edge after placement.

    Use when chip assembly code needs to route from a specific edge without
    rediscovering launcher references from geometry.

    Example:
        refs = place_launchers(c)
        left_launcher = refs.left[0]
    """

    left: list[gf.ComponentReference]
    right: list[gf.ComponentReference]
    top: list[gf.ComponentReference]
    bottom: list[gf.ComponentReference]


def _add_launcher_ref(
    c: gf.Component,
    position: tuple[float, float],
    rotation: float,
    launcher: ComponentSpec,
    launcher_end_gap_width: float,
    cpw_xs: CrossSectionSpec,
    draw_layer: Layer,
    etch_layer: Layer,
    ground_mask_layer: Layer,
) -> gf.ComponentReference:
    ref = c << gf.get_component(
        component=launcher,
        end_gap_width=launcher_end_gap_width,
        cpw_xs=cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    if rotation:
        ref.rotate(rotation)
    ref.move(position)
    return ref


def place_launchers(
    c: gf.Component,
    chip_width: float = 9900,
    chip_height: float = 9900,
    launcher_end_gap_width: float = 85.0,
    launcher_edge_gap: float = 50.0,
    launcher: ComponentSpec = "launcher",
    cpw_xs: CrossSectionSpec = "coplanar_waveguide",
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> LauncherRefs:
    """Place the standard four-per-edge launcher assembly on a chip component.

    Use when a chip cell wants the project launcher convention as placement
    behavior, separate from routing algorithms and launcher primitive geometry.

    Example:
        launchers = place_launchers(c, chip_width=9900, chip_height=9900)
    """

    left_right_margin = chip_width / 2 - launcher_edge_gap - launcher_end_gap_width
    top_bottom_margin = chip_height / 2 - launcher_edge_gap - launcher_end_gap_width

    left_y = [2550, 850, -850, -2550]
    top_x = [-2550, -850, 850, 2550]
    bottom_x = [2550, 850, -850, -2550]

    left = [
        _add_launcher_ref(
            c=c,
            position=(-left_right_margin, y),
            rotation=0,
            launcher=launcher,
            launcher_end_gap_width=launcher_end_gap_width,
            cpw_xs=cpw_xs,
            draw_layer=draw_layer,
            etch_layer=etch_layer,
            ground_mask_layer=ground_mask_layer,
        )
        for y in left_y
    ]
    top = [
        _add_launcher_ref(
            c=c,
            position=(x, top_bottom_margin),
            rotation=-90,
            launcher=launcher,
            launcher_end_gap_width=launcher_end_gap_width,
            cpw_xs=cpw_xs,
            draw_layer=draw_layer,
            etch_layer=etch_layer,
            ground_mask_layer=ground_mask_layer,
        )
        for x in top_x
    ]
    right = [
        _add_launcher_ref(
            c=c,
            position=(left_right_margin, y),
            rotation=180,
            launcher=launcher,
            launcher_end_gap_width=launcher_end_gap_width,
            cpw_xs=cpw_xs,
            draw_layer=draw_layer,
            etch_layer=etch_layer,
            ground_mask_layer=ground_mask_layer,
        )
        for y in left_y
    ]
    bottom = [
        _add_launcher_ref(
            c=c,
            position=(x, -top_bottom_margin),
            rotation=90,
            launcher=launcher,
            launcher_end_gap_width=launcher_end_gap_width,
            cpw_xs=cpw_xs,
            draw_layer=draw_layer,
            etch_layer=etch_layer,
            ground_mask_layer=ground_mask_layer,
        )
        for x in bottom_x
    ]

    return LauncherRefs(left=left, top=top, right=right, bottom=bottom)


__all__ = ["LauncherRefs", "place_launchers"]
