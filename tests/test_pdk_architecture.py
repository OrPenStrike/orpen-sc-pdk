from __future__ import annotations

import gdsfactory as gf
from gdsfactory.technology import LayerViews

import orpen_sc_pdk
from orpen_sc_pdk import PDK, cells, config, models, tech
from orpen_sc_pdk.helper import layer_views_to_tuples


def test_orpen_style_public_import_surface() -> None:
    assert orpen_sc_pdk.PATH == config.PATH
    assert cells.cpw_straight
    assert cells.interdigital_capacitor
    assert cells.launcher
    assert cells.resonator
    assert cells.taper
    assert (tech.LAYER.D0_TOP_M1_DRAW.layer, tech.LAYER.D0_TOP_M1_DRAW.datatype) == (1, 0)
    assert (tech.LAYER.D1_D2_UNDER_BUMP.layer, tech.LAYER.D1_D2_UNDER_BUMP.datatype) == (41, 1)
    assert models.__all__ == []


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
        "single_trace_flip_chip_xs_chip",
        "single_trace_xs_chip",
        "straight",
        "two_trace_flip_chip_xs_chip",
        "two_trace_xs_chip",
    }

    assert set(PDK.cells) == expected


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


def test_pdk_registry_contains_public_cpw_cross_sections() -> None:
    expected = {
        "as_coplanar_waveguide",
        "as_cpw_2dot7_4_2dot7",
        "as_cpw_6_7_6",
        "as_cpw_6_10_6",
        "as_cpw_15_5_15",
    }

    assert expected <= set(PDK.cross_sections)


def test_layer_yaml_matches_public_layer_map() -> None:
    assert config.PATH.lyp_yaml.exists()
    assert config.PATH.lyp.exists()
    assert config.PATH.lyt.exists()

    layer_views = LayerViews(config.PATH.lyp_yaml)
    layers_from_yaml = layer_views_to_tuples(layer_views)
    layers_defined = {
        str(layer_enum): (layer_enum.layer, layer_enum.datatype) for layer_enum in tech.LAYER
    }

    assert layers_from_yaml == layers_defined


def test_pdk_uses_yaml_layer_views() -> None:
    assert layer_views_to_tuples(tech.LAYER_VIEWS) == layer_views_to_tuples(
        LayerViews(config.PATH.lyp_yaml)
    )


def test_gdsfactory_get_component_works_after_activation() -> None:
    orpen_sc_pdk.activate()

    assert gf.get_component("cpw_straight").name.startswith("cpw_straight")
    assert gf.get_component("launcher").ports
    assert gf.get_component("interdigital_capacitor").ports
    assert gf.get_component("resonator").ports
    assert gf.get_component("taper").ports


def test_public_samples_are_empty_after_registry_cleanup() -> None:
    assert orpen_sc_pdk.get_sample_functions() == {}
