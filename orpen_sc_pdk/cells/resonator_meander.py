"""Length-controlled CPW meander body for readout resonators."""

import gdsfactory as gf
from gdsfactory.typings import ComponentSpec, CrossSectionSpec

from orpen_sc_pdk.ports import MeshProfile, add_mesh_port
from orpen_sc_pdk.tech import (
    CPW_ETCH_POS,
    CPW_GROUND_MASK,
    LAYER,
    Layer,
)


@gf.cell(tags=["elements"])
def resonator_meander(
    length: float = 4000.0,
    meanders: int = 6,
    straight_length_weights: tuple[float, ...] | None = None,
    bend_spec: ComponentSpec = "bend_euler",
    cpw_xs: CrossSectionSpec = "cpw_6_10_6",
    cpw_radius: float = 100.0,
    bend_npoints: int | None = 16,
    start_with_bend: bool = False,
    end_with_bend: bool = False,
    open_start: bool = False,
    open_end: bool = False,
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Create a meandering coplanar waveguide resonator.

    The CPW cross-section is rebuilt with the provided DRAW / ETCH /
    GROUND_MASK layers, so the same resonator can be placed on either chip face.
    ``length`` is the intended centerline length of this meander body only; the
    parent resonator decides how much length is left after fixed hanger, tail,
    and qubit-pocket geometry.
    """

    if meanders < 0:
        raise ValueError(f"meanders must be non-negative, got {meanders!r}.")
    if bend_npoints is not None and bend_npoints <= 0:
        raise ValueError(f"bend_npoints must be positive or None, got {bend_npoints!r}.")

    c = gf.Component()
    xs = gf.get_cross_section(
        cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=cpw_radius,
    )
    bend_kwargs = {
        "cross_section": xs,
        "radius": cpw_radius,
        "angle": 180,
    }
    if bend_npoints is not None:
        bend_kwargs["npoints"] = bend_npoints
    bend = gf.get_component(bend_spec, **bend_kwargs)

    num_straights = meanders + 1
    if start_with_bend:
        num_straights -= 1
    if end_with_bend:
        num_straights -= 1

    if num_straights < 0:
        raise ValueError(
            "Cannot have fewer than 0 straight sections. Reduce meanders or adjust "
            "start_with_bend/end_with_bend."
        )

    bend_length = float(bend.info["length"])
    total_straight_length = length - meanders * bend_length
    straight_lengths: list[float] = []

    if num_straights > 0:
        if total_straight_length <= 0:
            raise ValueError(
                f"Resonator length {length} is too short for {meanders} meanders "
                f"with bend {bend.name!r}. Increase length, reduce meanders, or "
                "change bend_spec/cpw_radius."
            )

        if straight_length_weights is None:
            straight_lengths = [total_straight_length / num_straights] * num_straights
        else:
            if len(straight_length_weights) != num_straights:
                raise ValueError(
                    "straight_length_weights must have one value per straight section. "
                    f"Expected {num_straights}, got {len(straight_length_weights)}."
                )
            if any(weight <= 0 for weight in straight_length_weights):
                raise ValueError("straight_length_weights values must all be positive.")

            weight_sum = sum(straight_length_weights)
            straight_lengths = [
                total_straight_length * weight / weight_sum for weight in straight_length_weights
            ]

    previous_port = None
    first_ref = None
    last_ref = None
    straight_refs: list[gf.ComponentReference] = []
    straight_index = 0

    def _next_straight_ref() -> gf.ComponentReference:
        nonlocal straight_index

        if straight_index >= len(straight_lengths):
            raise ValueError("No straight length is available for this meander section.")

        straight_comp = gf.components.straight(
            length=straight_lengths[straight_index],
            cross_section=xs,
        )
        straight_index += 1
        straight_ref = c << straight_comp
        straight_refs.append(straight_ref)
        return straight_ref

    for i in range(meanders):
        if i == 0 and start_with_bend:
            bend_ref = c << bend
            if i % 2 == 0:
                bend_ref.mirror()
                bend_ref.rotate(90)
            first_ref = bend_ref
            previous_port = bend_ref.ports["o2"]
        else:
            straight_ref = _next_straight_ref()
            if i == 0:
                first_ref = straight_ref
            else:
                straight_ref.connect("o1", previous_port)

            bend_ref = c << bend
            if i % 2 == 0:
                bend_ref.mirror()
                bend_ref.rotate(90)

            bend_ref.connect("o1", straight_ref.ports["o2"])
            previous_port = bend_ref.ports["o2"]

        last_ref = bend_ref

    if not end_with_bend:
        final_straight_ref = _next_straight_ref()
        if previous_port is not None:
            final_straight_ref.connect("o1", previous_port)
        last_ref = final_straight_ref
        if first_ref is None:
            first_ref = final_straight_ref

    if first_ref is None or last_ref is None:
        raise ValueError("Resonator could not be generated correctly.")

    if open_end or open_start:
        etch_section = xs[CPW_ETCH_POS]
        ground_mask_section = xs[CPW_GROUND_MASK]
        open_etch_comp = gf.components.rectangle(
            size=(
                etch_section.width,
                2 * etch_section.width + xs.width,
            ),
            layer=etch_section.layer,
            centered=True,
            port_type="optical",
            port_orientations=(0, 180),
        )
        open_ground_mask_comp = gf.components.rectangle(
            size=(
                etch_section.width,
                ground_mask_section.width,
            ),
            layer=ground_mask_section.layer,
            centered=True,
            port_type="optical",
            port_orientations=(0, 180),
        )

        def _add_etch_at_port(
            port_name: str,
            ref_port: gf.Port,
            output_port: str,
        ) -> None:
            open_etch = c << open_etch_comp
            open_ground_mask = c << open_ground_mask_comp
            open_etch.connect(
                port_name,
                ref_port,
                allow_width_mismatch=True,
                allow_layer_mismatch=True,
            )
            open_ground_mask.connect(
                port_name,
                ref_port,
                allow_width_mismatch=True,
                allow_layer_mismatch=True,
            )
            c.add_port(
                output_port,
                port=open_etch.ports[output_port],
                port_type="placement",
            )

        if open_end:
            _add_etch_at_port("o1", last_ref.ports["o2"], "o2")
        if open_start:
            _add_etch_at_port("o2", first_ref.ports["o1"], "o1")

    if not open_end:
        c.add_port("o2", port=last_ref.ports["o2"])

    if not open_start:
        c.add_port("o1", port=first_ref.ports["o1"])

    cpw_draw_width = float(xs.width)
    for index, straight_ref in enumerate(straight_refs):
        add_mesh_port(
            c,
            name=f"o_mesh_meander_straight_{index}",
            center=straight_ref.center,
            width=cpw_draw_width,
            feature_width_um=cpw_draw_width,
            orientation=straight_ref.ports["o1"].orientation,
            layer=draw_layer,
            mesh_profile=MeshProfile.CRITICAL_METAL_TRACE,
        )

    c.info["length"] = meanders * bend_length + sum(straight_lengths)
    c.info["bend_length"] = bend_length
    c.info["straight_lengths"] = tuple(straight_lengths)
    c.info["meanders"] = meanders

    return c
