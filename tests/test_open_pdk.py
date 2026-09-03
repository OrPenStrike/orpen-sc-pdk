"""Smoke tests for activating the public OrPen PDK and building public cells."""

from pathlib import Path

import gdsfactory as gf

from orpen_sc_pdk.cells import (
    dicing_edge,
    interdigital_capacitor,
    launcher,
    martinis2022_differential_ribbon_capacitor,
    resonator,
    taper,
)
from orpen_sc_pdk.pdk import PDK
from orpen_sc_pdk.tech import LAYER, LAYER_STACK


def test_pdk_activates_and_builds_public_cells() -> None:
    PDK.activate()

    assert gf.get_active_pdk().name == "orpen_sc_pdk"
    assert "D0_TOP_M1" in LAYER_STACK.layers
    assert (LAYER.D1_D2_INDIUM_BUMP.layer, LAYER.D1_D2_INDIUM_BUMP.datatype) == (41, 0)
    assert launcher().ports
    assert interdigital_capacitor().ports
    assert martinis2022_differential_ribbon_capacitor().ports
    assert resonator().ports
    assert taper().ports
    assert dicing_edge()


def test_flip_chip_layer_metadata() -> None:
    assert {name for name in LAYER_STACK.layers if "UNDER_BUMP" in name} == {"D0_D1_UNDER_BUMP"}
    assert LAYER_STACK.layers["D0_TOP_M1"].info == {
        "simulation_role": "conductor",
        "layer_type": "conductor",
        "part_role": "face_metal",
        "host_void_semantic_id": "D0_TO_D1_GAP",
        "geometry": {
            "geometry_source": "die_face_minus_ground_mask",
            "plane_bounds_ref": "D0_SUBSTRATE",
        },
    }
    assert LAYER_STACK.layers["D1_BOTTOM_M1"].info == {
        "simulation_role": "conductor",
        "layer_type": "conductor",
        "part_role": "face_metal",
        "host_void_semantic_id": "D0_TO_D1_GAP",
        "geometry": {
            "geometry_source": "die_face_minus_ground_mask",
            "plane_bounds_ref": "D1_SUBSTRATE",
        },
    }
    bump_info = LAYER_STACK.layers["D0_D1_INDIUM_BUMP"].info
    assert set(bump_info) == {
        "simulation_role",
        "layer_type",
        "part_role",
        "host_void_semantic_id",
        "geometry",
        "ground_bump_fill_spec",
    }
    assert {key: bump_info[key] for key in ("simulation_role", "layer_type", "part_role")} == {
        "simulation_role": "conductor",
        "layer_type": "via",
        "part_role": "bump_body",
    }
    assert bump_info["host_void_semantic_id"] == "D0_TO_D1_GAP"
    assert bump_info["geometry"] == {
        "geometry_source": "gds_polygon",
        "split_polygons_as_entities": True,
    }
    fill_spec = bump_info["ground_bump_fill_spec"]
    assert fill_spec["schema_version"] == 1
    assert fill_spec["body_layer"] == tuple(LAYER.D0_D1_INDIUM_BUMP)
    assert fill_spec["contact_layer"] == tuple(LAYER.D0_D1_UNDER_BUMP)
    assert LAYER_STACK.layers["D0_D1_UNDER_BUMP"].info == {
        "exclude_from_simulation": True,
    }


def test_public_pdk_has_no_private_imports_or_gds() -> None:
    package_root = Path(__file__).resolve().parents[1] / "orpen_sc_pdk"
    source_text = "\n".join(path.read_text() for path in package_root.rglob("*.py"))

    assert "ncuas_designs" not in source_text
    assert "as_single" not in source_text
    assert "as_reference" not in source_text
    assert "AS Reference" not in source_text
    assert "AS Circular" not in source_text
    assert not list(package_root.rglob("*.gds"))
