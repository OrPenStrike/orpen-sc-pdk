"""PDK construction and activation."""

from functools import lru_cache

from gdsfactory.pdk import Pdk

from orpen_sc_pdk import tech
from orpen_sc_pdk.cells import (
    bend_circular,
    bend_euler,
    cpw_straight,
    dicing_edge,
    global_purcell_filter_demo_chip,
    indium_bump,
    indium_ground,
    interdigital_capacitor,
    launcher,
    manhattan_style_junction,
    martinis2022_differential_ribbon_capacitor,
    resonator,
    resonator_hanger,
    resonator_meander,
    sim_flip_chip_distance,
    sim_flip_chip_distance_keepout_global_routing_demo,
    sim_flip_chip_distance_keepout_routing_demo,
    single_trace_flip_chip_xs_chip,
    single_trace_xs_chip,
    straight,
    taper,
    two_trace_flip_chip_xs_chip,
    two_trace_xs_chip,
)
from orpen_sc_pdk.ports import register_sim_port_types
from orpen_sc_pdk.tech import (
    coplanar_waveguide,
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
    strip,
    strip_metal,
)

_cells = {
    "indium_bump": indium_bump,
    "indium_ground": indium_ground,
    "resonator": resonator,
    "resonator_hanger": resonator_hanger,
    "resonator_meander": resonator_meander,
    "taper": taper,
    "bend_circular": bend_circular,
    "bend_euler": bend_euler,
    "cpw_straight": cpw_straight,
    "dicing_edge": dicing_edge,
    "global_purcell_filter_demo_chip": global_purcell_filter_demo_chip,
    "interdigital_capacitor": interdigital_capacitor,
    "launcher": launcher,
    "manhattan_style_junction": manhattan_style_junction,
    "martinis2022_differential_ribbon_capacitor": martinis2022_differential_ribbon_capacitor,
    "single_trace_flip_chip_xs_chip": single_trace_flip_chip_xs_chip,
    "single_trace_xs_chip": single_trace_xs_chip,
    "sim_flip_chip_distance": sim_flip_chip_distance,
    "sim_flip_chip_distance_keepout_global_routing_demo": (
        sim_flip_chip_distance_keepout_global_routing_demo
    ),
    "sim_flip_chip_distance_keepout_routing_demo": sim_flip_chip_distance_keepout_routing_demo,
    "straight": straight,
    "two_trace_flip_chip_xs_chip": two_trace_flip_chip_xs_chip,
    "two_trace_xs_chip": two_trace_xs_chip,
}

_cross_sections = {
    "coplanar_waveguide": coplanar_waveguide,
    "cpw": cpw,
    "cpw_2dot7_4_2dot7": cpw_2dot7_4_2dot7,
    "cpw_6_7_6": cpw_6_7_6,
    "cpw_6_10_6": cpw_6_10_6,
    "cpw_15_5_15": cpw_15_5_15,
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
