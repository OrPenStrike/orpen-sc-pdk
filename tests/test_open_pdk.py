from pathlib import Path

import orpen_sc_pdk
from orpen_sc_pdk.cells import (
    cpw_straight,
    dicing_edge,
    global_purcell_filter_demo_chip,
    interdigital_capacitor,
    launcher,
    martinis2022_differential_ribbon_capacitor,
    resonator,
    sim_flip_chip_distance,
    sim_flip_chip_distance_keepout_global_routing_demo,
    sim_flip_chip_distance_keepout_routing_demo,
    taper,
)
from orpen_sc_pdk.tech import LAYER, LAYER_STACK


def test_pdk_activates_and_builds_public_cells() -> None:
    pdk = orpen_sc_pdk.activate()

    assert pdk.name == "orpen_sc_pdk"
    assert "D0_TOP_M1" in LAYER_STACK.layers
    assert (LAYER.D1_D2_INDIUM_BUMP.layer, LAYER.D1_D2_INDIUM_BUMP.datatype) == (41, 0)
    assert cpw_straight().ports
    assert global_purcell_filter_demo_chip().ports
    assert launcher().ports
    assert interdigital_capacitor().ports
    assert martinis2022_differential_ribbon_capacitor().ports
    assert resonator().ports
    assert sim_flip_chip_distance().ports
    assert sim_flip_chip_distance_keepout_routing_demo(
        show_route_centerline=False,
        show_route_keepout=False,
    )
    assert sim_flip_chip_distance_keepout_global_routing_demo(
        show_route_centerline=False,
        show_route_keepout=False,
    )
    assert taper().ports
    assert dicing_edge()


def test_public_pdk_has_no_private_imports_or_gds() -> None:
    package_root = Path(__file__).resolve().parents[1] / "orpen_sc_pdk"
    source_text = "\n".join(path.read_text() for path in package_root.rglob("*.py"))

    assert "ncuas_designs" not in source_text
    assert "as_single" not in source_text
    assert "as_reference" not in source_text
    assert "AS Reference" not in source_text
    assert "AS Circular" not in source_text
    assert not list(package_root.rglob("*.gds"))
