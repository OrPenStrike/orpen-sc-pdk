"""Public capacitor primitives."""

from __future__ import annotations

from itertools import chain
from math import ceil, isfinite

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec, Layer

from orpen_sc_pdk.helpers.layout import add_etch_for_component
from orpen_sc_pdk.tech import LAYER


@gf.cell(tags=["elements"])
def interdigital_capacitor(
    fingers: int = 20,
    finger_length: float = 100.0,
    finger_gap: float = 3.3,
    finger_width: float = 3.3,
    taper_length: float = 150.0,
    terminal_extension_length_um: float = 100.0,
    capacitor_ground_gap: float = 85.0,
    cpw_xs: CrossSectionSpec = "coplanar_waveguide",
    half: bool = False,
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Return an IDC with symmetric CPW terminal extensions and derived etch.

    The public ports are the outer CPW cut planes: standalone terminals remain
    open for Q3D extraction, while assembled CPW routes connect at those planes.
    """

    xs = gf.get_cross_section(cpw_xs)
    cpw_width = xs["cpw_draw"].width
    cpw_gap = xs["cpw_etch_pos"].width

    component = gf.Component()
    core_capacitor_temp = gf.Component()
    if fingers < 1:
        raise ValueError("fingers must be at least 1.")
    if not isfinite(terminal_extension_length_um) or terminal_extension_length_um <= 0:
        raise ValueError(
            "terminal_extension_length_um must be finite and positive, "
            f"got {terminal_extension_length_um!r}."
        )

    width = finger_length + finger_gap if not half else finger_length
    height = fingers * finger_width + (fingers - 1) * finger_gap

    points_1 = [
        (0, 0),
        (0, height),
        (finger_length, height),
        (finger_length, height - finger_width),
        (0, height - finger_width),
        *chain.from_iterable(
            (
                (0, height - (2 * index) * (finger_width + finger_gap)),
                (
                    finger_length,
                    height - (2 * index) * (finger_width + finger_gap),
                ),
                (
                    finger_length,
                    height - (2 * index) * (finger_width + finger_gap) - finger_width,
                ),
                (
                    0,
                    height - (2 * index) * (finger_width + finger_gap) - finger_width,
                ),
            )
            for index in range(ceil(fingers / 2))
        ),
        (0, 0),
    ]
    core_capacitor_temp.add_polygon(points=points_1, layer=draw_layer)

    if not half:
        points_2 = [
            (width, 0),
            (width, height),
            *chain.from_iterable(
                (
                    (width, height - (2 * index + 1) * (finger_width + finger_gap)),
                    (
                        width - finger_length,
                        height - (2 * index + 1) * (finger_width + finger_gap),
                    ),
                    (
                        width - finger_length,
                        height - (2 * index + 1) * (finger_width + finger_gap) - finger_width,
                    ),
                    (
                        width,
                        height - (2 * index + 1) * (finger_width + finger_gap) - finger_width,
                    ),
                )
                for index in range(fingers // 2)
            ),
        ]
        core_capacitor_temp.add_polygon(points=points_2, layer=draw_layer)

    core_capacitor = component << core_capacitor_temp
    core_capacitor.move((-core_capacitor_temp.x, -core_capacitor_temp.y))

    in_taper = component << gf.components.taper(
        length=taper_length,
        width1=cpw_width,
        width2=height,
        layer=draw_layer,
    )
    in_taper.movex(-(taper_length + core_capacitor_temp.x))
    out_taper = component << gf.components.taper(
        length=taper_length,
        width1=height,
        width2=cpw_width,
        layer=draw_layer,
    )
    out_taper.movex(core_capacitor_temp.x)

    terminal_extension = gf.path.extrude(
        gf.path.straight(terminal_extension_length_um),
        width=cpw_width,
        layer=draw_layer,
    )
    in_extension = component << terminal_extension
    in_extension.dmovex(in_taper.xmin - in_extension.xmax)
    out_extension = component << terminal_extension
    out_extension.dmovex(out_taper.xmax - out_extension.xmin)

    component.add_port(
        name="o_capacitor_in",
        center=(component.xmin, 0),
        width=cpw_width,
        orientation=180,
        layer=draw_layer,
    )
    component.add_port(
        name="o_capacitor_out",
        center=(component.xmax, 0),
        width=cpw_width,
        orientation=0,
        layer=draw_layer,
    )

    mask_points = [
        (component.xmin, cpw_width / 2 + cpw_gap),
        (in_taper.xmin, cpw_width / 2 + cpw_gap),
        (core_capacitor.xmin, height / 2 + capacitor_ground_gap),
        (core_capacitor.xmax, height / 2 + capacitor_ground_gap),
        (out_taper.xmax, cpw_width / 2 + cpw_gap),
        (component.xmax, cpw_width / 2 + cpw_gap),
        (component.xmax, -cpw_width / 2 - cpw_gap),
        (out_taper.xmax, -cpw_width / 2 - cpw_gap),
        (core_capacitor.xmax, -height / 2 - capacitor_ground_gap),
        (core_capacitor.xmin, -height / 2 - capacitor_ground_gap),
        (in_taper.xmin, -cpw_width / 2 - cpw_gap),
        (component.xmin, -cpw_width / 2 - cpw_gap),
    ]
    component.add_polygon(points=mask_points, layer=ground_mask_layer)

    result = add_etch_for_component(
        component=component,
        draw_layer=draw_layer,
        mask_layer=ground_mask_layer,
        etch_layer=etch_layer,
    )
    result.info["cpw_gap_um"] = float(cpw_gap)
    return result
