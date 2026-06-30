"""Architecture checks for the public OrPen PDK import and registry surface."""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec

import gdsfactory as gf
from gdsfactory.technology import LayerViews

from orpen_sc_pdk.config import PATH
from orpen_sc_pdk.helper import layer_views_to_tuples
from orpen_sc_pdk.pdk import PDK
from orpen_sc_pdk.tech import LAYER, LAYER_VIEWS

cells = import_module("orpen_sc_pdk.cells")
package = import_module("orpen_sc_pdk")
model_exports = import_module("orpen_sc_pdk.models").__all__


def test_orpen_style_public_import_surface() -> None:
    assert package.PATH == PATH
    assert cells.cpw_straight
    assert cells.interdigital_capacitor
    assert cells.launcher
    assert cells.martinis2022_differential_ribbon_capacitor
    assert cells.resonator
    assert cells.taper
    assert (LAYER.D0_TOP_M1_DRAW.layer, LAYER.D0_TOP_M1_DRAW.datatype) == (1, 0)
    assert (LAYER.D1_D2_UNDER_BUMP.layer, LAYER.D1_D2_UNDER_BUMP.datatype) == (41, 1)
    assert model_exports == []
    assert {"helper", "logger", "models"}.isdisjoint(package.__all__)


def test_pdk_registry_contains_public_cells() -> None:
    expected = {
        "indium_bump",
        "indium_ground",
        "resonator",
        "resonator_hanger",
        "resonator_meander",
        "taper",
        "bend_circular",
        "bend_euler",
        "cpw_straight",
        "dicing_edge",
        "interdigital_capacitor",
        "launcher",
        "manhattan_style_junction",
        "martinis2022_differential_ribbon_capacitor",
        "straight",
    }

    assert set(PDK.cells) == expected


def test_public_chip_demos_live_in_one_module_per_chip() -> None:
    chips = import_module("orpen_sc_pdk.cells.chips")
    chip_modules = {
        "global_purcell_filter_demo_chip": (
            "orpen_sc_pdk.cells.chips.global_purcell_filter_demo_chip"
        ),
        "resonator_with_indium_bumps": ("orpen_sc_pdk.cells.chips.resonator_with_indium_bumps"),
        "sim_flip_chip_distance": "orpen_sc_pdk.cells.chips.sim_flip_chip_distance",
        "sim_flip_chip_distance_keepout_global_routing_demo": (
            "orpen_sc_pdk.cells.chips.sim_flip_chip_distance_keepout_global_routing_demo"
        ),
        "sim_flip_chip_distance_keepout_routing_demo": (
            "orpen_sc_pdk.cells.chips.sim_flip_chip_distance_keepout_routing_demo"
        ),
        "small_airbridge_chip": "orpen_sc_pdk.cells.chips.small_airbridge_chip",
    }

    assert set(chips.__all__) == set(chip_modules)
    for name, module_name in chip_modules.items():
        module = import_module(module_name)
        assert getattr(chips, name) is getattr(module, name)

    assert find_spec("orpen_sc_pdk.cells.flip_chip") is None
    assert find_spec("orpen_sc_pdk.cells.purcell") is None
    assert find_spec("orpen_sc_pdk.cells.chips.resonators_with_flip_chip") is None


def test_pdk_registry_removed_misleading_cell_names() -> None:
    removed = {
        "all" + "_public_cells",
        "as" + "_interdigital_capacitor",
        "as" + "_indium_bump",
        "as" + "_indium_ground",
        "as" + "_launcher",
        "as" + "_resonator",
        "as" + "_resonator_hanger",
        "as" + "_resonator_meander",
        "as" + "_taper",
        "quarter" + "_wave_resonator",
    }

    assert removed.isdisjoint(PDK.cells)
    assert not any(name.startswith("as_") for name in PDK.cells)
    assert not hasattr(cells, "as" + "_interdigital_capacitor")
    assert not hasattr(cells, "as" + "_indium_bump")
    assert not hasattr(cells, "as" + "_indium_ground")
    assert not hasattr(cells, "as" + "_launcher")
    assert not hasattr(cells, "as" + "_resonator")
    assert not hasattr(cells, "as" + "_resonator_hanger")
    assert not hasattr(cells, "as" + "_resonator_meander")
    assert not hasattr(cells, "as" + "_taper")
    assert not hasattr(cells, "quarter" + "_wave_resonator")


def test_pdk_registry_does_not_publish_generic_gf_cells() -> None:
    generic_cells = {
        "add_frame",
        "align_wafer",
        "awg",
        "rounded_rectangle",
    }

    assert PDK.base_pdks == []
    assert generic_cells.isdisjoint(PDK.cells)


def test_fixture_cells_stay_in_deep_owner_modules_until_notebook_facing() -> None:
    from orpen_sc_pdk.cells import xs_chip

    fixture_cells = {
        "single_trace_flip_chip_xs_chip",
        "single_trace_xs_chip",
        "two_trace_flip_chip_xs_chip",
        "two_trace_xs_chip",
    }

    assert all(callable(getattr(xs_chip, name)) for name in fixture_cells)
    assert fixture_cells.isdisjoint(cells.__all__)
    assert fixture_cells.isdisjoint(PDK.cells)


def test_pdk_registry_contains_public_cpw_cross_sections() -> None:
    expected = {
        "coplanar_waveguide",
        "cpw_2dot7_4_2dot7",
        "cpw_6_7_6",
        "cpw_6_10_6",
        "cpw_15_5_15",
    }

    assert expected <= set(PDK.cross_sections)
    assert not any(name.startswith("as_") for name in PDK.cross_sections)


def test_layer_yaml_matches_public_layer_map() -> None:
    assert PATH.lyp_yaml.exists()
    assert PATH.lyp.exists()
    assert PATH.lyt.exists()

    layer_views = LayerViews(PATH.lyp_yaml)
    layers_from_yaml = layer_views_to_tuples(layer_views)
    layers_defined = {
        str(layer_enum): (layer_enum.layer, layer_enum.datatype) for layer_enum in LAYER
    }

    assert layers_from_yaml == layers_defined


def test_pdk_uses_yaml_layer_views() -> None:
    assert layer_views_to_tuples(LAYER_VIEWS) == layer_views_to_tuples(LayerViews(PATH.lyp_yaml))


def test_gdsfactory_get_component_works_after_activation() -> None:
    PDK.activate()

    assert gf.get_component("cpw_straight").name.startswith("cpw_straight")
    assert gf.get_component("launcher").ports
    assert gf.get_component("interdigital_capacitor").ports
    assert gf.get_component("martinis2022_differential_ribbon_capacitor").ports
    assert gf.get_component("resonator").ports
    assert gf.get_component("taper").ports


def test_public_samples_hold_demo_cells_after_registry_cleanup() -> None:
    samples = package.get_sample_functions()

    assert set(samples) == {
        "orpen_sc_pdk.samples.simulation_demos.global_purcell_filter_demo_chip",
        "orpen_sc_pdk.samples.simulation_demos.resonator_with_indium_bumps",
        "orpen_sc_pdk.samples.simulation_demos.sim_flip_chip_distance",
        "orpen_sc_pdk.samples.simulation_demos.sim_flip_chip_distance_keepout_global_routing_demo",
        "orpen_sc_pdk.samples.simulation_demos.sim_flip_chip_distance_keepout_routing_demo",
        "orpen_sc_pdk.samples.simulation_demos.small_airbridge_chip",
    }
    resonator_coupon = samples[
        "orpen_sc_pdk.samples.simulation_demos.resonator_with_indium_bumps"
    ]()
    resonator_flat = resonator_coupon.copy()
    resonator_flat.flatten()
    resonator_polygons = resonator_flat.get_polygons(merge=False, by="tuple")
    assert resonator_coupon.ports
    assert resonator_coupon.size_info.width < 2500
    assert resonator_coupon.size_info.height < 2500
    assert (
        len(resonator_polygons[(LAYER.D0_D1_INDIUM_BUMP.layer, LAYER.D0_D1_INDIUM_BUMP.datatype)])
        > 100
    )
    assert (
        len(resonator_polygons[(LAYER.D0_D1_UNDER_BUMP.layer, LAYER.D0_D1_UNDER_BUMP.datatype)])
        > 100
    )
    assert (
        len(resonator_polygons[(LAYER.D1_BOTTOM_M1_ETCH.layer, LAYER.D1_BOTTOM_M1_ETCH.datatype)])
        == 1
    )
    assert (
        len(resonator_polygons.get((LAYER.D0_TOP_AB_DRAW.layer, LAYER.D0_TOP_AB_DRAW.datatype), []))
        == 0
    )

    airbridge_chip = samples["orpen_sc_pdk.samples.simulation_demos.small_airbridge_chip"]()
    airbridge_flat = airbridge_chip.copy()
    airbridge_flat.flatten()
    airbridge_polygons = airbridge_flat.get_polygons(merge=False, by="tuple")
    assert {port.name for port in airbridge_chip.ports} == {"o_left", "o_right"}
    assert len(airbridge_polygons[(LAYER.D0_TOP_AB_DRAW.layer, LAYER.D0_TOP_AB_DRAW.datatype)]) == 3
    assert len(airbridge_polygons[(LAYER.D0_TOP_AB_VIA.layer, LAYER.D0_TOP_AB_VIA.datatype)]) == 6
    assert samples["orpen_sc_pdk.samples.simulation_demos.sim_flip_chip_distance"]().ports
