"""PDK construction and activation."""

from functools import lru_cache

from gdsfactory.pdk import Pdk

from orpen_sc_pdk import tech
from orpen_sc_pdk.cells import (
    airbridge,
    bend_circular,
    bend_euler,
    capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators,
    cpw_straight,
    cpw_t_junction,
    dicing_edge,
    indium_bump,
    indium_ground,
    interdigital_capacitor,
    interdigital_capacitor_q3d_coupon,
    kosen2024_flip_chip_xmon_qubit,
    launcher,
    manhattan_style_junction,
    martinis2022_differential_ribbon_capacitor,
    mtl_bend_bend_transition,
    mtl_bend_coupling_section,
    mtl_straight_bend_coupling_section,
    mtl_straight_bend_transition,
    n_trace_mtl_section,
    resonator,
    resonator_hanger,
    resonator_meander,
    straight,
    taper,
)
from orpen_sc_pdk.ports import register_sim_port_types
from orpen_sc_pdk.tech import (
    coplanar_waveguide,
    coupled_cpw_w7_s6_d3,
    cpw,
    cpw_2dot7_4_2dot7,
    cpw_6_7_6,
    cpw_6_10_6,
    cpw_15_5_15,
    etch,
    etch_only,
    josephson_junction_cross_section_narrow,
    josephson_junction_cross_section_wide,
    launcher_cross_section_big,
    microstrip,
    n_trace_coplanar_waveguide,
    strip,
    strip_metal,
)

_cells = {
    "indium_bump": indium_bump,
    "airbridge": airbridge,
    "indium_ground": indium_ground,
    "resonator": resonator,
    "resonator_hanger": resonator_hanger,
    "resonator_meander": resonator_meander,
    "taper": taper,
    "bend_circular": bend_circular,
    "bend_euler": bend_euler,
    "cpw_straight": cpw_straight,
    "cpw_t_junction": cpw_t_junction,
    "capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators": (
        capacitive_coupling_intrinsic_individual_purcell_filter_readout_resonators
    ),
    "n_trace_mtl_section": n_trace_mtl_section,
    "mtl_bend_coupling_section": mtl_bend_coupling_section,
    "mtl_straight_bend_coupling_section": mtl_straight_bend_coupling_section,
    "mtl_straight_bend_transition": mtl_straight_bend_transition,
    "mtl_bend_bend_transition": mtl_bend_bend_transition,
    "dicing_edge": dicing_edge,
    "interdigital_capacitor": interdigital_capacitor,
    "interdigital_capacitor_q3d_coupon": interdigital_capacitor_q3d_coupon,
    "kosen2024_flip_chip_xmon_qubit": kosen2024_flip_chip_xmon_qubit,
    "launcher": launcher,
    "manhattan_style_junction": manhattan_style_junction,
    "martinis2022_differential_ribbon_capacitor": martinis2022_differential_ribbon_capacitor,
    "straight": straight,
}

_cross_sections = {
    "coplanar_waveguide": coplanar_waveguide,
    "coupled_cpw_w7_s6_d3": coupled_cpw_w7_s6_d3,
    "cpw": cpw,
    "cpw_2dot7_4_2dot7": cpw_2dot7_4_2dot7,
    "cpw_6_7_6": cpw_6_7_6,
    "cpw_6_10_6": cpw_6_10_6,
    "cpw_15_5_15": cpw_15_5_15,
    "n_trace_coplanar_waveguide": n_trace_coplanar_waveguide,
    "etch": etch,
    "etch_only": etch_only,
    "josephson_junction_cross_section_narrow": josephson_junction_cross_section_narrow,
    "josephson_junction_cross_section_wide": josephson_junction_cross_section_wide,
    "launcher_cross_section_big": launcher_cross_section_big,
    "microstrip": microstrip,
    "strip": strip,
    "strip_metal": strip_metal,
}


@lru_cache
def get_pdk() -> Pdk:
    """Return the open superconducting quantum/RF PDK."""

    register_sim_port_types()
    return Pdk(
        name="orpen_sc_pdk",
        cells=_cells,
        cross_sections=_cross_sections,
        layers=tech.LAYER,
        layer_stack=tech.LAYER_STACK,
        layer_views=tech.LAYER_VIEWS,
        connectivity=tech.LAYER_CONNECTIVITY,
        routing_strategies=tech.routing_strategies,
    )


PDK = get_pdk()


def activate() -> Pdk:
    """Activate the open PDK and return it."""

    PDK.activate()
    return PDK
