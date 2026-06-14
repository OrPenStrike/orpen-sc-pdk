"""CPW hanger section used as the resonator anchor near a readout line."""

from typing import Literal

import gdsfactory as gf
from gdsfactory.typings import CrossSectionSpec

from orpen_sc_pdk.ports import MeshProfile, add_mesh_port
from orpen_sc_pdk.tech import LAYER, Layer


@gf.cell(tags=["AS", "elements"])
def resonator_hanger(
    coupling_length: float = 200.0,
    straight_length: float = 160.0,
    # XS
    cpw_xs: CrossSectionSpec = "as_cpw_6_10_6",
    cpw_radius: float = 100.0,
    bend_npoints: int | None = 16,
    bend_segment2_angle: Literal[-90, 90] = -90,
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Return the hanger head of a readout resonator.

    The coupling straight is centered at the origin so parent qubit/chip cells
    can align the hanger to a physical qubit pocket without re-solving the CPW
    path. ``o_hanger_center`` is therefore an anchor port, not a route terminus.
    """

    if bend_segment2_angle not in (-90, 90):
        raise ValueError(
            f"bend_segment2_angle must be either -90 or 90, got {bend_segment2_angle!r}."
        )
    if bend_npoints is not None and bend_npoints <= 0:
        raise ValueError(f"bend_npoints must be positive or None, got {bend_npoints!r}.")

    c = gf.Component()

    cpw_xs_instance = gf.get_cross_section(
        cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=cpw_radius,
    )

    coupling_component = gf.components.straight(
        length=coupling_length,
        cross_section=cpw_xs_instance,
    )
    bend_kwargs = {
        "radius": cpw_radius,
        "cross_section": cpw_xs_instance,
    }
    if bend_npoints is not None:
        bend_kwargs["npoints"] = bend_npoints
    bend_segment1_component = gf.components.bend_euler(
        angle=90,
        **bend_kwargs,
    )
    straight_component = gf.components.straight(
        length=straight_length,
        cross_section=cpw_xs_instance,
    )
    bend_segment2_component = gf.components.bend_euler(
        angle=bend_segment2_angle,
        **bend_kwargs,
    )

    coupling_segment = c << coupling_component
    bend_segment1 = c << bend_segment1_component
    straight_segment = c << straight_component
    bend_segment2 = c << bend_segment2_component

    # Anchor convention: the coupling section center is the parent placement
    # point; downstream CPW geometry grows from its end port.
    coupling_segment.move(origin=coupling_segment.center, destination=(0, 0))
    bend_segment1.connect("o1", coupling_segment.ports["o2"])
    straight_segment.connect("o1", bend_segment1.ports["o2"])
    bend_segment2.connect("o1", straight_segment.ports["o2"])
    cpw_draw_width = float(cpw_xs_instance.width)

    c.add_port(
        name="o_hanger_start",
        port=coupling_segment.ports["o1"],
        layer=draw_layer,
    )
    c.add_port(
        name="o_hanger_center",
        center=coupling_segment.center,
        width=coupling_segment.ports["o1"].width,
        orientation=0,
        layer=draw_layer,
    )
    c.add_port(
        name="o_hanger_end",
        port=bend_segment2.ports["o2"],
        layer=draw_layer,
    )
    c.add_port(
        name="o_hanger_readout_coupling_start",
        port=coupling_segment.ports["o1"],
        layer=draw_layer,
    )
    c.add_port(
        name="o_hanger_readout_coupling_end",
        center=(bend_segment1.ports["o2"].x, coupling_segment.ports["o1"].y),
        width=coupling_segment.ports["o2"].width,
        orientation=0,
        layer=draw_layer,
    )
    add_mesh_port(
        c,
        name="o_mesh_hanger_coupling",
        center=coupling_segment.center,
        width=cpw_draw_width,
        feature_width_um=cpw_draw_width,
        orientation=0,
        layer=draw_layer,
        mesh_profile=MeshProfile.CRITICAL_METAL_TRACE,
    )
    add_mesh_port(
        c,
        name="o_mesh_hanger_straight",
        center=straight_segment.center,
        width=cpw_draw_width,
        feature_width_um=cpw_draw_width,
        orientation=straight_segment.ports["o1"].orientation,
        layer=draw_layer,
        mesh_profile=MeshProfile.CRITICAL_METAL_TRACE,
    )

    c.info["length"] = (
        coupling_length
        + straight_length
        + float(bend_segment1_component.info["length"])
        + float(bend_segment2_component.info["length"])
    )

    return c
