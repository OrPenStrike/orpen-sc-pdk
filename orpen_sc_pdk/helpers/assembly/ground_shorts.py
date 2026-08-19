"""Place flip-chip indium bumps on an isolated simulation coupon."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

import gdsfactory as gf

from orpen_sc_pdk.cells.indium import indium_bump
from orpen_sc_pdk.helpers.layout import indium_bump_centers_around_polygon
from orpen_sc_pdk.tech import INDIUM_BUMP_SIZE_UM, LAYER, UNDER_BUMP_SIZE_UM, Layer

_BUMP_SEMANTIC_ID = "D0_D1_INDIUM_BUMP"
_PLACEMENT_MODES = ("corner_anchors", "full_field")
PlacementMode = Literal["corner_anchors", "full_field"]


@dataclass(frozen=True)
class GroundShortCoupon:
    """Device cell wrapped with authored coupon indium bumps.

    Bumps are GDS geometry. ``plot()`` shows them because they already exist on
    the component; SCGSim only compiles those polygons.
    """

    component: gf.Component
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
        wrapped = _wrap_with_bumps(
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
            "corner-anchored indium bumps violate bump-to-bump padding; "
            f"centers={centers!r}."
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
) -> gf.Component:
    wrapped = gf.Component()
    device_ref = wrapped << component
    wrapped.add_ports(device_ref.ports)
    bump_cell = indium_bump(
        indium_bump_size=bump_size_um,
        under_bump_size=under_bump_size_um,
        indium_bump_layer=indium_bump_layer,
    )
    for center in centers:
        bump_ref = wrapped << bump_cell
        bump_ref.move(center)
    wrapped.info["component_semantics"] = _authored_bump_semantics(
        component,
        indium_bump_layer=indium_bump_layer,
    )
    return wrapped


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


def _authored_bump_semantics(component: gf.Component, *, indium_bump_layer: Layer) -> dict:
    raw = component.info.get("component_semantics")
    if not isinstance(raw, dict):
        raise ValueError("component must provide info['component_semantics'].")
    semantics = deepcopy(dict(raw))
    regions = semantics.get("conductor_regions")
    if isinstance(regions, str | bytes) or not isinstance(regions, Sequence):
        raise TypeError("component conductor_regions must be a sequence.")
    regions = [deepcopy(record) for record in regions]

    found = False
    for record in regions:
        if not isinstance(record, dict) or record.get("semantic_id") != _BUMP_SEMANTIC_ID:
            continue
        metadata = record.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            raise TypeError("indium bump metadata must be a mapping.")
        metadata["source_kind"] = "authored"
        found = True
    if not found:
        regions.append(
            {
                "semantic_id": _BUMP_SEMANTIC_ID,
                "level": "D0_D1_INDIUM_BUMP",
                "gds_layer": tuple(int(value) for value in indium_bump_layer),
                "net_id": "Ground",
                "metadata": {
                    "semantic_group_id": _BUMP_SEMANTIC_ID,
                    "source_kind": "authored",
                    "source_semantic_id": _BUMP_SEMANTIC_ID,
                    "equipotential_id": "Ground",
                    "owner_semantic_ids": (
                        "D0_TOP_GROUND_PLANE",
                        "D1_BOTTOM_GROUND_PLANE",
                    ),
                },
            }
        )
    semantics["conductor_regions"] = regions
    return semantics


__all__ = ["GroundShortCoupon", "place_flip_chip_ground_short_bumps"]
