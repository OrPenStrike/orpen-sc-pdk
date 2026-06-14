"""Composite readout resonator cells with explicit length ownership."""

from typing import Literal

import gdsfactory as gf
from gdsfactory.typings import ComponentSpec, CrossSectionSpec

from orpen_sc_pdk.cells.resonator_hanger import resonator_hanger
from orpen_sc_pdk.cells.resonator_meander import resonator_meander
from orpen_sc_pdk.helpers.layout.etch import as_add_etch_for_component
from orpen_sc_pdk.ports import MeshProfile, add_mesh_port
from orpen_sc_pdk.tech import (
    AS_CPW_ETCH_POS,
    AS_CPW_GROUND_MASK,
    LAYER,
    Layer,
)


def _component_length(component: gf.Component, name: str) -> float:
    """Read child centerline length metadata required by parent length budgeting."""

    length = getattr(component.info, "length", None)
    if length is None:
        raise ValueError(f"{name} must provide a length in its component info.")
    return float(length)


@gf.cell(tags=["AS", "resonators"])
def resonator(
    length: float = 4000.0,
    meanders: int = 6,
    coupling_length: float = 200.0,
    hanger_straight_length: float = 160.0,
    hanger_bend_segment2_angle: Literal[-90, 90] = 90,
    tail_straight_length: float = 0.0,
    tail_bend_angle: Literal[-90, 0, 90] = 0,
    tail_after_bend_length: float = 0.0,
    qubit_resonator_segment_reference_point: tuple[float, float] | None = None,
    qubit_resonator_segment_length: float = 0.0,
    qubit_resonator_segment_gap: float = 10.0,
    route_to_qubit_resonator_segment: bool = False,
    # XS
    cpw_xs: CrossSectionSpec = "as_cpw_6_10_6",
    cpw_radius: float = 100.0,
    hanger_radius: float | None = None,
    meander_radius: float | None = None,
    tail_radius: float | None = None,
    bend_npoints: int | None = 16,
    meander_bend_spec: ComponentSpec = "bend_euler",
    tail_bend_spec: ComponentSpec = "bend_euler",
    meander_straight_length_weights: tuple[float, ...] | None = None,
    meander_start_with_bend: bool = False,
    meander_end_with_bend: bool = False,
    open_end: bool = True,
    # Layers
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Create a hanger + meander + optional tail CPW resonator.

    ``length`` is the target centerline length of the full resonator, including
    the hanger, the meander, the optional tail segment, the optional route to a
    qubit resonator segment, and that qubit segment itself. The meander absorbs
    the remaining length after the fixed and routed lengths are accounted for.
    This keeps the parent-facing resonator contract stable while allowing the
    local hanger/tail/qubit-pocket geometry to change independently.
    """

    if length <= 0:
        raise ValueError(f"length must be positive, got {length!r}.")
    if tail_straight_length < 0:
        raise ValueError(
            f"tail_straight_length must be non-negative, got {tail_straight_length!r}."
        )
    if tail_after_bend_length < 0:
        raise ValueError(
            f"tail_after_bend_length must be non-negative, got {tail_after_bend_length!r}."
        )
    if tail_bend_angle not in (-90, 0, 90):
        raise ValueError(f"tail_bend_angle must be -90, 0, or 90, got {tail_bend_angle!r}.")
    if qubit_resonator_segment_gap < 0:
        raise ValueError(
            "qubit_resonator_segment_gap must be non-negative, "
            f"got {qubit_resonator_segment_gap!r}."
        )
    if qubit_resonator_segment_length < 0:
        raise ValueError(
            "qubit_resonator_segment_length must be non-negative, "
            f"got {qubit_resonator_segment_length!r}."
        )
    if route_to_qubit_resonator_segment and qubit_resonator_segment_reference_point is None:
        raise ValueError(
            "route_to_qubit_resonator_segment=True requires "
            "qubit_resonator_segment_reference_point."
        )
    if qubit_resonator_segment_reference_point is not None and qubit_resonator_segment_length <= 0:
        raise ValueError(
            "qubit_resonator_segment_length must be positive when "
            "qubit_resonator_segment_reference_point is provided."
        )
    if bend_npoints is not None and bend_npoints <= 0:
        raise ValueError(f"bend_npoints must be positive or None, got {bend_npoints!r}.")

    hanger_radius = cpw_radius if hanger_radius is None else hanger_radius
    meander_radius = cpw_radius if meander_radius is None else meander_radius
    tail_radius = meander_radius if tail_radius is None else tail_radius

    c = gf.Component()

    # Tail geometry owns the final optional bend/straight exit; the meander
    # length is solved after this fixed length is known.
    tail_xs = gf.get_cross_section(
        cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
        radius=tail_radius,
    )
    tail_bend_kwargs = {
        "radius": tail_radius,
        "angle": tail_bend_angle,
        "cross_section": tail_xs,
    }
    if bend_npoints is not None:
        tail_bend_kwargs["npoints"] = bend_npoints
    tail_bend = gf.get_component(tail_bend_spec, **tail_bend_kwargs) if tail_bend_angle else None

    hanger = resonator_hanger(
        coupling_length=coupling_length,
        straight_length=hanger_straight_length,
        cpw_xs=cpw_xs,
        cpw_radius=hanger_radius,
        bend_npoints=bend_npoints,
        bend_segment2_angle=hanger_bend_segment2_angle,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    hanger_length = _component_length(hanger, "hanger")
    tail_length = (
        tail_straight_length
        + tail_after_bend_length
        + (_component_length(tail_bend, "tail_bend") if tail_bend is not None else 0.0)
    )

    qubit_segment = (
        _qubit_resonator_segment(
            length=qubit_resonator_segment_length,
            gap=qubit_resonator_segment_gap,
            cpw_xs=cpw_xs,
            draw_layer=draw_layer,
            etch_layer=etch_layer,
            ground_mask_layer=ground_mask_layer,
        )
        if qubit_resonator_segment_reference_point is not None
        else None
    )
    fixed_length = hanger_length + tail_length
    if qubit_segment is not None:
        fixed_length += qubit_resonator_segment_length

    def _add_body(component: gf.Component, body_meander_length: float) -> gf.Port:
        """Place hanger + meander + tail using a candidate meander length."""

        hanger_ref = component << hanger
        hanger_ref.move(
            origin=hanger_ref.ports["o_hanger_center"].center,
            destination=(0, 0),
        )

        meander = resonator_meander(
            length=body_meander_length,
            meanders=meanders,
            straight_length_weights=meander_straight_length_weights,
            bend_spec=meander_bend_spec,
            cpw_xs=cpw_xs,
            cpw_radius=meander_radius,
            bend_npoints=bend_npoints,
            start_with_bend=meander_start_with_bend,
            end_with_bend=meander_end_with_bend,
            open_start=False,
            open_end=False,
            draw_layer=draw_layer,
            etch_layer=etch_layer,
            ground_mask_layer=ground_mask_layer,
        )
        meander_ref = component << meander
        meander_ref.connect("o1", hanger_ref.ports["o_hanger_end"])

        return _add_tail(
            component=component,
            start_port=meander_ref.ports["o2"],
            tail_straight_length=tail_straight_length,
            tail_bend=tail_bend,
            tail_after_bend_length=tail_after_bend_length,
            tail_xs=tail_xs,
        )

    def _add_qubit_segment_ref(component: gf.Component) -> gf.ComponentReference:
        """Place the qubit-pocket segment at its parent-supplied anchor."""

        if qubit_segment is None or qubit_resonator_segment_reference_point is None:
            raise ValueError("qubit_segment is required but not initialized.")
        segment_ref = component << qubit_segment
        segment_ref.move(
            origin=segment_ref.ports["o_resonator_segment"].center,
            destination=qubit_resonator_segment_reference_point,
        )
        return segment_ref

    def _route_to_qubit_segment(
        component: gf.Component,
        start_port: gf.Port,
        segment_ref: gf.ComponentReference,
    ):
        """Route the final resonator port into the qubit-pocket segment."""

        routes = gf.routing.route_bundle(
            component=component,
            ports1=[start_port],
            ports2=[segment_ref.ports["o_resonator_segment"]],
            cross_section=tail_xs,
            radius=tail_radius,
            allow_width_mismatch=True,
            allow_layer_mismatch=True,
            raise_on_error=True,
        )
        return routes[0]

    qubit_route_length = 0.0
    if route_to_qubit_resonator_segment:
        # The route length depends on the meander endpoint, and the meander
        # endpoint depends on remaining length. Iterate to keep total length
        # anchored to the public ``length`` contract.
        for _ in range(12):
            candidate_meander_length = length - fixed_length - qubit_route_length
            if candidate_meander_length <= 0:
                raise ValueError(
                    "Resonator length is too short for the requested hanger, tail, "
                    "qubit segment, and route. "
                    f"length={length!r}, fixed_length={fixed_length!r}, "
                    f"route_length={qubit_route_length!r}."
                )

            temp = gf.Component()
            temp_final_port = _add_body(temp, candidate_meander_length)
            temp_segment_ref = _add_qubit_segment_ref(temp)
            route = _route_to_qubit_segment(temp, temp_final_port, temp_segment_ref)
            measured_route_length = float(route.length) / 1e3

            if abs(measured_route_length - qubit_route_length) <= 1e-3:
                qubit_route_length = measured_route_length
                break
            qubit_route_length = measured_route_length

    meander_length = length - fixed_length - qubit_route_length
    if meander_length <= 0:
        raise ValueError(
            "Resonator length is too short for the requested fixed sections. "
            f"length={length!r}, fixed_length={fixed_length!r}, "
            f"route_length={qubit_route_length!r}."
        )

    hanger_ref = c << hanger
    hanger_ref.move(
        origin=hanger_ref.ports["o_hanger_center"].center,
        destination=(0, 0),
    )

    meander = resonator_meander(
        length=meander_length,
        meanders=meanders,
        straight_length_weights=meander_straight_length_weights,
        bend_spec=meander_bend_spec,
        cpw_xs=cpw_xs,
        cpw_radius=meander_radius,
        bend_npoints=bend_npoints,
        start_with_bend=meander_start_with_bend,
        end_with_bend=meander_end_with_bend,
        open_start=False,
        open_end=False,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    meander_ref = c << meander
    meander_ref.connect("o1", hanger_ref.ports["o_hanger_end"])

    final_port = _add_tail(
        component=c,
        start_port=meander_ref.ports["o2"],
        tail_straight_length=tail_straight_length,
        tail_bend=tail_bend,
        tail_after_bend_length=tail_after_bend_length,
        tail_xs=tail_xs,
    )
    cpw_draw_width = float(tail_xs.width)
    add_mesh_port(
        c,
        name="o_mesh_resonator",
        center=hanger_ref.ports["o_hanger_center"].center,
        width=cpw_draw_width,
        feature_width_um=cpw_draw_width,
        orientation=hanger_ref.ports["o_hanger_center"].orientation,
        layer=draw_layer,
        mesh_profile=MeshProfile.CRITICAL_METAL_TRACE,
    )

    c.add_port("o1", port=hanger_ref.ports["o_hanger_start"])
    c.add_port("o_hanger_center", port=hanger_ref.ports["o_hanger_center"])
    c.add_port("o_hanger_end", port=hanger_ref.ports["o_hanger_end"])
    hanger_port_names = {port.name for port in hanger_ref.ports}
    if "o_hanger_readout_coupling_start" in hanger_port_names:
        c.add_port(
            "o_hanger_readout_coupling_start",
            port=hanger_ref.ports["o_hanger_readout_coupling_start"],
        )
        c.add_port(
            "o_hanger_readout_coupling_end",
            port=hanger_ref.ports["o_hanger_readout_coupling_end"],
        )
    else:
        c.add_port(
            "o_hanger_readout_coupling_start",
            port=hanger_ref.ports["o_hanger_start"],
        )
        c.add_port(
            name="o_hanger_readout_coupling_end",
            center=(
                hanger_ref.ports["o_hanger_center"].x + coupling_length / 2 + hanger_radius,
                hanger_ref.ports["o_hanger_center"].y,
            ),
            width=hanger_ref.ports["o_hanger_start"].width,
            orientation=0,
            layer=draw_layer,
        )

    if qubit_segment is not None:
        qubit_segment_ref = _add_qubit_segment_ref(c)
        c.add_port(
            "o_qubit_resonator_segment",
            port=qubit_segment_ref.ports["o_resonator_segment"],
        )
        if route_to_qubit_resonator_segment:
            route = _route_to_qubit_segment(c, final_port, qubit_segment_ref)
            qubit_route_length = float(route.length) / 1e3
            c.add_port("o2", port=qubit_segment_ref.ports["o_resonator_segment"])
        elif open_end:
            _add_open_end(c, final_port, tail_xs)
        else:
            c.add_port("o2", port=final_port)
    elif open_end:
        _add_open_end(c, final_port, tail_xs)
    else:
        c.add_port("o2", port=final_port)

    c.info["length"] = length
    c.info["hanger_length"] = hanger_length
    c.info["meander_length"] = meander_length
    c.info["tail_length"] = tail_length
    c.info["qubit_route_length"] = qubit_route_length
    c.info["qubit_resonator_segment_length"] = qubit_resonator_segment_length

    c.flatten()

    return c


def _add_tail(
    component: gf.Component,
    start_port: gf.Port,
    tail_straight_length: float,
    tail_bend: gf.Component | None,
    tail_after_bend_length: float,
    tail_xs: gf.CrossSection,
) -> gf.Port:
    """Append optional tail pieces and return the route port after the tail."""

    final_port = start_port

    if tail_straight_length > 0:
        tail_straight = gf.components.straight(
            length=tail_straight_length,
            cross_section=tail_xs,
        )
        tail_straight_ref = component << tail_straight
        tail_straight_ref.connect("o1", final_port)
        final_port = tail_straight_ref.ports["o2"]

    if tail_bend is not None:
        tail_bend_ref = component << tail_bend
        tail_bend_ref.connect("o1", final_port)
        final_port = tail_bend_ref.ports["o2"]

    if tail_after_bend_length > 0:
        tail_after_bend = gf.components.straight(
            length=tail_after_bend_length,
            cross_section=tail_xs,
        )
        tail_after_bend_ref = component << tail_after_bend
        tail_after_bend_ref.connect("o1", final_port)
        final_port = tail_after_bend_ref.ports["o2"]

    return final_port


@gf.cell
def _qubit_resonator_segment(
    length: float,
    gap: float = 10.0,
    cpw_xs: CrossSectionSpec = "as_cpw_6_10_6",
    draw_layer: Layer = LAYER.D0_TOP_M1_DRAW,
    etch_layer: Layer = LAYER.D0_TOP_M1_ETCH,
    ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
) -> gf.Component:
    """Rounded-end metal segment used to insert the resonator into a qubit pocket.

    The DRAW segment owns a rounded dead-end metal finger. The GROUND_MASK is
    sized from that finger and ETCH is derived locally so the segment can be
    placed independently of the parent resonator body.
    """

    xs = gf.get_cross_section(
        cpw_xs,
        draw_layer=draw_layer,
        etch_layer=etch_layer,
        ground_mask_layer=ground_mask_layer,
    )
    cpw_width = float(xs.width)
    radius = cpw_width / 2
    if length <= radius:
        raise ValueError(
            "qubit_resonator_segment_length must be larger than half the CPW width "
            f"({radius}), got {length!r}."
        )

    c = gf.Component()
    temp = gf.Component()

    rectangle_segment = temp << gf.components.rectangle(
        size=(cpw_width, length - radius),
        layer=draw_layer,
    )
    rectangle_segment.move((-cpw_width / 2, -(length - radius)))

    semicircle_segment = temp << gf.components.circle(
        radius=radius,
        layer=draw_layer,
    )
    semicircle_segment.move((0, -length + radius))

    _ = c << gf.boolean(
        A=rectangle_segment,
        B=semicircle_segment,
        operation="or",
        layer=draw_layer,
    )

    segment_region = c.get_region(layer=draw_layer)
    c.add_polygon(
        segment_region.size(d=gap * 1e3),
        layer=ground_mask_layer,
    )

    c = as_add_etch_for_component(
        component=c,
        draw_layer=draw_layer,
        mask_layer=ground_mask_layer,
        etch_layer=etch_layer,
    )
    c.add_port(
        name="o_resonator_segment",
        center=(0, 0),
        width=cpw_width,
        orientation=90,
        layer=draw_layer,
    )
    c.info["length"] = length

    return c


def _add_open_end(component: gf.Component, port: gf.Port, cross_section: gf.CrossSection) -> None:
    """Add the open-end ETCH and GROUND_MASK caps for an unterminated CPW."""

    etch_section = cross_section[AS_CPW_ETCH_POS]
    ground_mask_section = cross_section[AS_CPW_GROUND_MASK]

    open_etch_comp = gf.components.rectangle(
        size=(
            etch_section.width,
            2 * etch_section.width + cross_section.width,
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

    open_etch = component << open_etch_comp
    open_ground_mask = component << open_ground_mask_comp
    open_etch.connect(
        "o1",
        port,
        allow_width_mismatch=True,
        allow_layer_mismatch=True,
    )
    open_ground_mask.connect(
        "o1",
        port,
        allow_width_mismatch=True,
        allow_layer_mismatch=True,
    )
    component.add_port("o2", port=open_etch.ports["o2"], port_type="placement")
