"""Tests for flip-chip coupon indium-bump placement."""

import pytest

from orpen_sc_pdk.cells.qubit import kosen2024_flip_chip_xmon_qubit
from orpen_sc_pdk.helpers.assembly import place_flip_chip_ground_short_bumps
from orpen_sc_pdk.pdk import PDK
from orpen_sc_pdk.tech import LAYER


def _indium_polygon_count(component) -> int:
    region = component.get_region(LAYER.D0_D1_INDIUM_BUMP, merge=True)
    return int(region.count())


def _under_bump_centers(component) -> tuple[tuple[float, float], ...]:
    region = component.get_region(LAYER.D0_D1_UNDER_BUMP, merge=True)
    dbu = float(component.kcl.dbu)
    centers = []
    for polygon in region.each():
        box = polygon.bbox()
        centers.append(((box.left + box.right) * dbu / 2, (box.bottom + box.top) * dbu / 2))
    return tuple(centers)


def _assert_pitch_separation(centers: tuple[tuple[float, float], ...], pitch_um: float) -> None:
    for index, (x, y) in enumerate(centers):
        for ox, oy in centers[index + 1 :]:
            assert abs(x - ox) >= pitch_um - 1e-6 or abs(y - oy) >= pitch_um - 1e-6


def test_kosen_zero_argument_cell_keeps_the_preview_bump_ring() -> None:
    PDK.activate()
    component = kosen2024_flip_chip_xmon_qubit()

    assert component.info["bump_count"] == 16
    assert _indium_polygon_count(component) == 16


def test_kosen_bump_ring_count_zero_omits_cell_bumps() -> None:
    PDK.activate()
    component = kosen2024_flip_chip_xmon_qubit(bump_ring_count_per_side=0)

    assert component.info["bump_count"] == 0
    assert _indium_polygon_count(component) == 0


def test_kosen_bump_ring_count_rejects_odd_nonzero_values() -> None:
    with pytest.raises(ValueError, match="0 or an even integer"):
        kosen2024_flip_chip_xmon_qubit(bump_ring_count_per_side=1)


def test_place_flip_chip_ground_short_bumps_authors_kosen_corner_sites() -> None:
    PDK.activate()
    device = kosen2024_flip_chip_xmon_qubit(bump_ring_count_per_side=0)
    device_bbox = device.dbbox()
    coupon = place_flip_chip_ground_short_bumps(
        device,
        coupon_padding_um=150.0,
        clearance_um=30.0,
        placement_mode="corner_anchors",
    )

    wrapped = coupon.component
    wrapped_bbox = wrapped.dbbox()
    bump_count = _indium_polygon_count(wrapped)
    semantics = wrapped.info["component_semantics"]
    bump_records = [
        record
        for record in semantics["conductor_regions"]
        if record.get("semantic_id") == "D0_D1_INDIUM_BUMP"
    ]

    assert bump_count == 8
    assert coupon.placement_mode == "corner_anchors"
    _assert_pitch_separation(_under_bump_centers(wrapped), pitch_um=80.0)
    assert all(record["metadata"]["source_kind"] == "authored" for record in bump_records)
    assert coupon.stack_coupon_padding_um >= 0.0
    assert coupon.coupon_padding_um >= coupon.requested_coupon_padding_um
    assert abs(float(device_bbox.left)) < 1e4  # GDSFactory physical um, not DBU
    assert float(wrapped_bbox.left) < float(device_bbox.left)
    assert float(wrapped_bbox.right) > float(device_bbox.right)
    assert callable(coupon.plot)
    assert "o_junction_lumped" in wrapped.ports


def test_place_flip_chip_ground_short_bumps_grows_undersized_coupon() -> None:
    PDK.activate()
    device = kosen2024_flip_chip_xmon_qubit(bump_ring_count_per_side=0)
    coupon = place_flip_chip_ground_short_bumps(
        device,
        coupon_padding_um=20.0,
        clearance_um=30.0,
        placement_mode="corner_anchors",
    )

    assert coupon.requested_coupon_padding_um == pytest.approx(20.0)
    assert coupon.coupon_padding_um > coupon.requested_coupon_padding_um
    assert _indium_polygon_count(coupon.component) == 8
    _assert_pitch_separation(_under_bump_centers(coupon.component), pitch_um=80.0)
    assert coupon.stack_coupon_padding_um >= 0.0


def test_place_flip_chip_ground_short_bumps_full_field_authors_gds_lattice() -> None:
    PDK.activate()
    device = kosen2024_flip_chip_xmon_qubit(bump_ring_count_per_side=0)
    coupon = place_flip_chip_ground_short_bumps(
        device,
        coupon_padding_um=75.0,
        clearance_um=30.0,
        placement_mode="full_field",
    )

    bump_count = _indium_polygon_count(coupon.component)
    assert coupon.placement_mode == "full_field"
    assert bump_count > 8
    _assert_pitch_separation(_under_bump_centers(coupon.component), pitch_um=80.0)
    assert coupon.coupon_padding_um >= coupon.requested_coupon_padding_um
    assert coupon.stack_coupon_padding_um >= 0.0
