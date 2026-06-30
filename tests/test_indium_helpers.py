"""Tests for indium layout helper functions."""

import pytest

from orpen_sc_pdk.helpers.layout import indium_bump_centers_around_polygon

POLYGON = ((-50.0, -25.0), (50.0, -25.0), (50.0, 25.0), (-50.0, 25.0))


def test_indium_bump_corner_anchors_surround_polygon_bounds() -> None:
    centers = indium_bump_centers_around_polygon(
        POLYGON,
        bump_size_um=20.0,
        bump_gap_um=40.0,
        margin_um=20.0,
        clearance_um=10.0,
        placement_mode="corner_anchors",
    )

    assert centers == ((-90.0, -60.0), (-90.0, 60.0), (90.0, -60.0), (90.0, 60.0))


def test_indium_bump_full_field_keeps_clearance() -> None:
    centers = indium_bump_centers_around_polygon(
        POLYGON,
        bump_size_um=20.0,
        bump_gap_um=40.0,
        margin_um=20.0,
        clearance_um=10.0,
    )

    assert len(centers) > 4
    assert all(not (-70.0 <= x <= 70.0 and -45.0 <= y <= 45.0) for x, y in centers)


def test_indium_bump_helper_rejects_bad_geometry() -> None:
    with pytest.raises(ValueError, match="at least three points"):
        indium_bump_centers_around_polygon(((0.0, 0.0), (1.0, 1.0)))
