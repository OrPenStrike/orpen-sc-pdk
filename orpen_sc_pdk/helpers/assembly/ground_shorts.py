"""Place flip-chip indium bumps on an isolated simulation coupon."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

import gdsfactory as gf

from orpen_sc_pdk.cells.layout.indium import indium_bump
from orpen_sc_pdk.helpers.layout import indium_bump_centers_around_polygon
from orpen_sc_pdk.tech import INDIUM_BUMP_SIZE_UM, LAYER, UNDER_BUMP_SIZE_UM, Layer

_PLACEMENT_MODES = ("corner_anchors", "full_field")
PlacementMode = Literal["corner_anchors", "full_field"]


@dataclass(frozen=True)
class GroundShortCoupon:
    """Device cell wrapped with authored coupon indium bumps.

    Bumps are GDS geometry. ``plot()`` shows them because they already exist on
    the component; SCGSim only compiles those polygons.
    """

    component: gf.Component
    named_instances: Mapping[str, gf.ComponentReference]
    requested_coupon_padding_um: float
    coupon_padding_um: float
    stack_coupon_padding_um: float
    placement_mode: PlacementMode

    def plot(self, *args, **kwargs):
        """Plot the coupon, including authored indium bumps."""

        return self.component.plot(*args, **kwargs)


def place_flip_chip_ground_short_bumps(
    component: gf.Component,
    *,
    coupon_padding_um: float,
    placement_mode: PlacementMode = "corner_anchors",
    clearance_um: float = 30.0,
    bump_size_um: float = INDIUM_BUMP_SIZE_UM,
    under_bump_size_um: float = UNDER_BUMP_SIZE_UM,
    bump_gap_um: float = 40.0,
    q_chip_ground_mask_layer: Layer = LAYER.D1_BOTTOM_GROUND_MASK,
    c_chip_ground_mask_layer: Layer = LAYER.D0_TOP_GROUND_MASK,
    indium_bump_layer: Layer = LAYER.D0_D1_INDIUM_BUMP,
) -> GroundShortCoupon:
    """Author indium bumps on a coupon in GDS, then grow padding until they fit.

    ``corner_anchors`` places keepout-surround and coupon-corner shorts.
    ``full_field`` places the dense PDK surround lattice in the coupon pad.
    Neither mode injects bumps later in SCGSim; ``fill`` there must stay false.
    """

    if coupon_padding_um < 0:
        raise ValueError(f"coupon_padding_um must be non-negative, got {coupon_padding_um!r}.")
    if placement_mode not in _PLACEMENT_MODES:
        raise ValueError(
            f"placement_mode must be 'corner_anchors' or 'full_field', got {placement_mode!r}."
        )
    if clearance_um < 0:
        raise ValueError(f"clearance_um must be non-negative, got {clearance_um!r}.")
    if bump_size_um <= 0:
        raise ValueError(f"bump_size_um must be positive, got {bump_size_um!r}.")
    if under_bump_size_um <= 0:
        raise ValueError(f"under_bump_size_um must be positive, got {under_bump_size_um!r}.")
    if bump_gap_um < 0:
        raise ValueError(f"bump_gap_um must be non-negative, got {bump_gap_um!r}.")

    footprint_um = max(bump_size_um, under_bump_size_um)
    pitch_um = footprint_um + bump_gap_um
    inset_um = footprint_um / 2 + clearance_um
    device_bbox = component.dbbox()
    keepout_polygon = _ground_mask_bbox_polygon(
        component,
        q_chip_ground_mask_layer=q_chip_ground_mask_layer,
        c_chip_ground_mask_layer=c_chip_ground_mask_layer,
    )
    requested = float(coupon_padding_um)
    padding = max(requested, inset_um)
    if placement_mode == "corner_anchors":
        keepout_centers = indium_bump_centers_around_polygon(
            keepout_polygon,
            bump_size_um=footprint_um,
            bump_gap_um=bump_gap_um,
            margin_um=0.0,
            clearance_um=clearance_um,
            placement_mode="corner_anchors",
        )
        padding = max(
            padding,
            _padding_to_separate_coupon_corners(
                device_bbox,
                keepout_centers,
                inset_um=inset_um,
                pitch_um=pitch_um,
            ),
        )
    wrapped = None
    for _ in range(16):
        centers = _bump_centers(
            placement_mode=placement_mode,
            keepout_polygon=keepout_polygon,
            device_bbox=device_bbox,
            coupon_padding_um=padding,
            bump_size_um=footprint_um,
            bump_gap_um=bump_gap_um,
            clearance_um=clearance_um,
            inset_um=inset_um,
        )
        if len(centers) < 2:
            raise ValueError(f"expected multiple indium-bump sites, got {centers!r}.")
        wrapped, named_instances = _wrap_with_bumps(
            component,
            centers=centers,
            bump_size_um=bump_size_um,
            under_bump_size_um=under_bump_size_um,
            indium_bump_layer=indium_bump_layer,
        )
        required = max(requested, inset_um, _padding_to_contain(device_bbox, wrapped.dbbox()))
        if required <= padding + 1e-6:
            stack_padding = _stack_coupon_padding(
                device_bbox=device_bbox,
                wrapped_bbox=wrapped.dbbox(),
                coupon_padding_um=padding,
            )
            return GroundShortCoupon(
                component=wrapped,
                named_instances=MappingProxyType(named_instances),
                requested_coupon_padding_um=requested,
                coupon_padding_um=padding,
                stack_coupon_padding_um=stack_padding,
                placement_mode=placement_mode,
            )
        padding = required

    raise RuntimeError("could not grow coupon padding to contain indium bumps.")


def _bump_centers(
    *,
    placement_mode: PlacementMode,
    keepout_polygon: tuple[tuple[float, float], ...],
    device_bbox,
    coupon_padding_um: float,
    bump_size_um: float,
    bump_gap_um: float,
    clearance_um: float,
    inset_um: float,
) -> tuple[tuple[float, float], ...]:
    keepout_centers = indium_bump_centers_around_polygon(
        keepout_polygon,
        bump_size_um=bump_size_um,
        bump_gap_um=bump_gap_um,
        margin_um=_field_margin(coupon_padding_um, inset_um, placement_mode),
        clearance_um=clearance_um,
        placement_mode=placement_mode,
    )
    if placement_mode == "full_field":
        return keepout_centers
    coupon_centers = _coupon_corner_centers(
        device_bbox,
        coupon_padding_um=coupon_padding_um,
        inset_um=inset_um,
    )
    centers = _unique_points((*keepout_centers, *coupon_centers))
    if _has_bump_gap_violation(centers, pitch_um=bump_size_um + bump_gap_um):
        raise ValueError(
            f"corner-anchored indium bumps violate bump-to-bump padding; centers={centers!r}."
        )
    return centers


def _field_margin(
    coupon_padding_um: float, inset_um: float, placement_mode: PlacementMode
) -> float:
    if placement_mode == "corner_anchors":
        return 0.0
    return max(0.0, coupon_padding_um - inset_um)


def _wrap_with_bumps(
    component: gf.Component,
    *,
    centers: tuple[tuple[float, float], ...],
    bump_size_um: float,
    under_bump_size_um: float,
    indium_bump_layer: Layer,
) -> tuple[gf.Component, dict[str, gf.ComponentReference]]:
    wrapped = gf.Component()
    device_ref = wrapped << component
    device_ref.name = "device"
    wrapped.add_ports(device_ref.ports)
    named_instances = {"device": device_ref}
    bump_names = set(component.info.get("bump_instance_names", ()))
    for bump_ref in component.insts:
        if bump_ref.name in bump_names:
            named_instances[f"device/{bump_ref.name}"] = bump_ref
    if len(named_instances) - 1 != len(bump_names):
        raise ValueError("Xmon bump instance names do not match actual references")
    bump_cell = indium_bump(
        indium_bump_size=bump_size_um,
        under_bump_size=under_bump_size_um,
        indium_bump_layer=indium_bump_layer,
    )
    for index, center in enumerate(centers):
        bump_ref = wrapped << bump_cell
        bump_ref.move(center)
        name = f"short_{index:03d}"
        bump_ref.name = name
        named_instances[name] = bump_ref
    author_common_flip_chip_ground_planes(wrapped)
    return wrapped, named_instances


def author_common_flip_chip_ground_planes(component: gf.Component) -> gf.Component:
    """Assign one D0 and one D1 physical ground plane to a final assembly."""

    if "component_semantics" in component.info:
        raise ValueError("final assembly already has component_semantics")
    d1_mask = tuple(int(value) for value in LAYER.D1_BOTTOM_GROUND_MASK)
    component.info["component_semantics"] = {
        "schema_version": 2,
        "conductor_regions": [
            {
                "semantic_id": "D0_TOP_GROUND_PLANE",
                "level": "D0_TOP_M1",
                "gds_layer": tuple(int(value) for value in LAYER.D0_TOP_GROUND_MASK),
            },
            {
                "semantic_id": "D1_BOTTOM_GROUND_PLANE",
                "level": "D1_BOTTOM_M1",
                "gds_layer": d1_mask,
            },
        ],
    }
    return component


def _ground_mask_bbox_polygon(
    component: gf.Component,
    *,
    q_chip_ground_mask_layer: Layer,
    c_chip_ground_mask_layer: Layer,
) -> tuple[tuple[float, float], ...]:
    keepout = component.get_region(q_chip_ground_mask_layer, merge=True)
    keepout += component.get_region(c_chip_ground_mask_layer, merge=True)
    if keepout.is_empty():
        raise ValueError("flip-chip ground shorts require authored ground-mask keepout.")
    box = keepout.bbox()
    dbu = float(component.kcl.dbu)
    left, bottom, right, top = (box.left * dbu, box.bottom * dbu, box.right * dbu, box.top * dbu)
    if left >= right or bottom >= top:
        raise ValueError("ground-mask keepout bbox must have positive width and height.")
    return (
        (left, bottom),
        (right, bottom),
        (right, top),
        (left, top),
    )


def _coupon_corner_centers(
    bbox,
    *,
    coupon_padding_um: float,
    inset_um: float,
) -> tuple[tuple[float, float], ...]:
    left = float(bbox.left) - coupon_padding_um + inset_um
    bottom = float(bbox.bottom) - coupon_padding_um + inset_um
    right = float(bbox.right) + coupon_padding_um - inset_um
    top = float(bbox.top) + coupon_padding_um - inset_um
    if left >= right or bottom >= top:
        raise ValueError("coupon-corner shorts do not fit inside the intended coupon.")
    return (
        (left, bottom),
        (left, top),
        (right, bottom),
        (right, top),
    )


def _padding_to_separate_coupon_corners(
    device_bbox,
    keepout_centers: tuple[tuple[float, float], ...],
    *,
    inset_um: float,
    pitch_um: float,
) -> float:
    """Return padding that keeps coupon-corner shorts one pitch outside keepout shorts."""

    left = float(device_bbox.left)
    bottom = float(device_bbox.bottom)
    right = float(device_bbox.right)
    top = float(device_bbox.top)
    mid_x = 0.5 * (left + right)
    mid_y = 0.5 * (bottom + top)
    needed = 0.0
    for ix, iy in keepout_centers:
        if ix <= mid_x:
            needed = max(needed, left - ix + inset_um + pitch_um)
        else:
            needed = max(needed, ix + pitch_um + inset_um - right)
        if iy <= mid_y:
            needed = max(needed, bottom - iy + inset_um + pitch_um)
        else:
            needed = max(needed, iy + pitch_um + inset_um - top)
    return needed


def _has_bump_gap_violation(
    centers: tuple[tuple[float, float], ...], *, pitch_um: float, tol_um: float = 1e-6
) -> bool:
    """True when two footprints would sit closer than one PDK pitch on both axes."""

    for index, (x, y) in enumerate(centers):
        for ox, oy in centers[index + 1 :]:
            if abs(x - ox) + tol_um < pitch_um and abs(y - oy) + tol_um < pitch_um:
                return True
    return False


def _unique_points(
    points: tuple[tuple[float, float], ...],
    *,
    tol_um: float = 1e-3,
) -> tuple[tuple[float, float], ...]:
    kept: list[tuple[float, float]] = []
    for x, y in points:
        if any(abs(x - px) < tol_um and abs(y - py) < tol_um for px, py in kept):
            continue
        kept.append((float(x), float(y)))
    return tuple(kept)


def _padding_to_contain(device_bbox, wrapped_bbox) -> float:
    return max(
        float(device_bbox.left) - float(wrapped_bbox.left),
        float(wrapped_bbox.right) - float(device_bbox.right),
        float(device_bbox.bottom) - float(wrapped_bbox.bottom),
        float(wrapped_bbox.top) - float(device_bbox.top),
        0.0,
    )


def _stack_coupon_padding(*, device_bbox, wrapped_bbox, coupon_padding_um: float) -> float:
    intended_left = float(device_bbox.left) - coupon_padding_um
    intended_bottom = float(device_bbox.bottom) - coupon_padding_um
    intended_right = float(device_bbox.right) + coupon_padding_um
    intended_top = float(device_bbox.top) + coupon_padding_um
    pads = (
        float(wrapped_bbox.left) - intended_left,
        float(wrapped_bbox.bottom) - intended_bottom,
        intended_right - float(wrapped_bbox.right),
        intended_top - float(wrapped_bbox.top),
    )
    if min(pads) < -1e-6:
        raise ValueError(
            "ground-short bumps extend beyond the intended coupon; "
            f"required residual pads={pads!r}."
        )
    return max(0.0, *pads)


__all__ = [
    "GroundShortCoupon",
    "author_common_flip_chip_ground_planes",
    "place_flip_chip_ground_short_bumps",
]
