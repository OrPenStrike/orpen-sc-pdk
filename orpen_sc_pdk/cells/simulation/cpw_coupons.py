"""Public finite CPW and the selected 17-bridge port-comparison source pair.

Geometry is in micrometres. These source factories do not assign final Nets,
native terminals, solver settings, or scientific acceptance. The meander pair
preserves the owner assembly selected on 2026-10-10, including full landings.
"""

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any, Literal

import gdsfactory as gf

from orpen_sc_pdk import tech
from orpen_sc_pdk.cells.layout.airbridge import airbridge
from orpen_sc_pdk.cells.layout.cpw import launcher, n_trace_mtl_section
from orpen_sc_pdk.cells.layout.primitives import straight
from orpen_sc_pdk.cells.layout.resonator_meander import resonator_meander
from orpen_sc_pdk.materials import get_material_records

_XS = "cpw_6_7_6"
_BRIDGE_X = (-1600, -1400, -1200, -1000, -800, -600, 800, 1000, 1200, 1400, 1600)
_DOMAIN = (-2235.0, -560.0, 2235.0, 1531.5)


@gf.cell(tags=["simulation", "cpw", "finite_ground"])
def finite_ground_cpw_coupon() -> gf.Component:
    """The existing four-rectangle L500/W10/gap6/ground80 notebook coupon."""
    c = gf.Component()
    signal = c << gf.components.rectangle(
        size=(500.0, 10.0), centered=True, layer=tech.LAYER.D0_TOP_M1_DRAW
    )
    signal.name = "SIGNAL"
    for y, name in ((51.0, "GROUND_PLUS"), (-51.0, "GROUND_MINUS")):
        ground = c << gf.components.rectangle(
            size=(500.0, 80.0), centered=True, layer=tech.LAYER.D0_TOP_M1_DRAW
        )
        ground.name = name
        ground.movey(y)
    substrate = c << gf.components.rectangle(
        size=(500.0, 182.0), centered=True, layer=tech.LAYER.D0_SUBSTRATE_AREA
    )
    substrate.name = "SUBSTRATE"
    c.info["component_semantics"] = {
        "schema_version": 2,
        "conductor_regions": [
            {
                "semantic_id": name,
                "level": "D0_TOP_M1",
                "gds_layer": tuple(tech.LAYER.D0_TOP_M1_DRAW),
                "geometry": {"geometry_source": "gds_polygon", "selector_point_um": point},
            }
            for name, point in (
                ("SIGNAL", (0.0, 0.0)),
                ("GROUND_PLUS", (0.0, 51.0)),
                ("GROUND_MINUS", (0.0, -51.0)),
            )
        ],
    }
    return c


def _shared_core() -> tuple[gf.Component, gf.Component]:
    body = gf.Component()
    mtl_xs = gf.get_cross_section("coupled_cpw_w7_s6_d3", trace_names=("p", "r"))
    hook = body << n_trace_mtl_section(length=500, cross_section=mtl_xs)
    hook.move((-250, 11))
    r_lead = body << straight(length=100, cross_section=_XS)
    r_lead.connect("o1", hook.ports["r_o2"])
    meander = body << resonator_meander(
        length=4000, meanders=6, cpw_xs=_XS, cpw_radius=100, open_end=True
    )
    meander.mirror()
    meander.connect("o1", r_lead.ports["o2"])
    short_lead = body << straight(length=100, cross_section=_XS)
    short_lead.connect("o1", hook.ports["r_o1"])
    for side, terminal in (("left", "p_o1"), ("right", "p_o2")):
        lead = body << straight(length=1500, cross_section=_XS)
        lead.connect("o1", hook.ports[terminal])
        body.add_port(side, port=lead.ports["o2"])
    body.add_port("r_short_anchor", port=short_lead.ports["o2"])
    body.add_port("r_open_placement", port=meander.ports["o2"])
    short = gf.Component()
    bar = short << gf.components.rectangle(
        size=(6, 21), centered=True, layer=tech.LAYER.D0_TOP_M1_DRAW
    )
    bar.move(body.ports["r_short_anchor"].center)
    common = gf.Component()
    common << body
    common << short
    canonical_bridge = airbridge()
    landings = gf.Component()
    for y in (-42, 42):
        landing = landings << gf.components.rectangle(
            size=(14, 14), centered=True, layer=tech.LAYER.D0_TOP_AB_DRAW
        )
        landing.move((0, y))
    full_deck = gf.boolean(
        A=canonical_bridge,
        B=landings,
        operation="or",
        layer=tech.LAYER.D0_TOP_AB_DRAW,
        layer1=tech.LAYER.D0_TOP_AB_DRAW,
        layer2=tech.LAYER.D0_TOP_AB_DRAW,
    )
    full_bridge = gf.Component()
    full_bridge << full_deck
    for polygon in canonical_bridge.get_polygons_points(by="tuple")[(10, 1)]:
        full_bridge.add_polygon(polygon, layer=tech.LAYER.D0_TOP_AB_VIA)
    bridge = gf.Component()
    for x in _BRIDGE_X:
        ref = bridge << full_bridge
        ref.move((x, 0))
    canonical_meander = resonator_meander(
        length=4000, meanders=6, cpw_xs=_XS, cpw_radius=100, open_end=True
    )
    # The lowest row is intentionally omitted: its deck also crosses the TL.
    for i in range(1, len(canonical_meander.info["straight_lengths"])):
        ref = bridge << full_bridge
        ref.move(meander.ports[f"o_mesh_meander_straight_{i}"].center)
    common << bridge
    common.add_ports(body.ports)
    return common, short


def _meander_coupon(mode: Literal["lumped", "wave"]) -> gf.Component:
    common, short = _shared_core()
    structure = gf.Component()
    structure << common
    for side in ("left", "right"):
        anchor = common.ports[side]
        if mode == "lumped":
            endpoint = structure << launcher(cpw_xs=_XS)
            endpoint.connect("o_neck", anchor)
            structure.add_port(f"{side}_signal", port=endpoint.ports["o_pad"])
            structure.add_port(f"{side}_source_locator", port=endpoint.ports["o_lumped"])
        else:
            x = _DOMAIN[0] if side == "left" else _DOMAIN[2]
            endpoint = structure << straight(length=abs(x - anchor.center[0]), cross_section=_XS)
            endpoint.connect("o1", anchor)
            structure.add_port(f"{side}_wave_cut", port=endpoint.ports["o2"])
    domain = gf.Component()
    x0, y0, x1, y1 = _DOMAIN
    ref = domain << gf.components.rectangle(
        size=(x1 - x0, y1 - y0), layer=tech.LAYER.D0_SUBSTRATE_AREA
    )
    ref.move((x0, y0))
    # Preserve the selected positive Ground recipe, including its short overlap.
    etch_void = gf.boolean(
        A=domain,
        B=structure,
        operation="not",
        layer=tech.LAYER.D0_TOP_M1_DRAW,
        layer1=tech.LAYER.D0_SUBSTRATE_AREA,
        layer2=tech.LAYER.D0_TOP_M1_ETCH,
    )
    original_draw = gf.boolean(
        A=structure,
        B=short,
        operation="not",
        layer=tech.LAYER.D0_TOP_M1_DRAW,
        layer1=tech.LAYER.D0_TOP_M1_DRAW,
        layer2=tech.LAYER.D0_TOP_M1_DRAW,
    )
    ground = gf.boolean(
        A=etch_void,
        B=original_draw,
        operation="not",
        layer=tech.LAYER.D0_TOP_M1_DRAW,
        layer1=tech.LAYER.D0_TOP_M1_DRAW,
        layer2=tech.LAYER.D0_TOP_M1_DRAW,
    )
    c = gf.Component()
    c << structure
    c << ground
    c << domain
    c.add_ports(structure.ports)
    c.info["source_record_variant"] = mode
    c.info["source_record_getter"] = "get_cpw_meander_airbridge_source_records"
    c.info["positive_ground_recipe"] = "DOMAIN - actual ETCH - original DRAW without short bar"
    c.info["stack_selection"] = "get_single_die_layer_stack(include_airbridges=True)"
    return c


@gf.cell(tags=["simulation", "cpw", "meander", "airbridge", "lumped"])
def cpw_meander_airbridge_lumped_coupon() -> gf.Component:
    """Selected 17-bridge source with both launchers and actual 202/1 sheets."""
    return _meander_coupon("lumped")


@gf.cell(tags=["simulation", "cpw", "meander", "airbridge", "wave"])
def cpw_meander_airbridge_wave_coupon() -> gf.Component:
    """Same selected core without launchers; through cuts at x = +/-2235 um."""
    return _meander_coupon("wave")


def get_cpw_meander_airbridge_source_records(
    mode: Literal["lumped", "wave"],
) -> dict[str, Any]:
    """Return detached owner-authored V5 rings/bodies and V6 local supports.

    The record retains complete placed and local geometry, producer occurrence
    identities and caller-only Net proposals. ``local_supports`` carries full
    local sheets, local contact endpoints and normals; the corresponding Entity
    supplies the once-only local-to-assembly affine. These are producer-local
    source IDs, not GF-generated cell names or native IDs.
    Callers construct SCGSim public inputs and own final Nets; this is source
    data, not a second runtime adapter. No transform applies to placed rings.

    ``source_levels`` and ``material_records`` are detached current PDK facts.
    The selected source preview envelope (-500 to +100 um) is not a generated
    native vacuum region or a solver default. Wave references name the one
    Ground Entity and its two disconnected source polygons, not native objects.
    """
    resources = files(__package__)
    record = json.loads(resources.joinpath("cpw_meander_source.json").read_text())[mode]
    for support in record["local_supports"]:
        owner = next(
            entity
            for entity in record["entities"]
            if entity["source_occurrence_path"] == support["source_occurrence_path"]
        )
        affine = owner["affine_local_to_assembly"]
        support["source_transform"] = [
            affine[0][0],
            affine[0][1],
            affine[1][0],
            affine[1][1],
            affine[0][2],
            affine[1][2],
        ]
    stack = tech.get_single_die_layer_stack(include_airbridges=True)
    record["source_levels"] = {
        name: {
            "zmin": level.zmin,
            "thickness": level.thickness,
            "material": level.material,
            "mesh_order": level.mesh_order,
            "info": deepcopy(level.info),
        }
        for name, level in stack.layers.items()
    }
    materials = get_material_records()
    record["material_records"] = {name: materials[name] for name in ("Al", "Si", "vacuum")}
    record["source_dbu_um"] = gf.kcl.dbu
    # Selected assembly's Si bottom and proposed YZ source-sheet air top;
    # neither value grants native air-domain or scientific Gate authority.
    record["source_envelope"] = {
        "bounds_xy_um": list(_DOMAIN),
        "z_interval_um": [-500.0, 100.0],
        "state": "source_preview_selection_not_native_air_region",
    }
    record["wave_sources"] = []
    if mode == "wave":
        entities = {entity["qualified_entity_id"]: entity for entity in record["entities"]}
        ground = entities["wave/positive-ground::GROUND"]
        for proposal in record["source_domain"]["wave_exterior_source_proposals"]:
            signal = entities[f"wave/endpoint-{proposal['side']}::SIGNAL"]
            record["wave_sources"].append(
                {
                    "side": proposal["side"],
                    "cut_x_um": proposal["cut_x_um"],
                    "normal": list(proposal["normal"]),
                    "corners_um": deepcopy(proposal["proposed_yz_corners_um"]),
                    "signal_entity_id": (
                        f"{signal['source_occurrence_path']}/{signal['local_semantic_id']}"
                    ),
                    "reference_entity_ids": [
                        f"{ground['source_occurrence_path']}/{ground['local_semantic_id']}"
                    ],
                    "reference_polygon_ids": [
                        polygon["polygon_id"] for polygon in ground["placed_polygons"]
                    ],
                    "state": "source_declaration_not_native_terminal_or_solved_mode",
                }
            )
    return record
