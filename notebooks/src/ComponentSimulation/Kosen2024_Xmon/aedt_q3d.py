# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Public OrPen Xmon — AEDT Q3D grounded C11 cross-check
#
# This public workflow extracts the tuned Xmon capacitance with the pad as the
# sole signal. The four couplers, both face ground planes, and corner-authored
# indium shorts share the grounded net, matching the Palace grounded-C11
# boundary. Q3D is cross-solver evidence; no solver-agreement gate is implied.

# %%
from __future__ import annotations

import subprocess
from itertools import count
from pathlib import Path

import gdsfactory as gf
from IPython.display import display
from scgsim.aedt import (
    LayerImport,
    MatrixRunControl,
    ObjectBinding,
    PdkMaterial,
    Q3dNetSpec,
    Q3dSpec,
    prepare_handoff,
    resolve_results,
)
from scgsim.sgb import build_component_stack

import orpen_sc_pdk
from orpen_sc_pdk import LAYER_STACK, get_material_records
from orpen_sc_pdk.helpers.assembly import place_flip_chip_ground_short_bumps

orpen_sc_pdk.activate()

# %% [markdown]
# ## Run controls

# %%
WORKFLOW_ACTION = "prepare_handoff"  # prepare_handoff | run | analyze_handoff
RUN_ID = "kosen2024_xmon_q3d_l309p5_w24p65_g20_20260827_02"
OUTPUT_ROOT = Path.cwd() / ".artifacts"
RUN_DIR = OUTPUT_ROOT / RUN_ID
RETURNED_RUN_DIR = RUN_DIR
SOURCE_GDS = OUTPUT_ROOT / "q3d_geometry" / f"{RUN_ID}.gds"

if WORKFLOW_ACTION not in {"prepare_handoff", "run", "analyze_handoff"}:
    raise ValueError("WORKFLOW_ACTION must be prepare_handoff, run, or analyze_handoff.")

# %% [markdown]
# ## Build the tuned physical coupon

# %%
if WORKFLOW_ACTION in {"prepare_handoff", "run"}:
    orpen_sc_pdk.activate()
    gf.clear_cache()
    device = gf.get_component(
        "kosen2024_flip_chip_xmon_qubit",
        bump_ring_count_per_side=0,
        qubit_pad_length=309.5,
        qubit_pad_width=24.65,
        qubit_gap=20.0,
    )
    coupon = place_flip_chip_ground_short_bumps(
        device,
        coupon_padding_um=75.0,
        clearance_um=30.0,
        placement_mode="corner_anchors",
    )
    component = coupon.component
    stack = build_component_stack(
        component=component,
        layer_stack=LAYER_STACK,
        material_records=get_material_records(),
        coupon_padding_um=coupon.stack_coupon_padding_um,
    )
    display(component)

# %% [markdown]
# ## Materialize semantic Q3D conductor layers
#
# Q3D imports positive GDS layers. The PDK remains authoritative: this cell
# evaluates its typed die-face metal construction, then assigns only the Xmon
# pad to the Signal net. Every remaining conductor is grounded for C11.

# %%
if WORKFLOW_ACTION in {"prepare_handoff", "run"}:
    flat = component.copy()
    flat.flatten()
    dbu = float(flat.kcl.dbu)
    layer_records = {item["semantic_id"]: item for item in stack["layers"]}
    d0_ground_record = layer_records["D0_TOP_GROUND_PLANE"]
    d1_ground_record = layer_records["D1_BOTTOM_GROUND_PLANE"]
    bump_record = layer_records["D0_D1_INDIUM_BUMP"]

    bounds = stack["solution_regions"]["D1_SUBSTRATE"]["geometry"]["domain_bounds_um"]
    domain_box = gf.kdb.Box(
        *(round(bounds[key] / dbu) for key in ("x_min_um", "y_min_um", "x_max_um", "y_max_um"))
    )
    domain = gf.Region(domain_box)

    d1_draw = flat.get_region(tuple(d1_ground_record["geometry"]["include_layer"]), merge=True)
    d1_mask = flat.get_region(tuple(d1_ground_record["geometry"]["mask_layer"]), merge=True)
    d1_metal = (domain - (d1_mask - d1_draw)).merged()
    semantic_regions = component.info["component_semantics"]["conductor_regions"]
    xmon_record = next(item for item in semantic_regions if item["semantic_id"] == "D1_XMON_PAD")
    xmon_selector = gf.kdb.Point(
        *(round(value / dbu) for value in xmon_record["geometry"]["selector_point_um"])
    )
    xmon_region = gf.Region()
    d1_ground_region = gf.Region()
    for polygon in d1_metal.each_merged():
        (xmon_region if polygon.inside(xmon_selector) else d1_ground_region).insert(polygon)
    if xmon_region.count() != 1 or d1_ground_region.count() != 1:
        raise ValueError("Expected one Xmon-pad region and one grounded D1 residual region.")

    d0_mask = flat.get_region((d0_ground_record["layer"], d0_ground_record["datatype"]), merge=True)
    d0_ground_region = (domain - d0_mask).merged()
    bump_region = flat.get_region((bump_record["layer"], bump_record["datatype"]), merge=True)

    q3d_geometry = gf.Component()
    layer_numbers = count(300)
    layer_imports: list[LayerImport] = []
    object_bindings: list[ObjectBinding] = []

    def add_import_region(
        prefix: str,
        region: gf.Region,
        z_min_um: float,
        z_max_um: float,
        role: str,
        material_id: str,
    ) -> tuple[str, ...]:
        polygons = list(region.each_merged())
        if not polygons:
            raise ValueError(f"Q3D region {prefix!r} is empty.")
        names = []
        for index, polygon in enumerate(polygons):
            layer = next(layer_numbers)
            layer_name = f"{prefix}{index:02d}" if len(polygons) > 1 else prefix
            object_name = f"{layer_name}_1"
            q3d_geometry.add_polygon(points=polygon.resolved_holes(), layer=(layer, 0))
            layer_imports.append(LayerImport(layer, 0, layer_name, z_min_um, z_max_um))
            object_bindings.append(ObjectBinding(object_name, layer, role, material_id))
            names.append(object_name)
        return tuple(names)

    d1_z = float(d1_ground_record["geometry"]["z_um"])
    d1_top = d1_z + float(d1_ground_record["geometry"]["thickness_um"])
    d0_z = float(d0_ground_record["geometry"]["z_um"])
    d0_top = d0_z + float(d0_ground_record["geometry"]["thickness_um"])
    bump_z = float(bump_record["geometry"]["z_um"])
    bump_top = bump_z + float(bump_record["geometry"]["thickness_um"])

    xmon_object = add_import_region("QXMON", xmon_region, d1_z, d1_top, "signal", "Al")[0]
    ground_objects = (
        *add_import_region("QGD1", d1_ground_region, d1_z, d1_top, "ground", "Al"),
        *add_import_region("QGD0", d0_ground_region, d0_z, d0_top, "ground", "Al"),
        *add_import_region("QGB", bump_region, bump_z, bump_top, "ground", "Al"),
    )
    for semantic_id, prefix in (("D0_SUBSTRATE", "QSD0"), ("D1_SUBSTRATE", "QSD1")):
        geometry = stack["solution_regions"][semantic_id]["geometry"]
        substrate_bounds = geometry["domain_bounds_um"]
        substrate_region = gf.Region(
            gf.kdb.Box(
                *(
                    round(substrate_bounds[key] / dbu)
                    for key in ("x_min_um", "y_min_um", "x_max_um", "y_max_um")
                )
            )
        )
        add_import_region(
            prefix,
            substrate_region,
            float(geometry["z_min_um"]),
            float(geometry["z_max_um"]),
            "substrate",
            "Si",
        )

    SOURCE_GDS.parent.mkdir(parents=True, exist_ok=True)
    q3d_geometry.write_gds(SOURCE_GDS, with_metadata=False)
    roundtrip = gf.kdb.Layout()
    roundtrip.read(str(SOURCE_GDS))
    top_cell = roundtrip.top_cell()
    if any(
        gf.Region(top_cell.begin_shapes_rec(roundtrip.layer(item.layer, item.datatype)))
        .merged()
        .count()
        != 1
        for item in layer_imports
    ):
        raise ValueError("Each Q3D import layer must round-trip as exactly one object.")
    display(q3d_geometry)

# %% [markdown]
# ## Q3D handoff

# %%
HANDOFF = None
if WORKFLOW_ACTION in {"prepare_handoff", "run"}:
    material_records = get_material_records()
    materials = {
        material_id: PdkMaterial(
            material_id,
            material_records[material_id]["material_kind"],
            material_records[material_id]["is_superconducting"],
            material_records[material_id]["aedt_library_name"],
        )
        for material_id in ("vacuum", "Si", "Al")
    }
    spec = Q3dSpec(
        gds_path=SOURCE_GDS,
        project_name=RUN_ID,
        design_name="Kosen2024XmonQ3d",
        materials=materials,
        vacuum_material_id="vacuum",
        layer_imports=tuple(layer_imports),
        object_bindings=tuple(object_bindings),
        nets=(
            Q3dNetSpec(
                "xmon_pad",
                "Signal",
                (xmon_object,),
                xmon_object,
                "-Z",
                xmon_object,
                "+Z",
            ),
            Q3dNetSpec("ground", "Ground", ground_objects),
        ),
        run_control=MatrixRunControl(
            setup_name="Setup1",
            frequency_ghz=4.7,
            maximum_passes=20,
            convergence_percent=0.1,
        ),
        region_padding_um=(100.0, 100.0, 100.0, 100.0, 1000.0, 1000.0),
        aedt_version="2024.2",
    )
    HANDOFF = prepare_handoff(spec=spec, output_dir=RUN_DIR)
display(HANDOFF)

# %% [markdown]
# ## Execute or analyze

# %%
if WORKFLOW_ACTION == "run":
    subprocess.run([str(HANDOFF.script_path)], cwd=HANDOFF.run_dir, check=True)

RESULT = (
    resolve_results(RETURNED_RUN_DIR) if WORKFLOW_ACTION in {"run", "analyze_handoff"} else None
)
display(RESULT)
if RESULT is not None:
    display(RESULT.convergence)
    display(RESULT.physics_results())
    display(RESULT.simulation_benchmark())

# %%
display(RESULT.project_path if RESULT is not None else HANDOFF.archive_path)
