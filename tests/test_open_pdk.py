from pathlib import Path

import orpen_sc_pdk
from orpen_sc_pdk.cells import (
    cpw_straight,
    dicing_edge,
    interdigital_capacitor,
    launcher,
    resonator,
    taper,
)
from orpen_sc_pdk.tech import LAYER, LAYER_STACK


def test_pdk_activates_and_builds_public_cells() -> None:
    pdk = orpen_sc_pdk.activate()

    assert pdk.name == "orpen_sc_pdk"
    assert "D0_TOP_M1" in LAYER_STACK.layers
    assert (LAYER.D1_D2_INDIUM_BUMP.layer, LAYER.D1_D2_INDIUM_BUMP.datatype) == (41, 0)
    assert cpw_straight().ports
    assert launcher().ports
    assert interdigital_capacitor().ports
    assert resonator().ports
    assert taper().ports
    assert dicing_edge()


def test_public_pdk_has_no_private_imports_or_gds() -> None:
    package_root = Path(__file__).resolve().parents[1] / "orpen_sc_pdk"
    source_text = "\n".join(path.read_text() for path in package_root.rglob("*.py"))

    assert "ncuas_designs" not in source_text
    assert "AS Reference" not in source_text
    assert "AS Circular" not in source_text
    assert not list(package_root.rglob("*.gds"))
