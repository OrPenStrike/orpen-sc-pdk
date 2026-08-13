"""Smoke tests for activating the public OrPen PDK and building public cells."""

from pathlib import Path

import gdsfactory as gf

from orpen_sc_pdk.cells import (
    cpw_straight,
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
    assert cpw_straight().ports
    assert launcher().ports
    assert interdigital_capacitor().ports
    assert martinis2022_differential_ribbon_capacitor().ports
    assert resonator().ports
    assert taper().ports
    assert dicing_edge()


def test_flip_chip_layer_metadata() -> None:
    assert {name for name in LAYER_STACK.layers if "UNDER_BUMP" in name} == {"D0_D1_UNDER_BUMP"}
    assert LAYER_STACK.layers["D0_TOP_M1"].info == {
        "layer_type": "conductor",
        "part_role": "face_metal",
        "net_id": "Ground",
        "equipotential_id": "Ground",
    }
    assert LAYER_STACK.layers["D1_BOTTOM_M1"].info == {
        "layer_type": "conductor",
        "part_role": "face_metal",
        "net_id": "Ground",
        "equipotential_id": "Ground",
    }
    assert LAYER_STACK.layers["D0_D1_INDIUM_BUMP"].info == {
        "layer_type": "via",
        "part_role": "bump_body",
        "net_id": "Ground",
        "equipotential_id": "Ground",
    }
    assert LAYER_STACK.layers["D0_D1_UNDER_BUMP"].info == {
        "layer_type": "conductor",
        "part_role": "contact_pad",
        "attached_face_metal_semantic_id": "D0_TOP_M1",
        "net_id": "Ground",
        "equipotential_id": "Ground",
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
